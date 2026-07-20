import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

pytest = __import__("pytest")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from main import app


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth_test.db"
    import db as db_module
    import db.connection as connection
    from db import init_db

    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setenv("AUTH_TEST_BYPASS", "0")
    init_db()
    yield
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")


def _login(client, username="admin", password="Test-only-admin-2026!"):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_default_admin_login_and_business_api_requires_login(auth_db):
    client = TestClient(app)
    assert client.get("/api/kpi?year=2026").status_code == 401

    data = _login(client)
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    assert all(data["user"]["permissions"].values())

    resp = client.get("/api/kpi?year=2026", headers=_auth_headers(data["token"]))
    assert resp.status_code == 200


def test_register_creates_normal_user_with_restricted_permissions(auth_db):
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"username": "normal_user", "password": "normal-pass-123"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    token = data["token"]
    user = data["user"]
    assert user["role"] == "normal"
    assert user["permissions"]["kpi"] is True
    assert user["permissions"]["team_enhanced"] is True
    assert user["permissions"]["upload"] is False
    assert user["permissions"]["product_config"] is False
    assert user["permissions"]["targets"] is False
    assert user["permissions"]["excel_export"] is False
    assert user["permissions"]["permission_admin"] is False
    assert user["permissions"]["personnel_management"] is False
    assert user["permissions"]["recalculate"] is True

    headers = _auth_headers(token)
    assert client.post("/api/upload", headers=headers).status_code == 403
    assert client.get("/api/product-config", headers=headers).status_code == 403
    assert client.get("/api/export/excel?year=2026", headers=headers).status_code == 403
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.get("/api/team-enhanced-analysis?year=2026", headers=headers).status_code == 200


def test_public_registration_can_be_disabled_in_production(auth_db, monkeypatch):
    client = TestClient(app)
    monkeypatch.delenv("AUTH_ALLOW_PUBLIC_REGISTRATION", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    config = client.get("/api/auth/config")
    assert config.status_code == 200
    assert config.json()["data"]["allowPublicRegistration"] is False

    resp = client.post("/api/auth/register", json={"username": "blocked_user", "password": "normal-pass-123"})
    assert resp.status_code == 403


def test_public_registration_can_be_explicitly_enabled_in_production(auth_db, monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_ALLOW_PUBLIC_REGISTRATION", "1")

    config = client.get("/api/auth/config")
    assert config.status_code == 200
    assert config.json()["data"]["allowPublicRegistration"] is True

    resp = client.post("/api/auth/register", json={"username": "enabled_user", "password": "normal-pass-123"})
    assert resp.status_code == 200
    user = resp.json()["data"]["user"]
    assert user["role"] == "normal"
    assert user["permissions"]["permission_admin"] is False
    assert user["permissions"]["upload"] is False


def test_username_rejects_event_attribute_payloads(auth_db):
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"username": "bad'user", "password": "normal-pass-123"})
    assert resp.status_code == 400

    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": 'bad"user', "password": "normal-pass-123", "role": "normal"},
    )
    assert created.status_code == 400


def test_admin_operation_logs_capture_login_register_and_permission_changes(auth_db):
    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])

    registered = client.post("/api/auth/register", json={"username": "log_user", "password": "normal-pass-123"})
    assert registered.status_code == 200
    user_id = registered.json()["data"]["user"]["id"]

    reset = client.patch(
        f"/api/admin/users/{user_id}",
        headers=admin_headers,
        json={"role": "normal", "password": "normal-pass-456", "permissions": {}},
    )
    assert reset.status_code == 200

    logs = client.get("/api/admin/operation-logs?limit=20", headers=admin_headers)
    assert logs.status_code == 200
    log_rows = logs.json()["data"]["logs"]
    actions = [row["action"] for row in log_rows]
    assert "login" in actions
    assert "register" in actions
    assert "password_reset" in actions
    assert "permission_admin" in actions
    assert all("created_at_utc" in row for row in log_rows)

    normal_token = registered.json()["data"]["token"]
    assert client.get("/api/auth/me", headers=_auth_headers(normal_token)).status_code == 401
    assert client.get("/api/admin/operation-logs", headers=_auth_headers(normal_token)).status_code == 401


