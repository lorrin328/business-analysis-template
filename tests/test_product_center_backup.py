"""Recovery-set checks use isolated SQLite files and synthetic originals."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import stat
import zipfile

import pytest

from product_center.backup import create_backup, restore_backup, verify_backup


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture()
def recovery_set(tmp_path):
    database = tmp_path / "live.db"
    store = tmp_path / "live-store"
    (store / "files").mkdir(parents=True)
    (store / "packages").mkdir()
    originals = {}
    packages = {}
    for number in (1, 2):
        raw = f"%PDF-1.4\nSynthetic original {number}; no business material\n%%EOF".encode()
        sha = digest(raw)
        entry = f"files/{sha}.pdf"
        originals[entry] = raw
        (store / entry).write_bytes(raw)
        manifest = {"formatVersion": 1, "synthetic": number}
        canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        manifest_hash = digest(canonical)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("manifest.json", canonical)
        entry = f"packages/{manifest_hash}.zip"
        packages[entry] = stream.getvalue()
        (store / entry).write_bytes(stream.getvalue())
    with sqlite3.connect(database) as conn:
        conn.executescript("""
            CREATE TABLE business_records(id INTEGER PRIMARY KEY, amount INTEGER);
            INSERT INTO business_records VALUES(1,123456);
            CREATE TABLE product_center_batches(id TEXT PRIMARY KEY, manifest_hash TEXT NOT NULL);
            CREATE TABLE product_center_sources(id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES product_center_batches(id), entry TEXT NOT NULL, sha256 TEXT NOT NULL);
            CREATE TABLE product_center_publications(id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES product_center_batches(id));
            CREATE TABLE product_center_state(id INTEGER PRIMARY KEY, publication_id INTEGER REFERENCES product_center_publications(id));
        """)
        for number, (entry, raw) in enumerate(originals.items(), 1):
            package_entry = list(packages)[number - 1]
            conn.execute("INSERT INTO product_center_batches VALUES(?,?)", (f"batch-{number}", Path(package_entry).stem))
            conn.execute("INSERT INTO product_center_sources VALUES(?,?,?,?)", (f"source-{number}", f"batch-{number}", entry, digest(raw)))
        conn.execute("INSERT INTO product_center_publications VALUES(1,'batch-2')")
        conn.execute("INSERT INTO product_center_state VALUES(1,1)")
    return database, store, tmp_path / "snapshot.zip", {**originals, **packages}


def rewrite_archive(archive_path, mutate):
    with zipfile.ZipFile(archive_path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    mutate(entries)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)


def test_snapshot_contains_full_database_all_history_and_referenced_originals(recovery_set):
    database, store, output, items = recovery_set
    report = create_backup(database, store, output)
    assert report["integrityCheck"] == "ok"
    assert report["activeBatchId"] == "batch-2"
    assert report["fileCount"] == 5
    assert report["sha256"] == digest(output.read_bytes())
    assert verify_backup(output) == report
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("backup-manifest.json"))
        assert set(archive.namelist()) == {"business_data.db", "backup-manifest.json", *["product_center_data/" + entry for entry in items]}
        for entry, raw in items.items():
            name = "product_center_data/" + entry
            assert archive.read(name) == raw
            assert manifest["files"][name] == {"sha256": digest(raw), "bytes": len(raw)}


def test_restore_to_new_directory_preserves_database_and_file_hashes(recovery_set, tmp_path):
    database, store, output, items = recovery_set
    create_backup(database, store, output)
    # A live change after backup must not contaminate the restored snapshot.
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE business_records SET amount=999")
    destination = tmp_path / "new-recovery"
    report = restore_backup(output, destination)
    assert report["activeBatchId"] == "batch-2"
    with sqlite3.connect(destination / "business_data.db") as conn:
        assert conn.execute("SELECT amount FROM business_records").fetchone()[0] == 123456
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    for entry, raw in items.items():
        assert digest((destination / "product_center_data" / entry).read_bytes()) == digest(raw)


def test_restore_refuses_nonempty_destination_without_changing_existing_files(recovery_set, tmp_path):
    database, store, output, _ = recovery_set
    create_backup(database, store, output)
    destination = tmp_path / "existing-recovery"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep original", encoding="utf-8")
    with pytest.raises(ValueError, match="空目录"):
        restore_backup(output, destination)
    assert sentinel.read_text(encoding="utf-8") == "keep original"
    assert sorted(p.name for p in destination.iterdir()) == ["keep.txt"]


def test_backup_refuses_overwriting_existing_snapshot(recovery_set):
    database, store, output, _ = recovery_set
    create_backup(database, store, output)
    before = output.read_bytes()
    with pytest.raises(ValueError, match="拒绝覆盖"):
        create_backup(database, store, output)
    assert output.read_bytes() == before


def test_missing_referenced_original_prevents_backup(recovery_set):
    database, store, output, items = recovery_set
    (store / next(entry for entry in items if entry.startswith("files/"))).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        create_backup(database, store, output)
    assert not output.exists()


def test_corrupt_referenced_original_prevents_backup(recovery_set):
    database, store, output, items = recovery_set
    (store / next(entry for entry in items if entry.startswith("files/"))).write_bytes(b"changed original")
    with pytest.raises(ValueError, match="哈希"):
        create_backup(database, store, output)
    assert not output.exists()


def test_missing_referenced_package_prevents_backup(recovery_set):
    database, store, output, items = recovery_set
    (store / next(entry for entry in items if entry.startswith("packages/"))).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        create_backup(database, store, output)
    assert not output.exists()


def test_stored_package_manifest_must_match_database_before_backup(recovery_set):
    database, store, output, items = recovery_set
    entry = next(entry for entry in items if entry.startswith("packages/"))
    with zipfile.ZipFile(store / entry, "w") as archive:
        archive.writestr("manifest.json", '{"changed":"not the reviewed manifest"}')
    with pytest.raises(ValueError, match="清单哈希"):
        create_backup(database, store, output)
    assert not output.exists()


def test_package_internal_hash_rejected_even_with_correct_outer_backup_hashes(recovery_set):
    database, store, output, items = recovery_set
    create_backup(database, store, output)
    target = "product_center_data/" + next(entry for entry in items if entry.startswith("packages/"))
    def replace(entries):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as package:
            package.writestr("manifest.json", '{"changed":"invalid identity"}')
        raw = stream.getvalue()
        entries[target] = raw
        meta = json.loads(entries["backup-manifest.json"])
        meta["files"][target] = {"sha256": digest(raw), "bytes": len(raw)}
        entries["backup-manifest.json"] = json.dumps(meta).encode()
    rewrite_archive(output, replace)
    with pytest.raises(ValueError, match="清单哈希"):
        verify_backup(output)


@pytest.mark.parametrize("raw", [b"corrupt zip", b"PK\x03\x04broken"])
def test_corrupt_stored_package_is_not_blessed_by_backup(recovery_set, raw):
    database, store, output, items = recovery_set
    entry = next(entry for entry in items if entry.startswith("packages/"))
    (store / entry).write_bytes(raw)
    with pytest.raises(ValueError, match="清单"):
        create_backup(database, store, output)
    assert not output.exists()


def test_archive_hash_corruption_is_rejected_before_restore(recovery_set, tmp_path):
    database, store, output, items = recovery_set
    create_backup(database, store, output)
    target = "product_center_data/" + next(entry for entry in items if entry.startswith("files/"))
    rewrite_archive(output, lambda entries: entries.__setitem__(target, b"corrupt archive bytes"))
    with pytest.raises(ValueError, match="哈希"):
        verify_backup(output)
    destination = tmp_path / "must-not-be-created"
    with pytest.raises(ValueError):
        restore_backup(output, destination)
    assert not destination.exists()


@pytest.mark.parametrize("name", ["../outside.txt", "/absolute.txt", "product_center_data/../../outside.txt", "product_center_data\\files\\unsafe.pdf"])
def test_archive_path_attack_rejected_before_writing(recovery_set, tmp_path, name):
    database, store, output, _ = recovery_set
    create_backup(database, store, output)
    rewrite_archive(output, lambda entries: entries.__setitem__(name, b"attack"))
    with pytest.raises(ValueError, match="非法"):
        verify_backup(output)
    destination = tmp_path / "safe-destination"
    with pytest.raises(ValueError):
        restore_backup(output, destination)
    assert not destination.exists()
    assert not (tmp_path / "outside.txt").exists()


def test_database_references_cannot_be_omitted_even_with_recomputed_backup_manifest(recovery_set):
    database, store, output, items = recovery_set
    create_backup(database, store, output)
    target = "product_center_data/" + next(entry for entry in items if entry.startswith("files/"))
    def remove(entries):
        del entries[target]
        meta = json.loads(entries["backup-manifest.json"])
        del meta["files"][target]
        entries["backup-manifest.json"] = json.dumps(meta).encode()
    rewrite_archive(output, remove)
    with pytest.raises(ValueError, match="引用"):
        verify_backup(output)


def test_archive_symlink_rejected(recovery_set):
    database, store, output, _ = recovery_set
    create_backup(database, store, output)
    raw = output.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            if name == "business_data.db":
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, data)
    with pytest.raises(ValueError, match="非法"):
        verify_backup(output)


def test_backup_verify_restore_never_load_database_archive_or_originals_whole(recovery_set, tmp_path, monkeypatch):
    database, store, output, items = recovery_set
    original_zip_read = zipfile.ZipFile.read
    def reject_path_read_bytes(_path):
        raise AssertionError("Recovery operations must stream files, not call Path.read_bytes")
    def manifest_only_zip_read(archive, name, *args, **kwargs):
        entry = name.filename if isinstance(name, zipfile.ZipInfo) else name
        assert entry in {"manifest.json", "backup-manifest.json"}, f"Eager ZIP read forbidden: {entry}"
        return original_zip_read(archive, name, *args, **kwargs)
    destination = tmp_path / "streamed-recovery"
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", reject_path_read_bytes)
        patch.setattr(zipfile.ZipFile, "read", manifest_only_zip_read)
        created = create_backup(database, store, output)
        assert verify_backup(output) == created
        assert restore_backup(output, destination) == created
    with sqlite3.connect(destination / "business_data.db") as conn:
        assert conn.execute("SELECT amount FROM business_records").fetchone()[0] == 123456
    for entry, raw in items.items():
        assert (destination / "product_center_data" / entry).read_bytes() == raw


def test_stream_copy_and_hash_use_fixed_size_reads():
    from product_center.backup import CHUNK_BYTES, _transfer

    raw = b"bounded-stream" * (CHUNK_BYTES // 4)
    class BoundedReader(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= CHUNK_BYTES
            return super().read(size)
    target = io.BytesIO()
    result = _transfer(BoundedReader(raw), target)
    assert target.getvalue() == raw
    assert result == {"sha256": digest(raw), "bytes": len(raw)}


def test_zip64_database_entry_can_cross_configured_large_file_threshold(recovery_set, tmp_path, monkeypatch):
    database, store, output, _ = recovery_set
    # Lower the ZIP64 threshold so a small real SQLite exercises >2/4GB handling.
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 1024)
    assert database.stat().st_size > zipfile.ZIP64_LIMIT
    report = create_backup(database, store, output)
    with zipfile.ZipFile(output) as archive:
        info = archive.getinfo("business_data.db")
        assert info.extract_version >= 45
        assert info.file_size > zipfile.ZIP64_LIMIT
    assert restore_backup(output, tmp_path / "zip64-recovery") == report


def add_three_historical_audit_orphans(database):
    conn = sqlite3.connect(database)
    try:
        conn.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES(1);
            CREATE TABLE operation_logs(id INTEGER PRIMARY KEY, user_id INTEGER,
                action TEXT, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL);
            INSERT INTO operation_logs VALUES(7,101,'historical_login');
            INSERT INTO operation_logs VALUES(8,102,'historical_import');
            INSERT INTO operation_logs VALUES(9,103,'historical_review');
            INSERT INTO operation_logs VALUES(10,1,'existing_user');
        """)
        conn.commit()
        return [list(row) for row in conn.execute('PRAGMA foreign_key_check')]
    finally:
        conn.close()


