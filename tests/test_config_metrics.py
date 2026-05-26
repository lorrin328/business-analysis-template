"""Tests for /api/config/metrics endpoint."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestConfigMetrics:
    def test_get_metrics_returns_all_definitions(self):
        resp = client.get("/api/config/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        metrics = data["data"]["metrics"]
        assert "achievement_rate" in metrics
        assert "activity_rate" in metrics
        assert "avg_premium" in metrics
        assert "avg_productivity" in metrics
        assert "yoy" in metrics
        assert "mom" in metrics
        assert "time_progress" in metrics
        assert "progress_gap" in metrics
        assert "conversion_rate" in metrics
        assert "expense_rate" in metrics
        assert "roi" in metrics

    def test_each_metric_has_required_fields(self):
        resp = client.get("/api/config/metrics")
        data = resp.json()
        metrics = data["data"]["metrics"]
        for key, metric in metrics.items():
            assert "name" in metric, f"{key} missing name"
            assert "unit" in metric, f"{key} missing unit"
            assert "definition" in metric, f"{key} missing definition"
            assert "uncalculable_rule" in metric, f"{key} missing uncalculable_rule"

    def test_display_constraints_present(self):
        resp = client.get("/api/config/metrics")
        data = resp.json()
        constraints = data["data"]["displayConstraints"]
        assert "activity_rate_yoy" in constraints
        assert constraints["activity_rate_yoy"]["unit"] == "pp"
        assert "incomplete_data" in constraints
        assert "target_fallback" in constraints

    def test_meta_includes_definitions(self):
        resp = client.get("/api/config/metrics")
        data = resp.json()
        assert "definitions" in data["meta"]
        assert "achievement_rate" in data["meta"]["definitions"]


class TestKpiDefinitions:
    def test_kpi_endpoint_includes_definitions(self):
        resp = client.get("/api/kpi?year=2026")
        assert resp.status_code == 200
        data = resp.json()
        assert "definitions" in data["meta"]
        assert "achievement_rate" in data["meta"]["definitions"]

    def test_kpi_definitions_endpoint(self):
        resp = client.get("/api/kpi-definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "achievement_rate" in data["data"]
        assert "activity_rate" in data["data"]


class TestOtherEndpointsIncludeDefinitions:
    def test_org_analysis_has_definitions(self):
        resp = client.get("/api/org-analysis?year=2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]

    def test_team_analysis_has_definitions(self):
        resp = client.get("/api/team-analysis?year=2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]

    def test_team_enhanced_analysis_has_definitions(self):
        resp = client.get("/api/team-enhanced-analysis?year=2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]
        assert resp.json()["meta"]["dataSource"] == "hr_data LEFT JOIN performance"

    def test_platform_data_has_definitions(self):
        resp = client.get("/api/platform-data?year=2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]

    def test_platform_trend_has_definitions(self):
        resp = client.get("/api/platform-trend?year=2026&periodType=year")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]

    def test_product_analysis_has_definitions(self):
        resp = client.get("/api/product-analysis?year=2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]

    def test_targets_has_definitions(self):
        resp = client.get("/api/targets?year=2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]

    def test_payment_period_has_definitions(self):
        resp = client.get("/api/payment-period/2026")
        assert resp.status_code == 200
        assert "definitions" in resp.json()["meta"]
