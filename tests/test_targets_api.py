import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pytest

import db as database
import db.connection as db_connection
from services.response import error_response, success_response


def test_response_format():
    ok = success_response({"x": 1}, meta={"year": 2026})
    assert ok["success"] is True
    assert ok["data"] == {"x": 1}
    assert ok["meta"]["year"] == 2026

    err = error_response("错误", "E")
    assert err == {"success": False, "data": None, "message": "错误", "errorCode": "E"}


def test_target_save_and_read(tmp_path):
    old_database_path = database.DB_PATH
    old_connection_path = db_connection.DB_PATH
    temp_db_path = str(tmp_path / "business_data.db")
    database.DB_PATH = temp_db_path
    db_connection.DB_PATH = temp_db_path
    try:
        payload = {
            "year": 2098,
            "categories": {
                "qjPremium": {
                    "metrics": {
                        "经代": {"year": 100, "quarter": [10, 20, 30, 40], "month": [1] * 12}
                    }
                }
            },
        }
        database.save_target_config(2098, payload, updated_by="pytest")
        saved = database.get_target_config(2098)
        rows = database.get_target_values(2098)
        assert saved["year"] == 2098
        assert saved["updated_by"] == "pytest"
        assert any(r["period_type"] == "year" and r["target_value"] == 100 for r in rows)
    finally:
        database.DB_PATH = old_database_path
        db_connection.DB_PATH = old_connection_path


def test_admin_auth_allows_development_without_token(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from auth import require_admin

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("APP_ENV", "development")

    assert require_admin(None) is True


def test_admin_auth_blocks_production_without_token(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from auth import require_admin

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(fastapi.HTTPException) as exc:
        require_admin(None)

    assert exc.value.status_code == 503


def test_admin_auth_validates_configured_token(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from auth import require_admin

    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("APP_ENV", "production")

    assert require_admin("secret-token") is True
    with pytest.raises(fastapi.HTTPException) as exc:
        require_admin("bad-token")

    assert exc.value.status_code == 401


def test_init_db_creates_raw_detail_tables(tmp_path):
    old_database_path = database.DB_PATH
    old_connection_path = db_connection.DB_PATH
    temp_db_path = str(tmp_path / "business_data.db")
    database.DB_PATH = temp_db_path
    db_connection.DB_PATH = temp_db_path
    try:
        database.init_db()
        conn = sqlite3.connect(temp_db_path)
        try:
            perf_cols = {
                row[1] for row in conn.execute('PRAGMA table_info("performance")').fetchall()
            }
            jingdai_cols = {
                row[1] for row in conn.execute('PRAGMA table_info("jingdai")').fetchall()
            }
        finally:
            conn.close()

        assert {"年月", "业务模式", "期交保费"}.issubset(perf_cols)
        assert {"时间", "经代机构", "期交保费"}.issubset(jingdai_cols)
    finally:
        database.DB_PATH = old_database_path
        db_connection.DB_PATH = old_connection_path
