"""Synthetic regression coverage for account patches and target write validation."""
import copy
import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

import auth
import db
from main import app
from validators.target_validator import validate_target_payload


def _admin_headers(client):
    response = client.post("/api/auth/login", json={
        "username": "admin", "password": "Test-only-admin-2026!"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["data"]["token"]}


def _targets():
    metric = {"year": 100, "quarter": [25] * 4, "month": [8] * 12}
    return {"year": 2095, "categories": {
        key: {"metrics": {line: copy.deepcopy(metric) for line in
            ["整体", "经代", "转型业务", "OTO", "证保", "蚁桥"]}}
        for key in ["qjPremium", "value", "shangbao", "baozhang", "tenYear"]
    }, "orgTargets": {"辽宁|OTO": {"qjPremium": copy.deepcopy(metric)}}}


@pytest.mark.parametrize("patch", [
    {"password": "Updated-test-password-2026!"},
    {"username": "renamed_senior"},
    {"isActive": False},
    {"permissions": {"market_analysis": False}},
])
def test_partial_account_patch_preserves_custom_permissions(auth_db, patch):
    client = TestClient(app)
    headers = _admin_headers(client)
    user = client.post("/api/admin/users", headers=headers, json={
        "username": "limited_senior", "password": "User-test-password-2026!",
        "role": "senior", "permissions": {"upload": False, "excel_export": False}
    }).json()["data"]
    result = client.patch(f"/api/admin/users/{user['id']}", headers=headers, json=patch)
    assert result.status_code == 200
    permissions = result.json()["data"]["permissions"]
    assert permissions["upload"] is False
    assert permissions["excel_export"] is False
    assert permissions["kpi"] is True
    if "permissions" in patch:
        assert permissions["market_analysis"] is False


def test_authentication_is_reused_only_within_request(auth_db, monkeypatch):
    client = TestClient(app)
    headers = _admin_headers(client)
    original = auth.get_db
    lookups = []

    @contextmanager
    def tracked_db():
        lookups.append(True)
        with original() as conn:
            yield conn

    monkeypatch.setattr(auth, "get_db", tracked_db)
    assert client.get("/api/admin/users", headers=headers).status_code == 200
    assert len(lookups) == 1
    assert client.get("/api/admin/users", headers=headers).status_code == 200
    assert len(lookups) == 2
    assert client.get("/api/admin/users").status_code == 401
    auth.revoke_session(headers["Authorization"])
    assert client.get("/api/admin/users", headers=headers).status_code == 401


def test_cached_user_still_requires_module_permission(auth_db):
    client = TestClient(app)
    headers = _admin_headers(client)
    client.post("/api/admin/users", headers=headers, json={
        "username": "no_upload", "password": "User-test-password-2026!",
        "role": "senior", "permissions": {"upload": False}})
    login = client.post("/api/auth/login", json={
        "username": "no_upload", "password": "User-test-password-2026!"}).json()["data"]
    limited = {"Authorization": "Bearer " + login["token"]}
    assert client.post("/api/upload/preview", headers=limited).status_code == 403
    assert client.get("/api/admin/users", headers=limited).status_code == 403


def _inject_invalid(payload, location, value):
    metric = {"year": value, "quarter": [25] * 4, "month": [8] * 12}
    if location == "year":
        payload["year"] = value
    elif location == "required":
        payload["categories"]["qjPremium"]["metrics"]["整体"]["year"] = value
    elif location == "org":
        payload["orgTargets"]["辽宁|OTO"]["qjPremium"]["month"][0] = value
    elif location == "extra_category":
        payload["categories"]["extra"] = {"metrics": {"OTO": metric}}
    elif location == "extra_line":
        payload["categories"]["qjPremium"]["metrics"]["extra"] = metric
    elif location == "metadata":
        payload["additional"] = {"nested": [value]}


@pytest.mark.parametrize("location", ["required", "org", "extra_category", "extra_line", "year"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan"), "Infinity", "NaN", "1e999"])
def test_target_validator_rejects_nonfinite_in_all_consumed_fields(location, value):
    payload = _targets()
    _inject_invalid(payload, location, value)
    assert not validate_target_payload(payload).valid


@pytest.mark.parametrize("location", ["required", "org", "extra_category", "extra_line", "year", "metadata"])
def test_invalid_target_never_changes_either_table(auth_db, location):
    client = TestClient(app)
    headers = _admin_headers(client)
    good = _targets()
    assert client.post("/api/targets?year=2095", headers=headers, json=good).status_code == 200
    before_config = db.get_target_config(2095)
    before_rows = db.get_target_values(2095)
    bad = copy.deepcopy(good)
    _inject_invalid(bad, location, float("inf"))
    for method, url in [("post", "/api/targets?year=2095"), ("put", "/api/targets/2095")]:
        response = getattr(client, method)(url, headers={**headers, "Content-Type": "application/json"},
                                          content=json.dumps(bad))
        assert response.status_code == 400
        assert db.get_target_config(2095) == before_config
        assert db.get_target_values(2095) == before_rows
    with pytest.raises(ValueError):
        db.save_target_config(2095, bad)
    assert db.get_target_config(2095) == before_config
    assert db.get_target_values(2095) == before_rows


@pytest.mark.parametrize("bad", [-1, True, "invalid"])
def test_org_target_requires_finite_nonnegative_number(bad):
    payload = _targets()
    _inject_invalid(payload, "org", bad)
    assert not validate_target_payload(payload).valid


def test_finite_extra_targets_and_numeric_strings_remain_supported(auth_db):
    payload = _targets()
    _inject_invalid(payload, "extra_category", "123.5")
    _inject_invalid(payload, "extra_line", 0)
    assert validate_target_payload(payload).valid
    db.save_target_config(2095, payload)
    rows = db.get_target_values(2095)
    assert any(row["metric_code"] == "extra" and row["target_value"] == 123.5 for row in rows)
    assert any(row["org"] == "辽宁" for row in rows)


@pytest.mark.parametrize("location", ["required", "org", "extra_category", "extra_line"])
@pytest.mark.parametrize("value", [float("inf"), float("nan"), "Infinity", "invalid", -1, True])
def test_target_row_writer_validates_before_delete(auth_db, location, value):
    payload = _targets()
    db.save_target_config(2095, payload)
    before_config = db.get_target_config(2095)
    before_rows = db.get_target_values(2095)
    _inject_invalid(payload, location, value)
    with db.get_db() as conn:
        with pytest.raises(ValueError):
            db.save_target_values(conn, 2095, payload)
        # Even a caller that commits after handling the error must retain rows.
        conn.commit()
    assert db.get_target_config(2095) == before_config
    assert db.get_target_values(2095) == before_rows
