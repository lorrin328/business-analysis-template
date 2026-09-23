"""Account approval and existing-account compatibility checks."""

import sqlite3

from fastapi.testclient import TestClient

from db import get_db, init_db
from main import app


def _admin_headers(client):
    response = client.post("/api/auth/login", json={
        "username": "admin", "password": "Test-only-admin-2026!",
    })
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["data"]["token"]}


def test_registration_requires_admin_activation_and_revokes_disabled_sessions(auth_db):
    client = TestClient(app)
    registered = client.post("/api/auth/register", json={
        "username": "awaiting_review", "password": "pending-pass-123",
        "role": "admin", "isActive": True,
    })
    assert registered.status_code == 200
    data = registered.json()["data"]
    user_id = data["user"]["id"]
    assert data["activationRequired"] is True
    assert data["user"]["accountStatus"] == "pending"
    assert data["user"]["role"] == "normal"
    assert "token" not in data
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM user_sessions WHERE user_id = ?", (user_id,)).fetchone()[0] == 0

    login = {"username": "awaiting_review", "password": "pending-pass-123"}
    assert client.post("/api/auth/login", json={**login, "password": "wrong-pass"}).status_code == 401
    pending_login = client.post("/api/auth/login", json=login)
    assert pending_login.status_code == 403
    assert "尚未激活" in pending_login.json()["detail"]
    assert client.get("/api/kpi?year=2026").status_code == 401

    admin_headers = _admin_headers(client)
    listed = client.get("/api/admin/users", headers=admin_headers).json()["data"]["users"]
    assert next(row for row in listed if row["id"] == user_id)["accountStatus"] == "pending"
    assert client.patch(f"/api/admin/users/{user_id}", json={"isActive": True}).status_code == 401
    configured = client.patch(f"/api/admin/users/{user_id}", headers=admin_headers,
                              json={"permissions": {"upload": True}})
    assert configured.status_code == 200
    assert configured.json()["data"]["accountStatus"] == "pending"
    assert client.post("/api/auth/login", json=login).status_code == 403

    activated = client.patch(f"/api/admin/users/{user_id}", headers=admin_headers,
                             json={"isActive": True})
    assert activated.status_code == 200
    assert activated.json()["data"]["accountStatus"] == "active"
    assert activated.json()["data"]["permissions"]["upload"] is True
    session = client.post("/api/auth/login", json=login).json()["data"]["token"]
    user_headers = {"Authorization": "Bearer " + session}
    assert client.get("/api/auth/me", headers=user_headers).status_code == 200
    assert client.patch(f"/api/admin/users/{user_id}", headers=user_headers,
                        json={"isActive": False}).status_code == 403

    disabled = client.patch(f"/api/admin/users/{user_id}", headers=admin_headers,
                            json={"isActive": False})
    assert disabled.status_code == 200
    assert disabled.json()["data"]["accountStatus"] == "disabled"
    assert client.get("/api/auth/me", headers=user_headers).status_code == 401
    assert client.post("/api/auth/login", json=login).status_code == 401
    assert client.patch(f"/api/admin/users/{user_id}", headers=admin_headers,
                        json={"isActive": True}).status_code == 200
    assert client.get("/api/auth/me", headers=user_headers).status_code == 401
    assert client.post("/api/auth/login", json=login).status_code == 200

    logs = client.get("/api/admin/operation-logs?limit=30", headers=admin_headers).json()["data"]["logs"]
    assert {"register", "account_activate", "account_disable"}.issubset({row["action"] for row in logs})


def test_existing_accounts_stay_active_after_repeated_schema_init(auth_db):
    client = TestClient(app)
    headers = _admin_headers(client)
    created = client.post("/api/admin/users", headers=headers, json={
        "username": "existing_user", "password": "existing-pass-123", "role": "normal",
    })
    assert created.status_code == 200
    assert created.json()["data"]["accountStatus"] == "active"
    init_db()
    assert client.post("/api/auth/login", json={
        "username": "existing_user", "password": "existing-pass-123",
    }).status_code == 200
    with get_db() as conn:
        migration = conn.execute("SELECT requires_aggregate_rebuild FROM schema_migrations WHERE version = ?",
                                 ("20260923_account_activation",)).fetchone()
        assert migration[0] == 0


def test_legacy_user_states_are_preserved_by_migration(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection

    db_path = tmp_path / "legacy_accounts.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'normal', is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_login_at TIMESTAMP
        )""")
        conn.executemany("INSERT INTO users (username, password_salt, password_hash, role, is_active) VALUES (?, '', '', ?, ?)", [
            ("legacy_admin", "admin", 1), ("legacy_disabled", "normal", 0),
        ])
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()
    init_db()
    with get_db() as conn:
        rows = conn.execute("SELECT username, is_active, activation_pending FROM users ORDER BY id").fetchall()
        assert [(r["username"], r["is_active"], r["activation_pending"]) for r in rows] == [
            ("legacy_admin", 1, 0), ("legacy_disabled", 0, 0),
        ]
