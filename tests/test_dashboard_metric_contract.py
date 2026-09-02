from copy import deepcopy
import shutil
import subprocess
from pathlib import Path

import pytest

from metrics.dashboard import build_dashboard_metrics, ratio_metric
from services.excel_exporter import _kpi_rows, _targets_for_period, _org_rows, _team_rows


def sample():
    return {
        "year": 2026, "month": 6,
        "period": {"startDate": "2026-05-20", "endDate": "2026-06-10", "targetMode": "year"},
        "qj_premium": {"total": 100, "jingdai": 0, "total_transform": 100, "oto": 100},
        "value": {"OTO": 0, "经代": 0},
        "metric_sources": {"value": True, "value_jingdai": False, "performance": True},
        "hr": {"OTO": {"avg": 10, "active": 0, "avg_sum": 20, "months": 2}},
        "hr_prev": {"OTO": {"avg": 10, "active": 0}},
    }


def targets():
    return {"categories": {category: {"metrics": {scope: {"year": 1000, "month": [100] * 12}
            for scope in ("整体", "经代", "转型业务")}} for category in ("qjPremium", "value")},
            "orgTargets": {"上海|OTO": {"qjPremium": {"year": 1000, "month": [100] * 12}}}}


@pytest.mark.parametrize("numerator,denominator,expected", [(0, 10, 0), (None, 10, None), (1, None, None),
                                                            (1, 0, None), (1, -1, None), (float("nan"), 10, None)])
def test_ratio_distinguishes_zero_missing_and_invalid(numerator, denominator, expected):
    metric = ratio_metric("activity_rate", numerator, denominator)
    assert metric["value"] == expected
    assert metric["calculable"] == (expected is not None)
    assert bool(metric["reason"]) == (expected is None)


def test_hr_zero_and_zero_prior_activity_are_calculable_with_pp_change():
    data = sample()
    data["hr"]["OTO"]["active"] = 2
    cards = build_dashboard_metrics(data, targets())["cards"]
    assert cards["activity"]["value"] == .2
    assert cards["activity"]["yoy"]["value"] == 20
    assert cards["activity"]["yoy"]["unit"] == "pp"
    assert cards["percapita"]["value"] == 5
    assert cards["percapita"]["numerator"] == 50
    assert cards["percapita"]["denominator"] == 10
    assert cards["percapita"]["coveredMonths"] == 2


def test_detail_breakdown_shares_scope_formula_and_same_period_yoy():
    data = sample()
    data["qj_premium_prev"] = {"total_transform": 0, "oto": 0}
    data["hr_prev"]["OTO"].update(months=2, avg_sum=20)
    configured = targets()
    configured["categories"]["qjPremium"]["metrics"]["OTO"] = {"year": 200}
    cards = build_dashboard_metrics(data, configured)["cards"]
    assert cards["overall"]["OTO"]["value"] == .5
    assert cards["activity"]["byChannel"]["OTO"]["value"] == cards["activity"]["value"] == 0
    assert cards["percapita"]["byChannel"]["OTO"]["value"] == cards["percapita"]["value"] == 5
    assert cards["percapita"]["yoy"]["value"] == 5
    assert cards["percapita"]["byChannel"]["OTO"]["yoy"]["value"] == 5


@pytest.mark.parametrize("change", ["missing_latest", "zero", "partial", "missing_channel"])
def test_hr_incomplete_denominators_do_not_become_zero_or_inflate_percapita(change):
    data = sample()
    if change == "missing_latest":
        data["hr"]["OTO"].update(avg=None, active=None, months=1)
    elif change == "zero":
        data["hr"]["OTO"].update(avg=0, avg_sum=0)
    elif change == "partial":
        data["hr"]["OTO"]["months"] = 1
    else:
        data["qj_premium"]["zhengbao"] = 30
    cards = build_dashboard_metrics(data, targets())["cards"]
    assert cards["percapita"]["value"] is None
    assert cards["percapita"]["reason"]
    if change != "partial":
        assert cards["activity"]["value"] is None


def test_value_zero_remains_zero_but_missing_source_and_provisional_scope_are_explicit():
    data = sample()
    cards = build_dashboard_metrics(data, targets())["cards"]
    assert cards["value"]["transform"]["value"] == 0
    assert cards["value"]["overall"]["value"] == 0
    assert cards["value"]["overall"]["status"] == "provisional"
    assert cards["value"]["overall"]["warning"]
    data["metric_sources"]["value"] = False
    assert build_dashboard_metrics(data, targets())["cards"]["value"]["overall"]["value"] is None