def test_historical_audit_orphans_are_rejected_by_default(recovery_set):
    database, store, output, _ = recovery_set
    assert len(add_three_historical_audit_orphans(database)) == 3
    with pytest.raises(ValueError, match='外键'):
        create_backup(database, store, output)
    assert not output.exists()


def test_explicit_exact_three_audit_orphans_are_preserved_verified_and_restored(recovery_set, tmp_path):
    database, store, output, _ = recovery_set
    baseline = add_three_historical_audit_orphans(database)
    report = create_backup(database, store, output, foreign_key_baseline=baseline)
    assert report['integrityCheck'] == 'ok'  # Page integrity, not a clean FK result.
    assert report['knownForeignKeyIssues'] == 3
    with zipfile.ZipFile(output) as archive:
        meta = json.loads(archive.read('backup-manifest.json'))
        assert meta['foreignKeyBaseline'] == sorted(baseline)
    assert verify_backup(output) == report
    destination = tmp_path / 'historical-recovery'
    assert restore_backup(output, destination) == report
    conn = sqlite3.connect(destination / 'business_data.db')
    try:
        assert [list(row) for row in conn.execute('PRAGMA foreign_key_check')] == baseline
        assert conn.execute('SELECT COUNT(*) FROM operation_logs').fetchone()[0] == 4
    finally:
        conn.close()


