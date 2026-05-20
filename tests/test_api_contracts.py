import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def test_product_analysis_forwards_filter_params(monkeypatch):
    from api import product as product_api

    captured = {}

    def fake_get_product_structure(year, dimension, transform_lines, jingdai_orgs, include_transform, include_jingdai, orgs, months, metric):
        captured.update(
            {
                "year": year,
                "dimension": dimension,
                "transform_lines": transform_lines,
                "jingdai_orgs": jingdai_orgs,
                "include_transform": include_transform,
                "include_jingdai": include_jingdai,
                "orgs": orgs,
                "months": months,
                "metric": metric,
            }
        )
        return {"premium": [], "count": []}

    monkeypatch.setattr(product_api, "get_product_structure", fake_get_product_structure)
    response = product_api.product_analysis(
        year=2026,
        dimension="product_mix",
        transformLines="OTO",
        jingdaiOrgs="A",
        includeTransform=True,
        includeJingdai=False,
        orgs="上海",
        months="4,5,6",
        metric="gm",
    )

    assert response["success"] is True
    assert captured == {
        "year": 2026,
        "dimension": "product_mix",
        "transform_lines": "OTO",
        "jingdai_orgs": "A",
        "include_transform": True,
        "include_jingdai": False,
        "orgs": "上海",
        "months": "4,5,6",
        "metric": "gm",
    }


def test_platform_data_route_returns_success_response(monkeypatch):
    from api import trend as trend_api

    monkeypatch.setattr(trend_api, "get_platform_data", lambda year: {"year": year, "performance": []})
    response = trend_api.platform_data(year=2026)

    assert response["success"] is True
    assert response["data"] == {"year": 2026, "performance": []}
    assert response["meta"]["metric"] == "platform-data"


def test_legacy_api_marks_deprecation_header():
    from fastapi import Response
    from api.legacy import mark_legacy_api

    response = Response()
    mark_legacy_api(response, "/api/kpi?year={year}")

    assert response.headers["X-API-Deprecated"] == "true"
    assert response.headers["X-API-Replacement"] == "/api/kpi?year={year}"


def test_js_static_mount_is_registered_when_assets_exist():
    from main import app

    assert any(getattr(route, "path", None) == "/js" for route in app.routes)
