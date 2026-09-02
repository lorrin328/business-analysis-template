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


def test_failed_backup_cleans_only_its_own_sqlite_sidecars(tmp_path, monkeypatch):
    import backup_database as module
    source = tmp_path / "invalid.db"
    source.write_text("invalid")
    destination = tmp_path / "backup.db"
    unrelated = tmp_path / ".backup.db.other.tmp-wal"
    unrelated.write_text("not owned by this invocation")
    connect = module.sqlite3.connect

    def add_temporary_sidecars(path, *args, **kwargs):
        connection = connect(path, *args, **kwargs)
        if str(path).endswith(".tmp"):
            from pathlib import Path
            Path(str(path) + "-journal").write_text("temporary")
        return connection

    monkeypatch.setattr(module.sqlite3, "connect", add_temporary_sidecars)
    with pytest.raises(sqlite3.DatabaseError):
        backup_database(source, destination)
    assert list(tmp_path.glob(".backup.db.*")) == [unrelated]


def test_backup_does_not_replace_destination_created_during_backup(tmp_path, monkeypatch):
    import backup_database as module
    source, destination = tmp_path / "source.db", tmp_path / "backup.db"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE example(value INTEGER)")
    connection.commit()
    connection.close()
    link = module.os.link

    def concurrent_backup_wins(source_path, destination_path):
        destination.write_bytes(b"another completed backup")
        return link(source_path, destination_path)

    monkeypatch.setattr(module.os, "link", concurrent_backup_wins)
    with pytest.raises(FileExistsError):
        backup_database(source, destination)
    assert destination.read_bytes() == b"another completed backup"
    assert not list(tmp_path.glob(".backup.db.*.tmp*"))
