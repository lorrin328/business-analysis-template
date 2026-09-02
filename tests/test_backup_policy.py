import json
import sqlite3
import sys
from collections import namedtuple
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
import backup_policy
from backup_database import backup_database, write_metadata
from backup_policy import check_space, prune_backups, verify_backup


def verified_backup(source, destination):
    result = backup_database(source, destination)
    write_metadata(str(destination) + ".meta", result)
    return destination


def test_capacity_reserves_two_copies_wal_and_margin_without_deleting_backups(tmp_path, monkeypatch):
    source = tmp_path / "live.db"
    source.write_bytes(b"x" * 100)
    Path(str(source) + "-wal").write_bytes(b"x" * 40)
    old = tmp_path / "business_data.db.20260901_010000"
    old.write_bytes(b"keep")
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(backup_policy.shutil, "disk_usage", lambda _: usage(1000, 0, 469))
    with pytest.raises(RuntimeError, match="insufficient backup space"):
        check_space(source, tmp_path, copies=2, reserve_bytes=50)
    assert old.read_bytes() == b"keep"
    monkeypatch.setattr(backup_policy.shutil, "disk_usage", lambda _: usage(1000, 0, 470))
    assert check_space(source, tmp_path, copies=2, reserve_bytes=50)["requiredBytes"] == 470


def test_capacity_checks_separate_database_filesystem(tmp_path, monkeypatch):
    data, backups = tmp_path / "data", tmp_path / "backups"
    data.mkdir()
    backups.mkdir()
    source = data / "live.db"
    source.write_bytes(b"x" * 100)
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(backup_policy.shutil, "disk_usage", lambda path: usage(10000, 0, 10000 if path == backups else 10))
    with pytest.raises(RuntimeError, match="database recovery space"):
        check_space(source, backups, reserve_bytes=50)


def test_retention_validates_new_backup_before_removing_old_and_ignores_unknown_files(tmp_path):
    source = tmp_path / "live.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE example(value INTEGER)")
    old = verified_backup(source, tmp_path / "business_data.db.20260901_010000")
    latest = verified_backup(source, tmp_path / "business_data.db.20260902_010000-123.frozen")
    unknown = tmp_path / "business_data.db.manual-archive"
    unknown.write_text("operator archive")
    original = latest.read_bytes()
    latest.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(ValueError, match="checksum"):
        prune_backups(tmp_path, latest)
    assert old.exists()
    latest.write_bytes(original)
    assert prune_backups(tmp_path, latest) == [old.name]
    assert not old.exists()
    assert latest.exists() and unknown.exists()
    assert verify_backup(latest)["quickCheck"] == "ok"


def test_retention_refuses_external_keep(tmp_path):
    managed = tmp_path / "managed"
    managed.mkdir()
    with pytest.raises(ValueError, match="outside"):
        prune_backups(managed, tmp_path / "business_data.db.20260902_010000")


def test_stale_acceptance_never_deletes_a_newer_backup(tmp_path):
    source = tmp_path / "live.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE example(value INTEGER)")
    old = verified_backup(source, tmp_path / "business_data.db.20260901_010000")
    latest = verified_backup(source, tmp_path / "business_data.db.20260902_010000")
    with pytest.raises(RuntimeError, match="newer backup"):
        prune_backups(tmp_path, old)
    assert old.exists() and latest.exists()
