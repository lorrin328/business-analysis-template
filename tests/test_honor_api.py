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
