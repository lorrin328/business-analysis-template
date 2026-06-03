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


def test_honor_dashboard_returns_tracking_sections(auth_db):
    from honor.repository import create_batch, replace_calculation_results

    client = TestClient(app)
    token = _login(client)["token"]
    batch_id = create_batch(year=2026, month=5, rule_version="2026-v1", created_by="pytest")
    replace_calculation_results(
        batch_id,
        {
            "org_summary": [
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "tracked_headcount": 2,
                    "member_count": 1,
                    "member_rate": 0.5,
                    "monthly_gain_count": 1,
                    "monthly_deduct_count": 1,
                    "total_diamond": 3,
                }
            ],
            "person_summary": [
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "latest_month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "1001",
                    "staff_name": "张三",
                    "role_type": "个人",
                    "diamond_balance": 3,
                    "membership_level": "初级会员",
                    "total_gain": 3,
                    "total_deduct": 0,
                    "qualified_months": 3,
                },
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "latest_month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "2001",
                    "staff_name": "李四",
                    "role_type": "主管",
                    "diamond_balance": 0,
                    "membership_level": "未入会",
                    "total_gain": 1,
                    "total_deduct": 1,
                    "qualified_months": 1,
                },
            ],
            "person_month": [
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 4,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "2001",
                    "staff_name": "李四",
                    "role_type": "主管",
                    "is_employed_end_month": 1,
                    "diamond_delta": 1,
                    "diamond_balance": 1,
                    "membership_level": "初级会员",
                    "standard_premium": 20000,
                    "longterm_policy_count": 1,
                },
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "1001",
                    "staff_name": "张三",
                    "role_type": "个人",
                    "is_employed_end_month": 1,
                    "diamond_delta": 1,
                    "diamond_balance": 3,
                    "membership_level": "初级会员",
                    "standard_premium": 20000,
                    "longterm_policy_count": 1,
                },
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "2001",
                    "staff_name": "李四",
                    "role_type": "主管",
                    "is_employed_end_month": 1,
                    "diamond_delta": -1,
                    "diamond_balance": 0,
                    "membership_level": "未入会",
                    "standard_premium": 0,
                    "longterm_policy_count": 0,
                }
            ],
            "quarter_rewards": [],
            "exceptions": [],
            "source_staff_month": [
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "1001",
                    "staff_name": "张三",
                    "role_type": "个人",
                    "group_code": "G1",
                    "department_code": "D1",
                },
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "2001",
                    "staff_name": "李四",
                    "role_type": "主管",
                    "group_code": "G1",
                    "department_code": "D1",
                },
            ],
            "source_policy": [
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "1001",
                    "policy_no": "P001",
                    "qj_premium": 20000,
                    "standard_premium": 20000,
                },
                {
                    "batch_id": batch_id,
                    "year": 2026,
                    "month": 5,
                    "org": "上海",
                    "business_line": "OTO",
                    "staff_code": "2001",
                    "policy_no": "P002",
                    "qj_premium": 10000,
                    "standard_premium": 10000,
                },
            ],
        },
        0,
    )

    resp = client.get(f"/api/honor/dashboard?batchId={batch_id}", headers=_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["orgs"][0]["org"] == "上海"
    assert data["projects"][0]["dimension"] == "OTO"
    assert data["projectOrgs"][0]["org"] == "上海"
    assert data["orgMemberStructure"][0]["member_count"] == 1
    assert data["orgMemberStructure"][0]["specialist_member_count"] == 1
    assert data["orgMemberStructure"][0]["manager_member_count"] == 0
    assert data["specialists"][0]["dimension"] == "上海"
    assert data["managers"][0]["dimension"] == "主管"
    assert data["specialistHistory"][0]["staff_code"] == "1001"
    assert data["specialistHistory"][0]["qj_premium"] == 20000
    assert data["managerHistory"][0]["manager_code"] == "2001"
    assert data["managerHistory"][0]["star_manpower_count"] == 1
    assert data["managerHistory"][0]["team_qj_premium"] == 30000
    assert data["warnings"][0]["warning_type"] == "等级下降"
    assert data["warnings"][0]["previous_level"] == "初级会员"
    assert data["warnings"][0]["current_level"] == "未入会"
    assert data["warnings"][0]["standard_premium_gap"] == 20000