def test_password_reset_revokes_existing_sessions(auth_db):
    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])
    registered = client.post("/api/auth/register", json={"username": "reset_user", "password": "normal-pass-123"})
    user = registered.json()["data"]

    reset = client.patch(
        f"/api/admin/users/{user['user']['id']}",
        headers=admin_headers,
        json={"password": "normal-pass-456"},
    )

    assert reset.status_code == 200
    assert client.get("/api/auth/me", headers=_auth_headers(user["token"])).status_code == 401


def test_login_rate_limit_blocks_repeated_failures(auth_db, monkeypatch):
    import api.auth_routes as auth_routes

    client = TestClient(app)
    monkeypatch.setattr(auth_routes, "LOGIN_ATTEMPT_LIMIT", 2)
    monkeypatch.setattr(auth_routes, "LOGIN_LOCK_SECONDS", 60)
    auth_routes._login_attempts.clear()
    auth_routes._login_locks.clear()
    try:
        first = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
        blocked = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
        still_blocked = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Test-only-admin-2026!"},
        )
        assert first.status_code == 401
        assert blocked.status_code == 429
        assert still_blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) >= 1
    finally:
        auth_routes._login_attempts.clear()
        auth_routes._login_locks.clear()


def test_legacy_read_routes_enforce_module_permissions(auth_db):
    from db import get_db

    client = TestClient(app)
    registered = client.post("/api/auth/register", json={"username": "legacy_user", "password": "normal-pass-123"})
    user = registered.json()["data"]
    with get_db() as conn:
        conn.execute(
            """
            UPDATE user_module_permissions
            SET allowed = 0
            WHERE user_id = ? AND module_key IN ('platform_trend', 'kpi', 'product_structure', 'org')
            """,
            (user["user"]["id"],),
        )
        conn.commit()
    headers = _auth_headers(user["token"])

    for path in ["/api/data/2026", "/api/kpi/2026", "/api/product/2026", "/api/org-kpi/2026"]:
        assert client.get(path, headers=headers).status_code == 403


