import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from backup_database import backup_database, write_metadata
from release_recovery import accept_release, capture_release, freeze_database, restore_release, update_release


def recovery_fixture(tmp_path):
    app, backups = tmp_path / "app", tmp_path / "backups"
    app.mkdir()
    backups.mkdir()
    (app / "backend" / "venv").mkdir(parents=True)
    (app / "backend" / "venv" / "dependency.txt").write_text("old dependencies")
    (app / "backend" / "logs").mkdir()
    (app / "backend" / "logs" / "app.log").write_text("keep runtime log")
    (app / "backend" / "main.py").write_text("old code")
    config = tmp_path / "service.conf"
    config.write_text("old service")
    database = tmp_path / "live.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE example(value INTEGER)")
        conn.execute("INSERT INTO example VALUES (1)")
    conn.close()
    release = backups / "release-20260902_010000-123"
    capture_release(app, release, database, "business-analysis", [str(config)])
    return app, backups, config, database, release


def test_failure_restores_code_dependencies_configuration_and_latest_frozen_commit(tmp_path):
    app, backups, config, database, release = recovery_fixture(tmp_path)
    online = backups / "business_data.db.20260902_010000-123"
    write_metadata(str(online) + ".meta", backup_database(database, online))
    # This new commit occurred after the online backup, before maintenance began.
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO example VALUES (2)")
    conn.close()
    frozen = backups / "business_data.db.20260902_010000-123.frozen"
    freeze_database(release, frozen)
    previous = app / "backend" / "venv.previous.20260902_010000-123"
    (app / "backend" / "venv").rename(previous)
    (app / "backend" / "venv").mkdir()
    (app / "backend" / "venv" / "dependency.txt").write_text("new dependencies")
    (app / "backend" / "main.py").write_text("new code")
    (app / "backend" / "introduced.py").write_text("new-only code")
    config.write_text("new service")
    update_release(release, state="mutating", previous_venv=str(previous))
    with sqlite3.connect(database) as conn:
        conn.execute("ALTER TABLE example ADD COLUMN new_schema TEXT")
        conn.execute("INSERT INTO example(value) VALUES (3)")
    conn.close()
    restore_release(release)
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT * FROM example ORDER BY value").fetchall() == [(1,), (2,)]
    assert (app / "backend" / "main.py").read_text() == "old code"
    assert not (app / "backend" / "introduced.py").exists()
    assert (app / "backend" / "venv" / "dependency.txt").read_text() == "old dependencies"
    assert config.read_text() == "old service"
    assert (app / "backend" / "logs" / "app.log").read_text() == "keep runtime log"
    assert online.exists() and frozen.exists()


def test_after_candidate_start_automatic_restore_changes_nothing(tmp_path):
    app, backups, config, database, release = recovery_fixture(tmp_path)
    freeze_database(release, backups / "business_data.db.20260902_010000-123.frozen")
    update_release(release, state="started")
    (app / "backend" / "main.py").write_text("running candidate")
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO example VALUES (99)")
    before = database.read_bytes()
    with pytest.raises(RuntimeError, match="automatic code/database rollback refused"):
        restore_release(release)
    assert database.read_bytes() == before
    assert (app / "backend" / "main.py").read_text() == "running candidate"


def test_acceptance_is_explicit_and_retains_current_recovery_package(tmp_path):
    app, backups, config, database, release = recovery_fixture(tmp_path)
    old = backups / "business_data.db.20260901_010000"
    write_metadata(str(old) + ".meta", backup_database(database, old))
    frozen = backups / "business_data.db.20260902_010000-123.frozen"
    freeze_database(release, frozen)
    with pytest.raises(RuntimeError, match="healthy reviewed"):
        accept_release(release)
    assert old.exists()
    update_release(release, state="healthy")
    result = accept_release(release)
    assert result["state"] == "accepted"
    assert not old.exists()
    assert frozen.exists() and (release / "code" / "backend" / "main.py").exists()


def test_restore_rejects_corrupt_frozen_backup_before_changing_code(tmp_path):
    app, backups, config, database, release = recovery_fixture(tmp_path)
    frozen = backups / "business_data.db.20260902_010000-123.frozen"
    freeze_database(release, frozen)
    frozen.write_bytes(b"corrupt")
    (app / "backend" / "main.py").write_text("new code")
    with pytest.raises(ValueError, match="size differs"):
        restore_release(release)
    assert (app / "backend" / "main.py").read_text() == "new code"


def test_deployment_orders_frozen_backup_before_mutation_and_never_auto_accepts():
    script = (Path(__file__).resolve().parents[1] / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    stop = script.index('systemctl stop "$SERVICE_NAME"')
    freeze = script.index('freeze --release-dir')
    mutate = script.index('rsync -a --delete')
    assert stop < freeze < mutate
    assert script.index('flock -n 8') < stop
    for command in ("rebuild_from_excels.py", "rebuild_aggregates_from_raw_tables.py", "rebuild_customer_facts.py"):
        assert f'BUSINESS_ANALYSIS_LOCK="$DEPLOY_REBUILD_LOCK" "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/{command}"' in script
    assert 'get("status") != "ok"' in script
    assert 'python3 "$RECOVERY_TOOL" accept-release' not in script


def test_corrupt_code_recovery_package_cannot_discard_last_backup(tmp_path):
    app, backups, config, database, release = recovery_fixture(tmp_path)
    old = backups / "business_data.db.20260901_010000"
    write_metadata(str(old) + ".meta", backup_database(database, old))
    freeze_database(release, backups / "business_data.db.20260902_010000-123.frozen")
    update_release(release, state="healthy")
    (release / "code" / "backend" / "main.py").write_text("corrupt recovery code")
    with pytest.raises(ValueError, match="checksum"):
        accept_release(release)
    assert old.exists()


def test_recovery_toolkit_is_self_contained_after_release_source_disappears(tmp_path):
    import subprocess
    app, backups, config, database, release = recovery_fixture(tmp_path)
    result = subprocess.run([sys.executable, str(release / "recovery-tools" / "release_recovery.py"), "--help"],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "accept-release" in result.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock must run on Linux CI/deployment validation")
def test_outer_maintenance_lock_blocks_external_writers_while_nested_rebuild_can_run(tmp_path):
    import fcntl
    import os
    import subprocess
    outer, inner = tmp_path / "database.import.lock", tmp_path / "deployment-operation.lock"
    snippet = ("from services.operation_lock import operation_lock\n"
               "with operation_lock('test-writer', timeout=0):\n    print('entered')\n")
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "backend"))
    with outer.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        rejected = subprocess.run([sys.executable, "-c", snippet], env=dict(environment, BUSINESS_ANALYSIS_LOCK=str(outer)),
                                  text=True, capture_output=True)
        assert rejected.returncode != 0 and "OperationLockError" in rejected.stderr
        allowed = subprocess.run([sys.executable, "-c", snippet], env=dict(environment, BUSINESS_ANALYSIS_LOCK=str(inner)),
                                 text=True, capture_output=True)
        assert allowed.returncode == 0 and "entered" in allowed.stdout
        still_rejected = subprocess.run([sys.executable, "-c", snippet], env=dict(environment, BUSINESS_ANALYSIS_LOCK=str(outer)),
                                        text=True, capture_output=True)
        assert still_rejected.returncode != 0
