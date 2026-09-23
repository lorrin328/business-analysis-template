import os
import sys

import pytest

os.environ.setdefault("AUTH_TEST_BYPASS", "1")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "Test-only-admin-2026!")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth_test.db"
    import db as db_module
    import db.connection as connection
    from db import init_db

    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setenv("AUTH_TEST_BYPASS", "0")
    monkeypatch.setenv("AUTH_ALLOW_PUBLIC_REGISTRATION", "1")
    init_db()
    yield
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")


@pytest.fixture()
def approved_user():
    """Exercise the real registration, administrator approval, and login path."""
    def create(client, username, password):
        registered = client.post("/api/auth/register", json={"username": username, "password": password})
        assert registered.status_code == 200
        user_id = registered.json()["data"]["user"]["id"]
        admin = client.post("/api/auth/login", json={
            "username": "admin", "password": "Test-only-admin-2026!",
        })
        assert admin.status_code == 200
        activated = client.patch(
            f"/api/admin/users/{user_id}",
            headers={"Authorization": "Bearer " + admin.json()["data"]["token"]},
            json={"isActive": True},
        )
        assert activated.status_code == 200
        login = client.post("/api/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200
        return login.json()["data"]

    return create