@pytest.mark.parametrize('change', ['missing', 'invented', 'duplicate', 'new_orphan'])
def test_foreign_key_baseline_must_match_every_actual_row_exactly(recovery_set, change):
    database, store, output, _ = recovery_set
    baseline = add_three_historical_audit_orphans(database)
    if change == 'missing':
        baseline.pop()
    elif change == 'invented':
        baseline.append(['operation_logs', 999, 'users', 0])
    elif change == 'duplicate':
        baseline.append(baseline[0])
    else:
        conn = sqlite3.connect(database)
        try:
            conn.execute("INSERT INTO operation_logs VALUES(11,104,'new_orphan')")
            conn.commit()
        finally:
            conn.close()
    with pytest.raises(ValueError, match='外键'):
        create_backup(database, store, output, foreign_key_baseline=baseline)
    assert not output.exists()


@pytest.mark.parametrize('issue', ['other_table', 'other_column', 'other_parent'])
def test_even_exact_baseline_cannot_waive_noneligible_foreign_keys(recovery_set, issue):
    database, store, output, _ = recovery_set
    conn = sqlite3.connect(database)
    try:
        if issue == 'other_table':
            conn.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY); CREATE TABLE other_logs(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id)); INSERT INTO other_logs VALUES(1,99);')
        elif issue == 'other_column':
            conn.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY); CREATE TABLE operation_logs(id INTEGER PRIMARY KEY,subject_user_id INTEGER REFERENCES users(id)); INSERT INTO operation_logs VALUES(1,99);')
        else:
            conn.executescript('CREATE TABLE groups(id INTEGER PRIMARY KEY); CREATE TABLE operation_logs(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES groups(id)); INSERT INTO operation_logs VALUES(1,99);')
        conn.commit()
        baseline = [list(row) for row in conn.execute('PRAGMA foreign_key_check')]
    finally:
        conn.close()
    with pytest.raises(ValueError, match='外键'):
        create_backup(database, store, output, foreign_key_baseline=baseline)
    assert not output.exists()


@pytest.mark.parametrize('change', ['remove', 'invent'])
def test_verify_and_restore_reject_missing_or_fabricated_recorded_baseline(recovery_set, tmp_path, change):
    database, store, output, _ = recovery_set
    baseline = add_three_historical_audit_orphans(database)
    create_backup(database, store, output, foreign_key_baseline=baseline)
    def mutate(entries):
        meta = json.loads(entries['backup-manifest.json'])
        if change == 'remove':
            del meta['foreignKeyBaseline']
        else:
            meta['foreignKeyBaseline'].append(['operation_logs',999,'users',0])
        entries['backup-manifest.json'] = json.dumps(meta).encode()
    rewrite_archive(output, mutate)
    with pytest.raises(ValueError, match='外键'):
        verify_backup(output)
    destination = tmp_path / 'must-not-restore'
    with pytest.raises(ValueError, match='外键'):
        restore_backup(output, destination)
    assert not destination.exists()
