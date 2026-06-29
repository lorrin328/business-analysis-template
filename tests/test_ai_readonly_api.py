from fastapi.testclient import TestClient

from main import app


def test_ai_api_requires_configured_token(auth_db, monkeypatch):
    monkeypatch.delenv("AI_READONLY_TOKEN", raising=False)
    client = TestClient(app)
    resp = client.get("/api/ai/kpi?year=2026", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 503
    assert "AI_READONLY_TOKEN" in resp.json()["detail"]


def test_ai_api_rejects_wrong_token(auth_db, monkeypatch):
    monkeypatch.setenv("AI_READONLY_TOKEN", "readonly-secret")
    client = TestClient(app)
    assert client.get("/api/ai/kpi?year=2026").status_code == 401
    assert client.get("/api/ai/kpi?year=2026", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_ai_api_reads_kpi_snapshot_and_logs(auth_db, monkeypatch):
    monkeypatch.setenv("AI_READONLY_TOKEN", "readonly-secret")
    client = TestClient(app)
    headers = {"Authorization": "Bearer readonly-secret"}

    kpi = client.get("/api/ai/kpi?year=2026", headers=headers)
    assert kpi.status_code == 200
    assert kpi.json()["success"] is True
    assert kpi.json()["meta"]["access"] == "ai-readonly"

    snapshot = client.get("/api/ai/dashboard-snapshot?year=2026", headers=headers)
    assert snapshot.status_code == 200
    payload = snapshot.json()["data"]
    assert payload["version"] == "v1.0.97"
    assert "kpi" in payload
    assert "orgOverview" in payload
    assert "metricDefinitions" in payload

    admin = client.post("/api/auth/login", json={"username": "admin", "password": "Aaaaasynology8888%"}).json()["data"]
    logs = client.get(
        "/api/admin/operation-logs",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    actions = [row["action"] for row in logs.json()["data"]["logs"]]
    assert "ai_kpi_read" in actions
    assert "ai_dashboard_snapshot_read" in actions


def test_ai_openapi_is_public_and_contains_only_ai_paths(auth_db):
    client = TestClient(app)
    resp = client.get("/api/ai/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "AIReadonlyToken" in data["components"]["securitySchemes"]
    assert "/api/ai/dashboard-snapshot" in data["paths"]
    assert not any(path.startswith("/api/upload") for path in data["paths"])
