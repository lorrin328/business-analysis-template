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
    source_conn = sqlite3.connect(str(source_path), timeout=30)
    destination_conn = sqlite3.connect(str(temp_path), timeout=30)
    backup_succeeded = False
    try:
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
        destination_conn.close()
        source_conn.close()
        if not backup_succeeded and temp_path.exists():
            temp_path.unlink()

    try:
        os.replace(temp_path, destination_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "source": str(source_path),
        "destination": str(destination_path),
        "sizeBytes": destination_path.stat().st_size,
        "sha256": _sha256(destination_path),
        "integrityCheck": integrity,
        "quickCheck": quick,
        "tableCount": len(tables),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--meta")
    args = parser.parse_args()
    metadata = backup_database(args.source, args.destination)
    payload = json.dumps(metadata, ensure_ascii=False, indent=2)
    if args.meta:
        Path(args.meta).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
