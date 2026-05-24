import os
import sqlite3
import sys
from contextlib import contextmanager

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def test_health_check_reports_runtime_state(tmp_path, monkeypatch):
    from services import health_check

    db_path = tmp_path / "business_data.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE target_config (id INTEGER)")
        conn.execute("CREATE TABLE target_values (id INTEGER)")
        conn.execute("CREATE TABLE data_imports (id INTEGER)")
        conn.execute("CREATE TABLE agg_performance (year INTEGER, month INTEGER)")
        conn.execute("INSERT INTO agg_performance VALUES (2026, 5)")
        conn.commit()
    finally:
        conn.close()

    html_path = tmp_path / "经营分析模板.html"
    html_path.write_text("<span>v1.2.3</span>", encoding="utf-8")

    @contextmanager
    def temp_get_db():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    monkeypatch.setattr(health_check, "DB_PATH", str(db_path))
    monkeypatch.setattr(health_check, "HTML_PATH", html_path)
    monkeypatch.setattr(health_check, "REQUIRED_TABLES", ["target_config", "target_values", "data_imports", "agg_performance"])
    monkeypatch.setattr(health_check, "get_db", temp_get_db)

    result = health_check.run_health_check()

    assert result["status"] == "ok"
    assert result["checks"]["page_version"] == "v1.2.3"
    assert result["checks"]["database"]["latest_period"] == 202605
    assert result["checks"]["database"]["missing_tables"] == []


def test_operation_lock_rejects_concurrent_write(tmp_path, monkeypatch):
    from services.operation_lock import OperationLockError, operation_lock

    monkeypatch.setenv("BUSINESS_ANALYSIS_LOCK", str(tmp_path / "import.lock"))

    with operation_lock("first", timeout=0):
        with pytest.raises(OperationLockError):
            with operation_lock("second", timeout=0):
                pass
