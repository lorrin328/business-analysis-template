import base64

from fastapi.testclient import TestClient

from main import app


def _basic_headers(username: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def test_ai_api_accepts_account_password_without_configured_token(auth_db, monkeypatch):
    monkeypatch.delenv("AI_READONLY_TOKEN", raising=False)
    client = TestClient(app)
    resp = client.get(
        "/api/ai/kpi?year=2026",
        headers=_basic_headers("admin", "Test-only-admin-2026!"),
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["access"] == "ai-readonly"


def test_ai_api_rejects_wrong_token(auth_db, monkeypatch):
    monkeypatch.setenv("AI_READONLY_TOKEN", "readonly-secret")
    client = TestClient(app)
    assert client.get("/api/ai/kpi?year=2026").status_code == 401
    assert client.get("/api/ai/kpi?year=2026", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_ai_api_rejects_wrong_account_password(auth_db, monkeypatch):
    monkeypatch.delenv("AI_READONLY_TOKEN", raising=False)
    client = TestClient(app)
    resp = client.get("/api/ai/kpi?year=2026", headers=_basic_headers("admin", "wrong-password"))
    assert resp.status_code == 401
    assert "password" not in str(resp.json()).lower()


def test_ai_basic_auth_reuses_login_rate_limit(auth_db, monkeypatch):
    import api.auth_routes as auth_routes

    monkeypatch.delenv("AI_READONLY_TOKEN", raising=False)
    monkeypatch.setattr(auth_routes, "LOGIN_ATTEMPT_LIMIT", 2)
    monkeypatch.setattr(auth_routes, "LOGIN_LOCK_SECONDS", 60)
    auth_routes._login_attempts.clear()
    auth_routes._login_locks.clear()
    client = TestClient(app)
    try:
        first = client.get("/api/ai/kpi?year=2026", headers=_basic_headers("admin", "wrong-password"))
        blocked = client.get("/api/ai/kpi?year=2026", headers=_basic_headers("admin", "wrong-password"))
        still_blocked = client.get(
            "/api/ai/kpi?year=2026",
            headers=_basic_headers("admin", "Test-only-admin-2026!"),
        )
        assert first.status_code == 401
        assert blocked.status_code == 429
        assert still_blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) >= 1
    finally:
        auth_routes._login_attempts.clear()
        auth_routes._login_locks.clear()


def test_ai_api_accepts_existing_account_session(auth_db, monkeypatch):
    monkeypatch.delenv("AI_READONLY_TOKEN", raising=False)
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Test-only-admin-2026!"},
    ).json()["data"]
    resp = client.get(
        "/api/ai/kpi?year=2026",
        headers={"Authorization": f"Bearer {login['token']}"},
    )
    assert resp.status_code == 200


def test_ai_api_enforces_account_module_permission(auth_db, monkeypatch):
    from db import get_db

    monkeypatch.delenv("AI_READONLY_TOKEN", raising=False)
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"username": "ai_limited", "password": "normal-pass-123"},
    )
    user_id = registered.json()["data"]["user"]["id"]
    with get_db() as conn:
        conn.execute(
            "UPDATE user_module_permissions SET allowed = 0 WHERE user_id = ? AND module_key = 'org'",
            (user_id,),
        )
        conn.commit()

    headers = _basic_headers("ai_limited", "normal-pass-123")
    assert client.get("/api/ai/kpi?year=2026", headers=headers).status_code == 200
    assert client.get("/api/ai/org-summary?year=2026", headers=headers).status_code == 403
    assert client.get("/api/ai/dashboard-snapshot?year=2026", headers=headers).status_code == 403


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
    assert payload["version"] == "v1.0.142"
    assert "kpi" in payload
    assert "orgOverview" in payload
    assert "metricDefinitions" in payload

    admin = client.post("/api/auth/login", json={"username": "admin", "password": "Test-only-admin-2026!"}).json()["data"]
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
    assert "AIAccountBasic" in data["components"]["securitySchemes"]
    assert "AIReadonlyToken" in data["components"]["securitySchemes"]
    assert {"AIAccountBasic": []} in data["security"]
    assert "/api/ai/dashboard-snapshot" in data["paths"]
    assert not any(path.startswith("/api/upload") for path in data["paths"])
