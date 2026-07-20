import sqlite3

import pytest

from backup_database import backup_database


def test_online_backup_includes_committed_wal_transactions(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "backup.db"
    conn = sqlite3.connect(source)
    try:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        conn.execute("CREATE TABLE sample (value INTEGER)")
        conn.commit()
        conn.execute("INSERT INTO sample VALUES (1)")
        conn.commit()

        metadata = backup_database(source, destination)
    finally:
        conn.close()

    with sqlite3.connect(destination) as restored:
        assert restored.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert metadata["integrityCheck"] == "ok"
    assert metadata["quickCheck"] == "ok"


def test_failed_backup_does_not_leave_destination_or_temp_file(tmp_path):
    source = tmp_path / "not-a-database.db"
    destination = tmp_path / "backup.db"
    source.write_text("invalid", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError):
        backup_database(source, destination)

    assert not destination.exists()
    assert not list(tmp_path.glob(".backup.db.*.tmp"))
