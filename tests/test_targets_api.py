import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import db as database
import db.connection as db_connection
from main import app
from services.response import batch_meta, error_response, response_meta, success_response
from validators.target_validator import validate_target_payload


def _complete_target_payload(year=2026):
    metric = {"year": 100, "quarter": [25] * 4, "month": [100 / 12] * 12}
    lines = ["整体", "经代", "转型业务", "OTO", "证保", "蚁桥"]
    categories = {}
    for key in ["qjPremium", "value", "shangbao", "baozhang", "tenYear"]:
        categories[key] = {"metrics": {line: dict(metric) for line in lines}}
    return {"year": year, "categories": categories, "orgTargets": {}}


def test_response_format():
    ok = success_response({"x": 1}, meta={"year": 2026})
    assert ok["success"] is True
    assert ok["data"] == {"x": 1}
    assert ok["meta"]["year"] == 2026

    err = error_response("错误", "E")
    assert err == {"success": False, "data": None, "message": "错误", "errorCode": "E"}


def test_response_meta_builds_common_metric_contract():
    meta = response_meta(
        metric="team-analysis",
        unit="人/万元",
        data_source="agg_hr_data",
        definitions={"activity_rate": {"name": "活动率"}},
        year=2026,
    )

    assert meta == {
        "metric": "team-analysis",
        "unit": "人/万元",
        "dataSource": "agg_hr_data",
        "definitions": {"activity_rate": {"name": "活动率"}},
        "year": 2026,
    }


def test_batch_meta_builds_common_batch_contract():
    meta = batch_meta(
        batch_id=10,
        rule_version="2026-v1",
        data_source_mode="raw_detail",
        exceptionCount=2,
    )

    assert meta == {
        "batchId": 10,
        "ruleVersion": "2026-v1",
        "dataSourceMode": "raw_detail",
        "exceptionCount": 2,
    }


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


def test_target_validation_rejects_incomplete_or_malformed_payloads():
    assert validate_target_payload({"year": 2026, "categories": {}}).valid is False
    incomplete = _complete_target_payload()
    incomplete["categories"]["qjPremium"]["metrics"].pop("整体")
    assert validate_target_payload(incomplete).valid is False
    malformed = _complete_target_payload()
    malformed["categories"]["value"]["metrics"]["整体"]["month"] = [1, 2]
    assert validate_target_payload(malformed).valid is False
    assert validate_target_payload(_complete_target_payload()).valid is True


def test_target_api_uses_authenticated_username_and_rejects_year_mismatch(auth_db):
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Test-only-admin-2026!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    payload = _complete_target_payload(2096)

    saved = client.post("/api/targets?year=2096&updatedBy=spoofed-user", headers=headers, json=payload)
    mismatch = client.post("/api/targets?year=2097", headers=headers, json=payload)

    assert saved.status_code == 200
    assert saved.json()["data"]["updated_by"] == "admin"
    assert mismatch.status_code == 400

    legacy_saved = client.put("/api/targets/2096", headers=headers, json=payload)
    legacy_mismatch = client.put("/api/targets/2097", headers=headers, json=payload)
    assert legacy_saved.status_code == 200
    assert legacy_saved.json()["updated_by"] == "admin"
    assert legacy_mismatch.status_code == 400


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
