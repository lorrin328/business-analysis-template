import base64
import json

from fastapi.testclient import TestClient

from db import get_db
from main import app
from services.ai_business_data import BUSINESS_DATASETS


def _headers(username="admin", password="Test-only-admin-2026!"):
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def test_business_catalog_covers_explicit_tables_and_excludes_credentials(auth_db):
    client = TestClient(app)
    assert client.get("/api/ai/business-datasets").status_code == 401
    result = client.get("/api/ai/business-datasets", headers=_headers())
    assert result.status_code == 200
    datasets = result.json()["data"]["datasets"]
    assert {entry["dataset"] for entry in datasets} == set(BUSINESS_DATASETS)
    assert "users" not in BUSINESS_DATASETS
    assert "user_sessions" not in BUSINESS_DATASETS
    assert "operation_logs" not in BUSINESS_DATASETS
    assert next(entry for entry in datasets if entry["dataset"] == "target_values")["available"]


def test_business_page_and_analysis_match_sqlite(auth_db):
    with get_db() as conn:
        conn.executemany(
            """INSERT INTO target_values
               (year,period_type,period_value,business_line,org,metric_code,target_value)
               VALUES (2026,'month',9,?,'上海','qjPremium',?)""",
            [("OTO", 100.0), ("OTO", 50.0), ("证保", 20.0)],
        )
        conn.commit()
    client = TestClient(app)
    headers = _headers()
    first = client.get("/api/ai/business-data/target_values", headers=headers,
                       params={"limit": 2})
    assert first.status_code == 200
    page = first.json()["data"]
    assert page["hasMore"] and len(page["rows"]) == 2
    second = client.get("/api/ai/business-data/target_values", headers=headers,
                        params={"afterRowId": page["nextAfterRowId"], "limit": 2})
    assert second.json()["data"]["rows"][0]["target_value"] == 20
    result = client.get("/api/ai/analyze/target_values", headers={**headers,
        "X-AI-Filters": json.dumps({"year": 2026, "target_value": {"gte": 20}})},
        params=[("groupBy", "business_line"), ("measure", "target_value"),
                ("aggregation", "sum")])
    assert result.status_code == 200
    assert result.json()["data"]["rows"] == [
        {"business_line": "OTO", "result": 150.0},
        {"business_line": "证保", "result": 20.0},
    ]
    context = client.get("/api/ai/project-context", headers=headers)
    assert context.status_code == 200
    assert "metrics" in context.json()["data"]


def test_business_access_needs_detail_and_module_permission(auth_db, monkeypatch):
    monkeypatch.setenv("AI_READONLY_TOKEN", "aggregate-only-test-token")
    client = TestClient(app)
    service = {"Authorization": "Bearer aggregate-only-test-token"}
    assert client.get("/api/ai/business-datasets", headers=service).status_code == 403
    assert client.get("/api/ai/analyze/target_values", headers=service).status_code == 403
    assert client.get("/api/ai/market-reports", headers=service).status_code == 403
    registered = client.post("/api/auth/register", json={"username": "analyst", "password": "test-pass-123"})
    user_id = registered.json()["data"]["user"]["id"]
    headers = _headers("analyst", "test-pass-123")
    assert client.get("/api/ai/business-data/target_values", headers=headers).status_code == 403
    with get_db() as conn:
        conn.execute("UPDATE user_module_permissions SET allowed=1 WHERE user_id=? AND module_key='ai_raw_data'", (user_id,))
        conn.commit()
    assert client.get("/api/ai/business-data/target_values", headers=headers).status_code == 403
    assert client.get("/api/ai/business-data/agg_performance", headers=headers).status_code == 200
    catalog = client.get("/api/ai/business-datasets", headers=headers).json()["data"]["datasets"]
    assert "target_values" not in {entry["dataset"] for entry in catalog}


def test_business_queries_reject_unknown_tables_columns_and_injection(auth_db):
    client = TestClient(app)
    headers = _headers()
    assert client.get("/api/ai/business-data/users", headers=headers).status_code == 404
    assert client.get("/api/ai/business-data/target_values", headers=headers,
                      params={"columns": "password_hash"}).status_code == 400
    assert client.get("/api/ai/analyze/target_values", headers=headers,
                      params={"groupBy": "year; DROP TABLE users"}).status_code == 400
    assert client.get("/api/ai/analyze/target_values", headers=headers,
                      params={"aggregation": "sum", "measure": "business_line"}).status_code == 400
    assert client.get("/api/ai/analyze/target_values", headers={**headers,
        "X-AI-Filters": json.dumps({"year": {"in": [2026, "' OR 1=1 --"]}})}).status_code == 200
    assert client.get("/api/ai/analyze/target_values", headers={**headers,
        "X-AI-Filters": '{"year":{"unknown":1}}'}).status_code == 400
    openapi = client.get("/api/ai/openapi.json").json()["paths"]
    assert "/api/ai/analyze/{dataset}" in openapi
    assert all(set(operations) == {"get"} for operations in openapi.values())
