"""测试 /api/config/business-lines 端点。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_business_lines_endpoint_returns_success():
    resp = client.get("/api/config/business-lines")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("success") is True
    assert "data" in payload


def test_business_lines_has_required_fields():
    resp = client.get("/api/config/business-lines")
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 4
    for item in data:
        assert "code" in item
        assert "name" in item
        assert "color" in item
        assert "supportOrgDimension" in item
        assert "supportTeamDimension" in item


def test_business_lines_includes_jingdai():
    resp = client.get("/api/config/business-lines")
    lines = resp.json()["data"]
    names = [l["name"] for l in lines]
    assert "经代" in names
    assert "OTO" in names
    assert "证保" in names
    assert "蚁桥" in names


def test_business_lines_jingdai_no_org_support():
    resp = client.get("/api/config/business-lines")
    jingdai = next(l for l in resp.json()["data"] if l["code"] == "jingdai")
    assert jingdai["supportOrgDimension"] is False


def test_metrics_endpoint_exposes_dashboard_kpi_registry():
    resp = client.get("/api/config/metrics")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["metrics"]["avg_premium"]["definition"] == "月均新单保费 / 月均在职人力"
    assert "dashboardKpiCards" in data
    assert any(
        card["code"] == "protection" and card["targetCategory"] == "baozhang"
        for card in data["dashboardKpiCards"]
    )
