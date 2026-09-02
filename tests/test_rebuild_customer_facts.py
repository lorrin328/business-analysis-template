import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

import rebuild_customer_facts as command
from db import get_db
from db.schema import AGG_TABLES


def _seed():
    with get_db() as conn:
        conn.execute("DROP TABLE performance")
        conn.execute('CREATE TABLE performance("投保单号" TEXT,"业务模式" TEXT,"年月" TEXT,"期交保费" REAL,"投保人id" TEXT)')
        conn.execute("INSERT INTO performance VALUES ('SYNTHETIC-1','OTO','2026-08',10000,'SYNTHETIC-C')")
        batch = conn.execute("INSERT INTO history_import_batches(source_directory,status,source_cutoff) VALUES ('synthetic','success','2026-08-31')").lastrowid
        conn.execute("INSERT INTO customer_policy_snapshot(policy_no,customer_id,underwriting_time,policy_status,status_group,batch_id) VALUES ('SYNTHETIC-1','SYNTHETIC-C','2026-08-10','有效','active',?)", (batch,))
        conn.execute("INSERT INTO customer_master(customer_id,first_underwriting_time,first_policy_no,batch_id) VALUES ('SYNTHETIC-C','2026-08-10','SYNTHETIC-1',?)", (batch,))
        conn.execute("INSERT INTO agg_performance(year,month,channel,qj_premium,gm_premium,zs_premium) VALUES (2026,8,'OTO',987,654,321)")
        conn.commit()


def _aggregates():
    with get_db() as conn:
        return {table: [tuple(row) for row in conn.execute(f'SELECT * FROM "{table}"')] for table in AGG_TABLES}


def test_scoped_customer_rebuild_preserves_all_main_aggregates_and_raw(auth_db):
    _seed()
    before = _aggregates()
    with get_db() as conn:
        raw_before = [tuple(row) for row in conn.execute("SELECT * FROM performance")]
    result = command.rebuild_customer_facts()
    assert result["refreshedRows"] == 1
    assert result["skipped"] is False
    assert _aggregates() == before
    with get_db() as conn:
        assert [tuple(row) for row in conn.execute("SELECT * FROM performance")] == raw_before
        assert tuple(conn.execute("SELECT policy_no,qj_premium,customer_match FROM customer_policy_month_fact").fetchone()) == ("SYNTHETIC-1", 10000, 1)
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='ix_raw_performance_policy_key'").fetchone()
    assert command.rebuild_customer_facts()["refreshedRows"] == 1


def test_customer_rebuild_rolls_back_facts_and_indexes_on_error(auth_db, monkeypatch):
    _seed()
    command.rebuild_customer_facts()
    with get_db() as conn:
        conn.execute("UPDATE customer_policy_month_fact SET qj_premium=765")
        conn.commit()
    original_indexes = command.ensure_policy_key_indexes
    original_refresh = command.refresh_customer_facts
    def indexes(conn):
        original_indexes(conn)
        conn.execute("CREATE INDEX ix_synthetic_atomic_rebuild ON customer_policy_month_fact(qj_premium)")
    def fail(conn):
        original_refresh(conn)
        raise RuntimeError("synthetic failure after customer refresh")
    monkeypatch.setattr(command, "ensure_policy_key_indexes", indexes)
    monkeypatch.setattr(command, "refresh_customer_facts", fail)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        command.rebuild_customer_facts()
    with get_db() as conn:
        assert conn.execute("SELECT qj_premium FROM customer_policy_month_fact").fetchone()[0] == 765
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name='ix_synthetic_atomic_rebuild'").fetchone()


def test_missing_customer_prerequisites_fail_instead_of_skipping(auth_db):
    with pytest.raises(RuntimeError, match="prerequisites are missing"):
        command.rebuild_customer_facts()


def test_customer_rebuild_cli_has_real_nonzero_exit_on_failure(tmp_path):
    database = tmp_path / "synthetic.db"
    result = subprocess.run(
        [sys.executable, str(Path(command.__file__).resolve())],
        env={**os.environ, "BUSINESS_ANALYSIS_DB": str(database), "BUSINESS_ANALYSIS_LOCK": str(tmp_path / "synthetic.lock"), "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode != 0
    assert "prerequisites are missing" in result.stderr


def test_customer_rebuild_cli_emits_aggregate_summary_under_lock(auth_db, tmp_path, monkeypatch, capsys):
    _seed()
    monkeypatch.setenv("BUSINESS_ANALYSIS_LOCK", str(tmp_path / "synthetic.lock"))
    command.main()
    assert json.loads(capsys.readouterr().out)["refreshedRows"] == 1
