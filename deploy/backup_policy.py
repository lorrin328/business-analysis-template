"""Capacity and retention policy; never remove a backup before explicit acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

BACKUP_NAME = re.compile(r"business_data\.db\.\d{8}_\d{6}(?:-\d+)?(?:\.frozen)?$")
DEFAULT_RESERVE = 2 * 1024**3


def check_space(database: str | Path, backup_dir: str | Path, *, copies: int = 2,
                reserve_bytes: int = DEFAULT_RESERVE, extra_bytes: int = 0) -> dict:
    source = Path(database).resolve()
    destination = Path(backup_dir).resolve()
    if copies < 1 or reserve_bytes < 0 or extra_bytes < 0:
        raise ValueError("invalid capacity policy")
    database_bytes = source.stat().st_size if source.is_file() else 0
    wal = Path(str(source) + "-wal")
    wal_bytes = wal.stat().st_size if wal.is_file() else 0
    recovery_bytes = database_bytes + wal_bytes
    shared_filesystem = source.parent.stat().st_dev == destination.stat().st_dev
    required = copies * recovery_bytes + reserve_bytes + extra_bytes
    if shared_filesystem:
        # A failed deployment needs one further atomic restore candidate while
        # both safety snapshots and the current database still exist.
        required += recovery_bytes
    available = shutil.disk_usage(destination).free
    if available < required:
        raise RuntimeError(f"insufficient backup space: required={required}, available={available}; existing backups preserved")
    # A separate data filesystem must retain room for WAL and a recovery copy.
    data_required = database_bytes + wal_bytes + reserve_bytes
    data_available = shutil.disk_usage(source.parent).free
    if data_available < data_required:
        raise RuntimeError(f"insufficient database recovery space: required={data_required}, available={data_available}")
    return {"databaseBytes": database_bytes, "walBytes": wal_bytes,
            "recoveryScratchBytes": recovery_bytes, "requiredBytes": required, "availableBytes": available}


def verify_backup(database: str | Path) -> dict:
    path = Path(database)
    if path.is_symlink() or not path.is_file():
        raise ValueError("backup must be a regular file")
    meta_path = Path(str(path) + ".meta")
    if meta_path.is_symlink():
        raise ValueError("backup metadata must not be a symlink")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if metadata.get("integrityCheck") != "ok" or metadata.get("quickCheck") != "ok":
        raise ValueError("backup metadata is not verified")
    if path.stat().st_size != metadata.get("sizeBytes"):
        raise ValueError("backup size differs from metadata")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != metadata.get("sha256"):
        raise ValueError("backup checksum differs from metadata")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("backup quick_check failed")
    return metadata


def prune_backups(backup_dir: str | Path, keep: str | Path) -> list[str]:
    """Remove only recognized, metadata-backed regular files beside verified keep."""
    root, retained = Path(backup_dir).resolve(), Path(keep).resolve()
    if retained.parent != root or not BACKUP_NAME.fullmatch(retained.name):
        raise ValueError("retained backup is outside the managed backup directory")
    verify_backup(retained)
    removed = []
    entries = sorted(root.iterdir())
    if any(path.is_file() and not path.is_symlink() and BACKUP_NAME.fullmatch(path.name)
           and path.name > retained.name for path in entries):
        raise RuntimeError("a newer backup exists; stale acceptance must not delete it")
    for path in entries:
        if path == retained or path.is_symlink() or not path.is_file() or not BACKUP_NAME.fullmatch(path.name):
            continue
        meta = Path(str(path) + ".meta")
        if not meta.is_file() or meta.is_symlink():
            continue
        # Unknown or incomplete backups are left for operator inspection.
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            valid_record = (data.get("integrityCheck") == "ok" and data.get("quickCheck") == "ok"
                            and data.get("sizeBytes") == path.stat().st_size
                            and re.fullmatch(r"[0-9a-f]{64}", str(data.get("sha256", ""))))
        except (OSError, ValueError):
            continue
        if not valid_record:
            continue
        path.unlink()
        meta.unlink()
        removed.append(path.name)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--copies", type=int, default=2)
    parser.add_argument("--reserve-bytes", type=int, default=DEFAULT_RESERVE)
    parser.add_argument("--extra-bytes", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(check_space(args.database, args.backup_dir, copies=args.copies,
                                 reserve_bytes=args.reserve_bytes, extra_bytes=args.extra_bytes)))


if __name__ == "__main__":
    main()
