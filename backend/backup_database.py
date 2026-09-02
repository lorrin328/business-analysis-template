"""Create a consistent SQLite backup, including committed WAL transactions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_database(source: str | Path, destination: str | Path) -> dict:
    source_path = Path(source).resolve()
    destination_path = Path(destination).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"source database does not exist: {source_path}")
    if source_path == destination_path:
        raise ValueError("source and destination must be different files")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise FileExistsError(f"backup destination already exists: {destination_path}")

    temp_path = destination_path.with_name(f".{destination_path.name}.{uuid.uuid4().hex}.tmp")
    source_conn = None
    destination_conn = None
    backup_succeeded = False
    try:
        source_conn = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True, timeout=30)
        destination_conn = sqlite3.connect(str(temp_path), timeout=30)
        temp_path.chmod(0o600)
        source_conn.execute("PRAGMA busy_timeout=30000")
        source_conn.backup(destination_conn)
        destination_conn.commit()
        integrity = destination_conn.execute("PRAGMA integrity_check").fetchone()[0]
        quick = destination_conn.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok" or quick != "ok":
            raise RuntimeError(f"backup verification failed: integrity={integrity}, quick={quick}")
        tables = [
            row[0]
            for row in destination_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        backup_succeeded = True
    finally:
        if destination_conn is not None:
            destination_conn.close()
        if source_conn is not None:
            source_conn.close()
        if not backup_succeeded:
            _cleanup_temporary_backup(temp_path)

    try:
        # Same-directory hard link is atomic and refuses an existing destination,
        # including one created by another backup after the initial existence check.
        os.link(temp_path, destination_path)
    finally:
        _cleanup_temporary_backup(temp_path)

    return {
        "source": str(source_path),
        "destination": str(destination_path),
        "sizeBytes": destination_path.stat().st_size,
        "sha256": _sha256(destination_path),
        "integrityCheck": integrity,
        "quickCheck": quick,
        "tableCount": len(tables),
    }


def _cleanup_temporary_backup(path: Path) -> None:
    """Only this invocation's UUID temporary file and SQLite sidecars are owned."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = Path(str(path) + suffix)
        if candidate.exists() or candidate.is_symlink():
            candidate.unlink()


def write_metadata(path: str | Path, metadata: dict) -> None:
    destination = Path(path)
    temp = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.chmod(0o600)
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--meta")
    args = parser.parse_args()
    metadata = backup_database(args.source, args.destination)
    payload = json.dumps(metadata, ensure_ascii=False, indent=2)
    if args.meta:
        write_metadata(args.meta, metadata)
    print(payload)


if __name__ == "__main__":
    main()