def test_operation_logs_return_local_display_time(auth_db):
    from db import get_db

    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO operation_logs (username, action, status, detail, created_at)
            VALUES ('pytest', 'login', 'success', '{}', '2026-05-29 01:00:24')
            """
        )
        conn.commit()

    logs = client.get("/api/admin/operation-logs?limit=1", headers=admin_headers)
    assert logs.status_code == 200
    row = logs.json()["data"]["logs"][0]
    assert row["created_at"] == "2026-05-29 09:00:24"
    assert row["created_at_utc"] == "2026-05-29 01:00:24"


def test_admin_can_create_senior_and_update_permissions(auth_db):
    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])

    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "senior_user", "password": "senior-pass-123", "role": "senior"},
    )
    assert created.status_code == 200
    senior = created.json()["data"]
    assert senior["permissions"]["permission_admin"] is False
    assert senior["permissions"]["personnel_management"] is False
    assert senior["permissions"]["upload"] is True
    assert senior["permissions"]["team_enhanced"] is True
    assert senior["permissions"]["excel_export"] is True

    senior_login = _login(client, "senior_user", "senior-pass-123")
    senior_headers = _auth_headers(senior_login["token"])
    assert client.get("/api/admin/users", headers=senior_headers).status_code == 403
    assert client.get("/api/export/excel?year=2026", headers=senior_headers).status_code == 200

    changed = client.patch(
        f"/api/admin/users/{senior['id']}",
        headers=admin_headers,
        json={"role": "senior", "permissions": {"excel_export": False}},
    )
    assert changed.status_code == 200
    senior_login = _login(client, "senior_user", "senior-pass-123")
    assert client.get("/api/export/excel?year=2026", headers=_auth_headers(senior_login["token"])).status_code == 403


def test_admin_can_promote_and_demote_admin_group_safely(auth_db):
    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])

    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "manager_user", "password": "manager-pass-123", "role": "normal"},
    )
    assert created.status_code == 200
    manager = created.json()["data"]

    promoted = client.patch(
        f"/api/admin/users/{manager['id']}",
        headers=admin_headers,
        json={"role": "admin", "permissions": {}},
    )
    assert promoted.status_code == 200
    assert promoted.json()["data"]["role"] == "admin"
    assert all(promoted.json()["data"]["permissions"].values())

    manager_login = _login(client, "manager_user", "manager-pass-123")
    manager_headers = _auth_headers(manager_login["token"])
    assert client.get("/api/admin/users", headers=manager_headers).status_code == 200

    self_demote = client.patch(
        f"/api/admin/users/{manager['id']}",
        headers=manager_headers,
        json={"role": "normal", "permissions": {}},
    )
    assert self_demote.status_code == 400

    demoted = client.patch(
        f"/api/admin/users/{manager['id']}",
        headers=admin_headers,
        json={"role": "normal", "permissions": {"upload": True, "excel_export": True}},
    )
    assert demoted.status_code == 200
    demoted_user = demoted.json()["data"]
    assert demoted_user["role"] == "normal"
    assert demoted_user["permissions"]["upload"] is False
    assert demoted_user["permissions"]["excel_export"] is False
    assert demoted_user["permissions"]["team_enhanced"] is True
    manager_login = _login(client, "manager_user", "manager-pass-123")
    assert client.get("/api/admin/users", headers=_auth_headers(manager_login["token"])).status_code == 403


def test_last_active_admin_cannot_be_removed(auth_db):
    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])
    admin_id = admin["user"]["id"]

    self_demote = client.patch(
        f"/api/admin/users/{admin_id}",
        headers=admin_headers,
        json={"role": "normal", "permissions": {}},
    )
    assert self_demote.status_code == 400

    self_disable = client.patch(
        f"/api/admin/users/{admin_id}",
        headers=admin_headers,
        json={"role": "admin", "isActive": False},
    )
    assert self_disable.status_code == 400


def test_admin_can_delete_users_but_not_self_or_last_admin(auth_db):
    client = TestClient(app)
    admin = _login(client)
    admin_headers = _auth_headers(admin["token"])
    admin_id = admin["user"]["id"]

    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "delete_me", "password": "delete-pass-123", "role": "normal"},
    )
    assert created.status_code == 200
    user_id = created.json()["data"]["id"]

    delete_user = client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert delete_user.status_code == 200
    assert client.post("/api/auth/login", json={"username": "delete_me", "password": "delete-pass-123"}).status_code == 401

    self_delete = client.delete(f"/api/admin/users/{admin_id}", headers=admin_headers)
    assert self_delete.status_code == 400

    created_admin = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "temp_admin", "password": "admin-pass-123", "role": "admin"},
    )
    assert created_admin.status_code == 200
    temp_admin_id = created_admin.json()["data"]["id"]
    delete_other_admin = client.delete(f"/api/admin/users/{temp_admin_id}", headers=admin_headers)
    assert delete_other_admin.status_code == 200


def test_auth_test_bypass_is_disabled_in_production(monkeypatch):
    from auth import _test_bypass_enabled

    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    monkeypatch.setenv("APP_ENV", "production")
    assert _test_bypass_enabled() is False


def test_default_admin_password_must_come_from_environment(monkeypatch):
    import importlib
    import auth

    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)
    reloaded = importlib.reload(auth)
    try:
        assert reloaded.DEFAULT_ADMIN_PASSWORD == ""
    finally:
        monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "Test-only-admin-2026!")
        importlib.reload(auth)
