import os
import sys

import pandas as pd
import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def _source_frame():
    return pd.DataFrame([
        {
            "年": 2026, "年月": "2026-07", "年月日": "2026-07-10", "是否职拓": "是",
            "业务模式": "OTO", "销售机构名称": "四川", "人员工号": "001",
            "产品名称": "产品A", "产品类型": "寿险", "缴费年限": 5, "长短险": "长险",
            "期交保费": 100000, "年化规保": 100000, "承保件数": 1,
        },
        {
            "年": 2026, "年月": "2026-08", "年月日": "2026-08-12", "是否职拓": "是",
            "业务模式": "OTO", "销售机构名称": "四川", "人员工号": "001",
            "产品名称": "产品B", "产品类型": "重疾", "缴费年限": 10, "长短险": "长险",
            "期交保费": 50000, "年化规保": 50000, "承保件数": 1,
        },
        {
            "年": 2026, "年月": "2026-08", "年月日": "2026-08-15", "是否职拓": "是",
            "业务模式": "证券", "销售机构名称": "湖北", "人员工号": "002",
            "产品名称": "产品A", "产品类型": "寿险", "缴费年限": 5, "长短险": "长险",
            "期交保费": 30000, "年化规保": 30000, "承保件数": 1,
        },
        {
            "年": 2026, "年月": "2026-08", "年月日": "2026-08-16", "是否职拓": "否",
            "业务模式": "OTO", "销售机构名称": "四川", "人员工号": "003",
            "产品名称": "产品C", "产品类型": "寿险", "缴费年限": 5, "长短险": "长险",
            "期交保费": 900000, "年化规保": 900000, "承保件数": 1,
        },
    ])


def test_aggregate_zhituo_performance_uses_flag_and_keeps_dimensions():
    from etl import aggregate_zhituo_performance

    rows = aggregate_zhituo_performance(_source_frame())

    assert len(rows) == 3
    assert round(sum(row["qj_premium"] for row in rows), 2) == 18.0
    assert {row["channel"] for row in rows} == {"OTO", "证保"}
    assert {row["staff_id"] for row in rows} == {"1", "2"}
    assert {row["payment_period"] for row in rows} == {"5年交", "10年及以上"}


def test_aggregate_zhituo_performance_returns_empty_without_flag():
    from etl import aggregate_zhituo_performance

    assert aggregate_zhituo_performance(_source_frame().drop(columns=["是否职拓"])) == []


def test_zhituo_repository_filters_year_month_and_org(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db import init_db, replace_rows
    from db.repositories.zhituo import get_zhituo_analysis, get_zhituo_kpi
    from etl import aggregate_zhituo_performance

    db_path = tmp_path / "zhituo.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()
    with connection.get_db() as conn:
        replace_rows(conn, "agg_zhituo_performance", aggregate_zhituo_performance(_source_frame()))
        conn.commit()
        kpi = get_zhituo_kpi(conn, 2026, {"month": 8, "day": 1}, {"month": 8, "day": 31})

    assert kpi == {"qj_premium": 8.0, "gm_premium": 8.0, "policy_count": 2, "staff_count": 2}
    result = get_zhituo_analysis(years="2026", months="8", orgs="四川")
    assert result["summary"]["qjPremium"] == 5.0
    assert result["summary"]["staffCount"] == 1
    assert result["organizations"][0]["org"] == "四川"
    assert result["products"][0]["productName"] == "产品B"
    assert result["paymentPeriods"][0]["paymentPeriod"] == "10年及以上"


def test_incremental_refresh_clears_zhituo_when_covered_month_becomes_empty(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db import init_db, replace_rows
    from etl import aggregate_zhituo_performance
    from services.excel_pipeline import ExcelPipelineResult, replace_aggregate_rows

    db_path = tmp_path / "zhituo_incremental.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    original = _source_frame()
    corrected = original.copy()
    corrected.loc[:, "是否职拓"] = "否"
    with connection.get_db() as conn:
        replace_rows(conn, "agg_zhituo_performance", aggregate_zhituo_performance(original))
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM agg_zhituo_performance").fetchone()[0] == 3

        result = ExcelPipelineResult(
            rows_by_table={"agg_zhituo_performance": aggregate_zhituo_performance(corrected)},
            raw_tables={"performance": corrected},
        )
        counts = replace_aggregate_rows(conn, result, incremental=True)
        conn.commit()

        assert counts["agg_zhituo_performance"] == 0
        assert conn.execute("SELECT COUNT(*) FROM agg_zhituo_performance").fetchone()[0] == 0


def test_zhituo_api_wraps_repository_result(monkeypatch):
    pytest.importorskip("fastapi")
    from api import zhituo_analysis as api

    monkeypatch.setattr(api, "get_zhituo_analysis", lambda **kwargs: {"filters": kwargs})
    response = api.zhituo_overview(years="2026", months="7,8", orgs="四川,湖北")

    assert response["success"] is True
    assert response["data"]["filters"] == {"years": "2026", "months": "7,8", "orgs": "四川,湖北"}
    assert response["meta"]["metric"] == "zhituo-analysis"


def test_zhituo_api_requires_team_enhanced_permission(auth_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={"username": "kpi_only", "password": "normal-pass-123"},
    )
    assert registered.status_code == 200
    user_id = registered.json()["data"]["user"]["id"]
    user_token = registered.json()["data"]["token"]

    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Test-only-admin-2026!"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["data"]["token"]
    updated = client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "normal", "permissions": {"kpi": True, "team_enhanced": False}},
    )
    assert updated.status_code == 200

    response = client.get(
        "/api/zhituo-analysis/overview",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_zhituo_page_and_assets_are_registered():
    pytest.importorskip("fastapi")
    from main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/zhituo-analysis" in paths
    assert "/zhituo-analysis.html" in paths
    html = open(os.path.join(ROOT, "zhituo-analysis.html"), encoding="utf-8").read()
    script = open(os.path.join(ROOT, "js", "zhituo-analysis.js"), encoding="utf-8").read()
    dashboard = open(os.path.join(ROOT, "经营分析模板.html"), encoding="utf-8").read()
    nginx = open(os.path.join(ROOT, "deploy", "nginx.conf"), encoding="utf-8").read()
    assert "职拓业务分析" in html
    assert 'id="yearChecks"' in html and 'id="monthChecks"' in html and 'id="orgChecks"' in html
    assert "/api/zhituo-analysis/overview" in script
    assert 'data-permission="team_enhanced" data-dashboard-action="navigate"' in dashboard
    assert 'data-kpi-permission="team_enhanced"' in dashboard
    assert 'id="kpi-zhituo-premium"' in dashboard
    assert "can('team_enhanced')" in script
    assert "location = /zhituo-analysis {" in nginx
    assert "location = /zhituo-analysis.html {" in nginx