def test_jingdai_payment_fallback_discloses_month_precision():
    data = sample()
    data["daily_cutoff"] = {"use_daily": True}
    data["metric_sources"]["tenyear_jingdai_precision"] = "month"
    card = build_dashboard_metrics(data, targets())["cards"]["10year"]
    assert card["overall"]["precision"] == "mixed"
    assert card["jingdai"]["precision"] == "month"
    assert card["transform"]["precision"] == "day"


@pytest.mark.parametrize("mode,expected_target,expected_rate", [("year", 1000, .1), ("month", 100, 1), ("none", None, None)])
def test_api_and_excel_use_same_period_targets(mode, expected_target, expected_rate):
    data = sample()
    data["period"]["targetMode"] = mode
    cards = build_dashboard_metrics(data, targets())["cards"]
    row = _kpi_rows(data, targets())[0]
    assert row[2:4] == [expected_target, expected_rate]
    assert row[3] == cards["overall"]["overall"]["value"]
    payload = targets()
    adapted = _targets_for_period(payload, data["period"])
    org = {"perf": {"上海|OTO": {"year": {"qj_premium": 100}}}}
    assert _org_rows(org, adapted)[0][2:5] == [expected_target, 100, expected_rate]
    assert payload == targets()


def test_excel_zero_activity_and_percapita_match_contract():
    data = sample()
    data["qj_premium"]["total_transform"] = 0
    rows = _kpi_rows(data, targets())
    assert rows[2][1] == 0
    assert rows[7][1] == 0
    data["hr"] = {}
    rows = _kpi_rows(data, targets())
    assert rows[2][1] is None
    assert rows[7][1] is None
    assert "缺少" in rows[7][4]


@pytest.mark.parametrize("source", ["performance", "performance_transform"])
def test_missing_premium_source_does_not_become_zero_percapita_with_complete_hr(source):
    data = sample()
    data["metric_sources"][source] = False
    data["qj_premium"].update(total=0, total_transform=0, oto=0)
    cards = build_dashboard_metrics(data, targets())["cards"]
    assert cards["percapita"]["value"] is None
    assert cards["percapita"]["numerator"] is None
    assert cards["percapita"]["byChannel"]["OTO"]["value"] is None
    assert "缺少实绩" in cards["percapita"]["reason"]


def test_team_export_distinguishes_missing_month_boundary_from_zero_activity():
    rows = _team_rows({"hr": [
        {"month": 1, "channel": "OTO", "start_headcount": 10, "end_headcount": None, "active_headcount": 0},
        {"month": 2, "channel": "OTO", "start_headcount": 10, "end_headcount": 10, "active_headcount": 0},
    ]})
    assert rows[0][4] is None
    assert rows[0][6] is None
    assert rows[1][6] == 0


def test_repository_marks_missing_latest_hr_and_value_source(tmp_path, monkeypatch):
    import db.connection as connection
    from db.schema import init_db
    from db.repositories.kpi import get_kpi_data
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "metrics.db"))
    init_db()
    with connection.get_db() as conn:
        conn.execute("INSERT INTO agg_hr_data(year, month, channel, start_headcount, end_headcount, active_headcount) VALUES (2026, 5, 'OTO', 10, 10, 0)")
        conn.execute("INSERT INTO agg_hr_data(year, month, channel, start_headcount, end_headcount, active_headcount) VALUES (2026, 6, '证保', 10, 10, 0)")
        conn.execute("INSERT INTO agg_performance(year, month, channel, qj_premium) VALUES (2026, 6, 'OTO', 100)")
        conn.execute("INSERT INTO agg_org_performance(year, month, org, channel, qj_premium, product_annuity) VALUES (2026, 6, '测试机构', 'OTO', 100, 20)")
        conn.execute("INSERT INTO agg_longterm_qj(year, month, business_type, channel, qj_premium) VALUES (2026, 6, '转型', 'OTO', 45)")
        conn.commit()
    result = get_kpi_data(2026, range_type="custom", start_date="2026-05-01", end_date="2026-06-30")
    assert result["hr"]["OTO"]["avg"] is None
    assert result["metrics"]["cards"]["activity"]["value"] is None
    assert result["metrics"]["cards"]["percapita"]["value"] is None
    assert result["metric_sources"]["value"] is False
    assert result["metrics"]["cards"]["longterm"]["OTO"]["numerator"] == 45
    assert result["metrics"]["cards"]["overall"]["OTO"]["numerator"] == 100
    assert result["metrics"]["cards"]["annuity"]["OTO"]["numerator"] == 20


def test_browser_metric_contract_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for browser behavior test")
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root / "tests" / "dashboard_metrics.test.cjs")], cwd=root, check=True, capture_output=True, text=True)
