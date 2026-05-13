import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

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
