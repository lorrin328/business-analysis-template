"""Retired scheme pages and APIs stay unavailable, including for administrators."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from main import app


def test_retired_scheme_routes_are_unavailable_to_admin(auth_db):
    client = TestClient(app)
    login = client.post("/api/auth/login", json={
        "username": "admin", "password": "Test-only-admin-2026!",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    for path in (
        "/scheme-calculator", "/scheme-calculator.html", "/js/scheme-calculator.js",
        "/api/scheme/options", "/api/scheme/latest?schemeId=2026-org-dev-policy",
    ):
        assert client.get(path, headers=headers).status_code == 404, path
    assert client.post("/api/scheme/upload", headers=headers).status_code == 404


def test_retired_permissions_are_ignored_without_deleting_history(auth_db):
    from auth import MODULE_KEYS, get_user_permissions
    from db.connection import get_db

    assert "scheme_calculation" not in MODULE_KEYS
    assert "scheme_upload" not in MODULE_KEYS
    with get_db() as conn:
        user_id = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()[0]
        conn.execute(
            "INSERT INTO user_module_permissions (user_id, module_key, allowed) VALUES (?, ?, 1)",
            (user_id, "scheme_upload"),
        )
        assert "scheme_upload" not in get_user_permissions(conn, user_id, "normal")
        assert conn.execute(
            "SELECT allowed FROM user_module_permissions WHERE user_id = ? AND module_key = ?",
            (user_id, "scheme_upload"),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'scheme_import_batches'"
        ).fetchone()
