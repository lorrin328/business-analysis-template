import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from fastapi.testclient import TestClient

from main import app


def _login(client, username="admin", password="Aaaaasynology8888%"):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_honor_api_requires_login(auth_db):
    client = TestClient(app)
    assert client.get("/api/honor/summary?year=2026").status_code == 401


def test_normal_user_can_view_but_not_recalculate(auth_db):
    client = TestClient(app)
    registered = client.post("/api/auth/register", json={"username": "honor_normal", "password": "normal-pass-123"})
    token = registered.json()["data"]["token"]
    assert client.get("/api/honor/summary?year=2026", headers=_headers(token)).status_code in {200, 404}
    assert client.post("/api/honor/recalculate", json={"year": 2026, "month": 5}, headers=_headers(token)).status_code == 403
    assert client.get("/api/honor/field-audit", headers=_headers(token)).status_code == 403


def test_admin_can_run_honor_field_audit(auth_db):
    client = TestClient(app)
    token = _login(client)["token"]
    resp = client.get("/api/honor/field-audit", headers=_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "rawTables" in data
    assert "ruleAssessment" in data


def test_honor_exceptions_include_staff_name(auth_db):
    from honor.repository import create_batch, replace_calculation_results

    client = TestClient(app)
    token = _login(client)["token"]
    batch_id = create_batch(year=2026, month=5, rule_version="2026-v1", created_by="pytest")
    replace_calculation_results(
        batch_id,
        {
            "org_summary": [],
            "person_summary": [
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "latest_month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "1001",
                    "staff_name": "张三",
                    "membership_level": "初级会员",
                }
            ],
            "person_month": [],
            "quarter_rewards": [],
            "exceptions": [
                {
                    "batch_id": batch_id,
                    "severity": "warning",
                    "exception_type": "negative_premium",
                    "org": "上海",
                    "staff_code": "1001",
                    "policy_no": "P001",
                    "message": "发现负数折算保费",
                }
            ],
            "source_staff_month": [],
            "source_policy": [],
        },
        1,
    )

    resp = client.get(f"/api/honor/exceptions?batchId={batch_id}", headers=_headers(token))
    assert resp.status_code == 200
    rows = resp.json()["data"]["rows"]
    assert rows[0]["staff_name"] == "张三"


def test_honor_summary_prefers_latest_calculation_batch_over_audit_only_batch(auth_db):
    from honor.repository import create_batch, latest_batch, replace_calculation_results

    result_batch = create_batch(year=2026, month=5, rule_version="2026-v1", created_by="pytest")
    replace_calculation_results(
        result_batch,
        {
            "org_summary": [],
            "person_summary": [
                {
                    "batch_id": result_batch,
                    "year": 2026,
                    "latest_month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "1001",
                    "staff_name": "张三",
                    "membership_level": "初级会员",
                }
            ],
            "person_month": [],
            "quarter_rewards": [],
            "exceptions": [],
            "source_staff_month": [],
            "source_policy": [],
        },
        0,
    )
    audit_only_batch = create_batch(year=2026, month=5, rule_version="2026-v1", created_by="pytest")

    assert audit_only_batch > result_batch
    assert latest_batch(2026, 5)["id"] == result_batch
