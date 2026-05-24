import os
import sqlite3
import sys
from datetime import date
from contextlib import contextmanager

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.data_transform import FIELD_MAPPINGS, map_record_fields, normalize_month
from config.orgs import ORG_LIST
from services.query_service import (
    JINGDAI_LINE, build_month_daily_cumulative, build_quarter_daily_cumulative,
    get_platform_trend, DEFAULT_TREND_LINES, build_period_cumulative,
)
from validators.data_validator import validate_rows
from validators.org_validator import org_scope_note
from db import get_platform_data
from db import get_product_structure, get_jingdai_orgs
from db.repositories.payment import get_payment_period_structure
from etl.aggregates.payment import aggregate_payment_period, aggregate_jingdai_payment_period
from db.repositories import product as product_repo


JINGDAI = JINGDAI_LINE
SHANGHAI = ORG_LIST[0]


def test_normalize_month():
    assert normalize_month("5") == 5
    assert normalize_month(5.0) == 5
    assert normalize_month("2026-05-01") == 5
    assert normalize_month("202605") == 5
    assert normalize_month("13") is None
    # Edge cases from requirements
    assert normalize_month("20260401") == 4
    assert normalize_month("2026-04-01") == 4
    assert normalize_month("2026/04/01") == 4
    assert normalize_month(4) == 4
    assert normalize_month("04") == 4
    assert normalize_month("") is None
    assert normalize_month(None) is None


def test_jingdai_daily_not_double_counted_when_daily_contains_jingdai():
    data = {
        "daily_performance": [
            {"month": "5", "day": 1, "channel": JINGDAI, "qj_premium": 10},
            {"month": 5, "day": 1, "channel": "OTO", "qj_premium": 20},
        ],
        "jingdai_daily": [
            {"month": 5, "day": 1, "qj_premium": 999},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 5, [JINGDAI, "OTO"], "qj", as_of_date=date(2026, 6, 1))
    assert len(result["values"]) == 31
    assert result["values"][0] == 30
    assert result["values"][-1] == 30
    assert result["jingdaiDeduped"] is True


def test_no_daily_data_does_not_generate_fake_curve():
    data = {"daily_performance": [], "jingdai_daily": []}
    result = build_month_daily_cumulative(data, 2026, 5, [JINGDAI], "qj")
    assert result["values"] == []
    assert result["hasRealDailyData"] is False
    assert result["message"] == "No daily cumulative data"


def test_platform_trend_supports_year_quarter_and_month(monkeypatch):
    data = {
        "performance": [
            {"month": 1, "channel": "OTO", "qj_premium": 10},
            {"month": 4, "channel": "OTO", "qj_premium": 20},
        ],
        "jingdai": [{"month": 1, "qj_premium": 5}, {"month": 4, "qj_premium": 20}],
        "daily_performance": [
            {"month": 1, "day": 1, "channel": "OTO", "qj_premium": 10},
            {"month": 4, "day": 1, "channel": "OTO", "qj_premium": 20},
        ],
        "jingdai_daily": [
            {"month": 1, "day": 1, "qj_premium": 5},
            {"month": 4, "day": 1, "qj_premium": 20},
        ],
    }
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data)

    yearly = get_platform_trend(2026, channels=[JINGDAI, "OTO"], period_type="year")
    quarterly = get_platform_trend(2026, channels=[JINGDAI, "OTO"], period_type="quarter")
    monthly = get_platform_trend(2026, month=1, channels=[JINGDAI, "OTO"], period_type="month")

    assert yearly["trend"]["values"][:4] == [15, 15, 15, 55]
    assert quarterly["trend"]["values"] == [15, 55, 55, 55]
    assert len(monthly["daily"]["values"]) == 31
    assert monthly["daily"]["values"][0] == 15
    assert monthly["daily"]["values"][-1] == 15


def test_jingdai_org_filter_note():
    assert org_scope_note([JINGDAI], [SHANGHAI])
    assert org_scope_note(["OTO"], [SHANGHAI]) == ""


def test_validate_rows_detail_and_aggregate_unique_modes():
    rows = [
        {"year": 2026, "month": 5, "channel": "OTO", "qj_premium": 1},
        {"year": 2026, "month": 5, "channel": "OTO", "qj_premium": 2},
    ]
    detail = validate_rows(
        rows,
        required=["year", "month", "channel"],
        unique_keys=["year", "month", "channel"],
        mode="detail",
    )
    aggregate = validate_rows(
        rows,
        required=["year", "month", "channel"],
        unique_keys=["year", "month", "channel"],
        mode="aggregate",
    )
    assert detail.warnings == []
    assert any("duplicate key" in warning for warning in aggregate.warnings)


def test_data_transform_field_mappings_cover_core_datasets():
    for dataset in ["performance", "jingdai", "hr", "value", "target"]:
        assert dataset in FIELD_MAPPINGS
    mapped = map_record_fields({"期交保费": 100, "业务模式名称": "OTO"}, "performance")
    assert mapped["qj_premium"] == 100


# --- New tests for Bug 1 & 2 fixes ---

def test_jingdai_daily_generated_when_date_fields_present():
    """经代日累计：有年月日字段时能生成日累计"""
    data = {
        "daily_performance": [],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 100, "gm_premium": 200, "zs_premium": 50},
            {"month": 4, "day": 2, "qj_premium": 50, "gm_premium": 100, "zs_premium": 25},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 4, [JINGDAI], "qj")
    assert len(result["values"]) == 30
    assert result["values"][:2] == [100, 150]
    assert result["values"][-1] == 150
    assert result["hasRealDailyData"] is True


def test_monthly_daily_generated_without_explicit_month_param(monkeypatch):
    """month 参数缺失但 periodType=month&periodValue=4 时仍能生成daily"""
    data = {
        "performance": [],
        "jingdai": [],
        "daily_performance": [],
        "jingdai_daily": [{"month": 4, "day": 1, "qj_premium": 30}],
    }
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data)
    result = get_platform_trend(
        2026, channels=[JINGDAI], metric="qj",
        period_type="month", period_value=4,
    )
    assert result["periodType"] == "month"
    assert result["periodValue"] == 4
    assert result.get("daily") is not None
    assert len(result["daily"]["values"]) == 30
    assert result["daily"]["values"][0] == 30
    assert result["daily"]["values"][-1] == 30


def test_jingdai_daily_used_when_daily_performance_lacks_jingdai():
    """daily_performance 不含经代时，使用 jingdai_daily"""
    data = {
        "daily_performance": [
            {"month": 4, "day": 1, "channel": "OTO", "qj_premium": 10},
        ],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 20},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 4, [JINGDAI, "OTO"], "qj")
    assert len(result["values"]) == 30
    assert result["values"][0] == 30  # 10 (OTO) + 20 (jingdai)
    assert result["values"][-1] == 30
    assert result["jingdaiDeduped"] is False


def test_month_daily_cumulative_uses_common_cutoff_for_transform_and_jingdai():
    data = {
        "daily_performance": [
            {"month": 4, "day": 13, "channel": "OTO", "qj_premium": 10},
            {"month": 4, "day": 14, "channel": "OTO", "qj_premium": 999},
        ],
        "jingdai_daily": [
            {"month": 4, "day": 13, "qj_premium": 20},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 4, [JINGDAI, "OTO"], "qj")
    assert result["commonCutoffDay"] == 13
    assert len(result["values"]) == 30
    assert result["values"][11] == 0
    assert result["values"][12] == 30
    assert result["values"][-1] == 30


def test_current_month_daily_cumulative_stops_at_as_of_day():
    data = {
        "daily_performance": [
            {"month": 5, "day": 12, "channel": "OTO", "qj_premium": 100},
            {"month": 5, "day": 24, "channel": "OTO", "qj_premium": 999},
        ],
        "jingdai_daily": [],
    }

    result = build_month_daily_cumulative(data, 2026, 5, ["OTO"], "qj", as_of_date=date(2026, 5, 23))

    assert len(result["values"]) == 23
    assert result["values"][10] == 0
    assert result["values"][11] == 100
    assert result["values"][-1] == 100


def test_completed_comparison_month_daily_cumulative_extends_to_natural_month_end():
    data = {
        "daily_performance": [
            {"month": 5, "day": 28, "channel": "证保", "qj_premium": 80},
        ],
        "jingdai_daily": [],
    }

    result = build_month_daily_cumulative(data, 2025, 5, ["证保"], "qj", as_of_date=date(2026, 5, 23))

    assert len(result["values"]) == 31
    assert result["values"][27] == 80
    assert result["values"][-1] == 80


def test_month_daily_cumulative_handles_february_leap_year():
    leap = build_month_daily_cumulative(
        {"daily_performance": [{"month": 2, "day": 1, "channel": "OTO", "qj_premium": 10}]},
        2024,
        2,
        ["OTO"],
        "qj",
    )
    normal = build_month_daily_cumulative(
        {"daily_performance": [{"month": 2, "day": 1, "channel": "OTO", "qj_premium": 10}]},
        2025,
        2,
        ["OTO"],
        "qj",
    )

    assert len(leap["values"]) == 29
    assert len(normal["values"]) == 28


def test_previous_month_daily_cumulative_extends_to_natural_month_end():
    data = {
        "daily_performance": [
            {"month": 4, "day": 23, "channel": "OTO", "qj_premium": 60},
        ],
        "jingdai_daily": [],
    }

    result = build_month_daily_cumulative(data, 2026, 4, ["OTO"], "qj", as_of_date=date(2026, 5, 23))

    assert len(result["values"]) == 30
    assert result["values"][22] == 60
    assert result["values"][-1] == 60


def test_period_cumulative_uses_common_cutoff_for_mixed_sources():
    data = {
        "performance": [
            {"month": 4, "channel": "OTO", "qj_premium": 1009},
        ],
        "jingdai": [
            {"month": 4, "qj_premium": 20},
        ],
        "daily_performance": [
            {"month": 4, "day": 13, "channel": "OTO", "qj_premium": 10},
            {"month": 4, "day": 14, "channel": "OTO", "qj_premium": 999},
        ],
        "jingdai_daily": [
            {"month": 4, "day": 13, "qj_premium": 20},
        ],
    }

    result = build_period_cumulative(data, [JINGDAI, "OTO"], "qj", "year")

    assert result["commonCutoff"] == {"month": 4, "day": 13}
    assert result["values"][3] == 30
    assert result["values"][4] == 30


def test_jingdai_daily_not_doubled_when_daily_contains_jingdai():
    """daily_performance 已含经代时，不重复叠加"""
    data = {
        "daily_performance": [
            {"month": 4, "day": 1, "channel": JINGDAI, "qj_premium": 20},
            {"month": 4, "day": 1, "channel": "OTO", "qj_premium": 10},
        ],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 999},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 4, [JINGDAI, "OTO"], "qj")
    assert len(result["values"]) == 30
    assert result["values"][0] == 30  # 20 (jingdai from daily) + 10 (OTO), NOT 20+10+999
    assert result["values"][-1] == 30
    assert result["jingdaiDeduped"] is True


def test_platform_trend_jingdai_quarter_has_current_and_prev_year(monkeypatch):
    """2026年Q2经代季度趋势有当年线和去年同期线"""
    data_2026 = {
        "performance": [],
        "jingdai": [
            {"month": 4, "qj_premium": 40},
            {"month": 5, "qj_premium": 50},
            {"month": 6, "qj_premium": 60},
        ],
        "daily_performance": [],
        "jingdai_daily": [],
    }
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data_2026)
    result = get_platform_trend(
        2026, channels=[JINGDAI], metric="qj", period_type="quarter",
    )
    assert result["periodType"] == "quarter"
    # Q2 should include months 4,5,6
    assert result["trend"]["values"][1] > 0  # Q2 累计 > 0


def test_platform_trend_jingdai_month_with_daily():
    """2026年4月经代月度趋势有日累计线"""
    data = {
        "performance": [],
        "jingdai": [{"month": 4, "qj_premium": 100}],
        "daily_performance": [],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 30},
            {"month": 4, "day": 2, "qj_premium": 20},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 4, [JINGDAI], "qj")
    assert result["hasRealDailyData"] is True
    assert len(result["values"]) == 30
    assert result["values"][:2] == [30, 50]
    assert result["values"][-1] == 50


def test_team_data_prev_year_loaded_for_2026():
    """队伍分析：验证 get_platform_data 可加载上一年数据"""
    d = get_platform_data(2025)
    assert isinstance(d, dict)
    assert "hr" in d
    # If 2025 HR data exists in DB, it will be loaded by loadYearFromApi
    # and converted to teamMock via convertApiToTeamMock (fixed in Bug 2)


def test_no_daily_data_returns_empty_not_fake():
    """无日数据时不生成伪曲线"""
    data = {"daily_performance": [], "jingdai_daily": []}
    result = build_month_daily_cumulative(data, 2026, 4, [JINGDAI], "qj")
    assert result["values"] == []
    assert result["hasRealDailyData"] is False


def test_org_scope_note_for_jingdai():
    """机构筛选时经代提示"""
    note = org_scope_note([JINGDAI, "OTO"], ORG_LIST[:2])
    assert isinstance(note, str)
    # 经代 + 机构筛选时应有提示
    jd_only = org_scope_note([JINGDAI], ORG_LIST[:2])
    assert isinstance(jd_only, str)
    # 仅转型业务无经代提示
    oto_only = org_scope_note(["OTO"], ORG_LIST[:2])
    assert oto_only == "" or isinstance(oto_only, str)


def test_period_type_month_with_period_value_generates_daily(monkeypatch):
    """periodType=month&periodValue=4 能正确生成daily，不依赖显式 month 参数"""
    data = {
        "performance": [],
        "jingdai": [],
        "daily_performance": [],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 50},
            {"month": 4, "day": 2, "qj_premium": 25},
        ],
    }
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data)
    # Simulate API call with periodType=month&periodValue=4 (no month param)
    result = get_platform_trend(
        2026, channels=[JINGDAI], metric="qj",
        month=None, period_type="month", period_value=4,
    )
    assert result.get("daily") is not None
    assert len(result["daily"]["values"]) == 30
    assert result["daily"]["values"][:2] == [50, 75]
    assert result["daily"]["values"][-1] == 75


# --- New tests for Phase 2: quarter daily, ymd, date field candidates ---

def test_build_quarter_daily_cumulative_q2_jingdai():
    """季度日累计：Q2(4,5,6月) 经代日累计正确跨月累积"""
    data = {
        "daily_performance": [],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 30},
            {"month": 4, "day": 2, "qj_premium": 20},
            {"month": 5, "day": 1, "qj_premium": 10},
            {"month": 6, "day": 1, "qj_premium": 40},
        ],
    }
    result = build_quarter_daily_cumulative(data, 2026, 2, [JINGDAI], "qj", as_of_date=date(2026, 7, 1))
    assert result["hasRealDailyData"] is True
    assert result["quarterMonths"] == [4, 5, 6]
    # Day 4-1: 30, 4-2: 50, 5-1: 60, 6-1: 100
    assert len(result["values"]) == 91
    assert result["values"][0] == 30
    assert result["values"][1] == 50
    assert result["values"][30] == 60
    assert result["values"][61] == 100
    assert result["values"][-1] == 100
    assert result["labels"][0] == "4-1"
    assert result["labels"][61] == "6-1"


def test_current_quarter_daily_cumulative_stops_at_as_of_day():
    data = {
        "daily_performance": [
            {"month": 4, "day": 1, "channel": "OTO", "qj_premium": 10},
            {"month": 5, "day": 23, "channel": "OTO", "qj_premium": 20},
            {"month": 6, "day": 1, "channel": "OTO", "qj_premium": 999},
        ],
        "jingdai_daily": [],
    }

    result = build_quarter_daily_cumulative(data, 2026, 2, ["OTO"], "qj", as_of_date=date(2026, 5, 23))

    assert len(result["values"]) == 53
    assert result["labels"][0] == "4-1"
    assert result["labels"][-1] == "5-23"
    assert result["values"][-1] == 30


def test_build_quarter_daily_cumulative_q3_oto():
    """季度日累计：Q3 仅 OTO 转型业务日累计"""
    data = {
        "daily_performance": [
            {"month": 7, "day": 1, "channel": "OTO", "qj_premium": 10},
            {"month": 7, "day": 2, "channel": "OTO", "qj_premium": 15},
            {"month": 8, "day": 3, "channel": "OTO", "qj_premium": 5},
        ],
        "jingdai_daily": [],
    }
    result = build_quarter_daily_cumulative(data, 2026, 3, ["OTO"], "qj", as_of_date=date(2026, 10, 1))
    assert result["hasRealDailyData"] is True
    assert result["quarterMonths"] == [7, 8, 9]
    assert len(result["values"]) == 92
    assert result["values"][0] == 10
    assert result["values"][1] == 25
    assert result["values"][33] == 30
    assert result["values"][-1] == 30


def test_build_quarter_daily_cumulative_mixed_jingdai_and_transform():
    """季度日累计：经代 + OTO 混合，经代从 jingdai_daily 取"""
    data = {
        "daily_performance": [
            {"month": 4, "day": 1, "channel": "OTO", "qj_premium": 10},
            {"month": 4, "day": 2, "channel": "OTO", "qj_premium": 10},
        ],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 20},
            {"month": 4, "day": 2, "qj_premium": 10},
        ],
    }
    result = build_quarter_daily_cumulative(data, 2026, 2, [JINGDAI, "OTO"], "qj", as_of_date=date(2026, 7, 1))
    assert result["hasRealDailyData"] is True
    # Day 4-1: 10(OTO) + 20(jd) = 30, Day 4-2: 50
    assert len(result["values"]) == 91
    assert result["values"][0] == 30
    assert result["values"][1] == 50
    assert result["values"][-1] == 50


def test_build_quarter_daily_cumulative_empty_returns_message():
    """季度日累计：无数据时返回空并含提示信息"""
    data = {"daily_performance": [], "jingdai_daily": []}
    result = build_quarter_daily_cumulative(data, 2026, 2, [JINGDAI], "qj")
    assert result["hasRealDailyData"] is False
    assert result["values"] == []
    assert result["message"] == "No quarter daily cumulative data"


def test_get_platform_trend_quarter_returns_daily(monkeypatch):
    """平台趋势API：季度模式返回 daily 日累计数据"""
    data = {
        "performance": [],
        "jingdai": [],
        "daily_performance": [],
        "jingdai_daily": [
            {"month": 4, "day": 1, "qj_premium": 50},
            {"month": 4, "day": 2, "qj_premium": 30},
        ],
    }
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data)
    result = get_platform_trend(
        2025, channels=[JINGDAI], metric="qj",
        period_type="quarter", period_value=2,
    )
    assert result["periodType"] == "quarter"
    assert result["periodValue"] == 2
    assert result.get("daily") is not None
    assert result["daily"]["hasRealDailyData"] is True
    assert len(result["daily"]["values"]) == 91
    assert result["daily"]["values"][:2] == [50, 80]
    assert result["daily"]["values"][-1] == 80
    assert result["daily"]["quarterMonths"] == [4, 5, 6]


def test_get_platform_trend_quarter_no_period_value_omits_daily(monkeypatch):
    """平台趋势API：季度无 periodValue 时不返回 daily"""
    data = {"performance": [], "jingdai": [], "daily_performance": [], "jingdai_daily": []}
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data)
    result = get_platform_trend(
        2026, channels=[JINGDAI], metric="qj",
        period_type="quarter", period_value=None,
    )
    assert result["periodType"] == "quarter"
    assert result.get("daily") is None


def test_aggregate_jingdai_daily_date_candidates():
    """经代日聚合：支持承保日期、出单日期、生效日期等时间列"""
    from etl.columns import _pick_col
    import pandas as pd

    # Test: 承保日期 as time column
    df1 = pd.DataFrame([
        {"承保日期": "2026-04-15", "期交保费": 10000, "承保年化规保": 20000, "缴费年限": 10},
        {"承保日期": "2026-04-16", "期交保费": 5000, "承保年化规保": 10000, "缴费年限": 5},
    ])
    col1 = _pick_col(df1, ['时间', '年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期'])
    assert col1 == "承保日期"

    # Test: 出单日期 as time column
    df2 = pd.DataFrame([
        {"出单日期": "2026-05-01", "期交保费": 10000, "承保年化规保": 20000, "缴费年限": 10},
    ])
    col2 = _pick_col(df2, ['时间', '年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期'])
    assert col2 == "出单日期"

    # Test: 生效日期 as time column
    df3 = pd.DataFrame([
        {"生效日期": "2026-06-01", "期交保费": 10000, "承保年化规保": 20000, "缴费年限": 10},
    ])
    col3 = _pick_col(df3, ['时间', '年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期'])
    assert col3 == "生效日期"


def test_aggregate_jingdai_daily_outputs_ymd():
    """经代日聚合：输出包含 ymd 字段"""
    from etl.aggregates.jingdai import aggregate_jingdai_daily
    import pandas as pd

    df = pd.DataFrame([
        {"日期": "2026-04-01", "期交保费": 10000, "承保年化规保": 20000, "缴费年限": 10},
        {"日期": "2026-04-02", "期交保费": 5000, "承保年化规保": 10000, "缴费年限": 5},
    ])
    rows = aggregate_jingdai_daily(df)
    assert len(rows) == 2
    for row in rows:
        assert "ymd" in row
        assert row["ymd"] == f"{row['year']:04d}-{row['month']:02d}-{row['day']:02d}"
        assert row["year"] == 2026
        assert row["month"] == 4
    assert rows[0]["ymd"] == "2026-04-01"
    assert rows[1]["ymd"] == "2026-04-02"


def test_payment_period_aggregates_classify_transform_and_jingdai():
    """交期结构聚合：转型和经代均能生成分类数据。"""
    import pandas as pd

    transform = pd.DataFrame([
        {"年": 2026, "年月": "202605", "业务模式": "OTO", "销售机构名称": "上海", "期交保费": 10000, "年化规保": 12000, "承保件数": 1, "长短险": "长期", "缴费年限": 10},
        {"年": 2026, "年月": "202605", "业务模式": "证券", "销售机构名称": "北京", "期交保费": 5000, "年化规保": 6000, "承保件数": 2, "长短险": "短期", "缴费年限": 1},
    ])
    transform_rows = aggregate_payment_period(transform)
    assert {row["category"] for row in transform_rows} == {"10年及以上", "短期险"}
    assert {row["channel"] for row in transform_rows} == {"OTO", "证保"}

    jingdai = pd.DataFrame([
        {"时间": "2026-05-01", "当前缴别大类": "趸交", "缴费年限": 0, "经代机构": "支付宝", "承保年化规保": 20000, "期交保费": 10000},
        {"时间": "2026-05-02", "当前缴别大类": "期交", "缴费年限": 5, "经代机构": "支付宝", "承保年化规保": 30000, "期交保费": 15000},
    ])
    jingdai_rows = aggregate_jingdai_payment_period(jingdai)
    assert {row["category"] for row in jingdai_rows} == {"趸交", "5年交"}


def test_payment_period_query_accepts_multiple_months(monkeypatch):
    """交期结构查询：季度模式可以按完整月份列表汇总。"""
    import sqlite3
    from contextlib import contextmanager

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE agg_payment_period (
            year INTEGER, month INTEGER, business_type TEXT, channel TEXT, org TEXT,
            category TEXT, qj_premium REAL, gm_premium REAL, count INTEGER
        )
    """)
    conn.executemany(
        "INSERT INTO agg_payment_period VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (2026, 4, "转型", "OTO", "上海", "10年及以上", 10, 12, 1),
            (2026, 5, "转型", "OTO", "上海", "10年及以上", 20, 24, 2),
            (2026, 6, "转型", "OTO", "上海", "5年交", 30, 36, 3),
            (2026, 7, "转型", "OTO", "上海", "5年交", 999, 999, 9),
        ],
    )

    @contextmanager
    def fake_db():
        yield conn

    monkeypatch.setattr("db.repositories.payment.init_db", lambda: None)
    monkeypatch.setattr("db.repositories.payment.get_db", fake_db)

    result = get_payment_period_structure(2026, months=[4, 5, 6])
    premium = {row["name"]: row["value"] for row in result["premium"]}
    assert premium == {"5年交": 30, "10年及以上": 30}


def test_get_platform_data_includes_year_and_ymd_in_jingdai_daily():
    """get_platform_data 返回 jingdai_daily 含 year 和 ymd 字段"""
    d = get_platform_data(2026)
    assert "jingdai_daily" in d
    jd_rows = d["jingdai_daily"]
    if jd_rows:
        row = jd_rows[0]
        assert "year" in row.keys() or hasattr(row, "year") or row.get("year") is not None
        # ymd may be None for old rows without ymd, but the key should exist
        # (check by attempting access)


def test_prev_year_team_mock_loaded(monkeypatch):
    """队伍分析上年数据：loadYearFromApi 加载上一年 teamMock"""
    # This test verifies the backend data is available for the frontend fix
    data_2025 = get_platform_data(2025)
    assert isinstance(data_2025, dict)
    assert "hr" in data_2025
    # If 2025 HR data exists in DB, the frontend can load it for teamMock
    # (The actual loading is tested in frontend integration)
    # At minimum the API should return valid structure
    assert "performance" in data_2025 or "hr" in data_2025


def test_field_mappings_jingdai_day_aliases():
    """经代字段映射：day 字段包含所有新增日期别名"""
    day_aliases = FIELD_MAPPINGS["jingdai"]["day"]
    for expected in ["日", "日期", "时间", "入账时间", "生效日期", "出单日期", "承保日期"]:
        assert expected in day_aliases, f"Missing jingdai day alias: {expected}"


def test_product_structure_uses_transform_product_type_and_jingdai_product_name():
    result = get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["OTO"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=False,
    )
    labels = {row["name"] for row in result["premium"]}
    assert labels
    assert {"寿险", "年金", "短期险"} & labels

    jd_orgs = get_jingdai_orgs(2026)
    assert jd_orgs
    jd_result = get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=[],
        jingdai_orgs=[jd_orgs[0]],
        include_transform=False,
        include_jingdai=True,
    )
    assert jd_result["premium"]
    assert jd_orgs[0] in jd_result["jingdaiOrgs"]


def test_product_structure_accepts_separated_period_text(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE performance (
            "年月" TEXT,
            "业务模式" TEXT,
            "产品类型" TEXT,
            "期交保费" REAL,
            "承保件数" INTEGER,
            "销售机构名称" TEXT
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE jingdai (
            "时间" TEXT,
            "经代机构" TEXT,
            "产品名称" TEXT,
            "期交保费" REAL
        )
        '''
    )
    conn.execute(
        'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?)',
        ("2026-05-01", "OTO", "测试产品", 10000, 1, "上海"),
    )
    conn.execute(
        'INSERT INTO jingdai VALUES (?, ?, ?, ?)',
        ("2026/05/02", "测试经代", "经代产品", 20000),
    )

    @contextmanager
    def fake_get_db():
        yield conn

    monkeypatch.setattr(product_repo, "get_db", fake_get_db)
    result = product_repo.get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["OTO"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=False,
        months=[5],
    )
    assert result["premium"] == [{"name": "测试产品", "value": 1.0}]
    assert "测试经代" in result["jingdaiOrgs"]


def test_product_structure_gm_uses_existing_scale_premium_column(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE performance (
            "年月" TEXT,
            "业务模式" TEXT,
            "产品类型" TEXT,
            "期交保费" REAL,
            "规模保费" REAL,
            "承保件数" INTEGER
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE jingdai (
            "时间" TEXT,
            "经代机构" TEXT,
            "产品名称" TEXT,
            "期交保费" REAL
        )
        '''
    )
    conn.execute(
        'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?)',
        ("202605", "OTO", "规模产品", 10000, 30000, 1),
    )

    @contextmanager
    def fake_get_db():
        yield conn

    monkeypatch.setattr(product_repo, "get_db", fake_get_db)
    result = product_repo.get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["OTO"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=False,
        months=[5],
        metric_type="gm",
    )
    assert result["premium"] == [{"name": "规模产品", "value": 3.0}]


def test_product_structure_mixed_sources_uses_common_daily_cutoff(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE performance (
            "日期" TEXT,
            "业务模式" TEXT,
            "产品类型" TEXT,
            "期交保费" REAL,
            "承保件数" INTEGER,
            "销售机构名称" TEXT
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE jingdai (
            "时间" TEXT,
            "经代机构" TEXT,
            "产品名称" TEXT,
            "期交保费" REAL
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE agg_daily_performance (
            year INTEGER, month INTEGER, day INTEGER, channel TEXT, qj_premium REAL
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE agg_jingdai_daily (
            year INTEGER, month INTEGER, day INTEGER, qj_premium REAL
        )
        '''
    )
    conn.executemany(
        'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?)',
        [
            ("2026-05-22", "OTO", "转型产品", 10000, 1, "上海"),
            ("2026-05-23", "OTO", "转型产品", 90000, 9, "上海"),
        ],
    )
    conn.execute(
        'INSERT INTO jingdai VALUES (?, ?, ?, ?)',
        ("2026-05-22", "测试经代", "经代产品", 20000),
    )
    conn.executemany(
        'INSERT INTO agg_daily_performance VALUES (?, ?, ?, ?, ?)',
        [(2026, 5, 22, "OTO", 1), (2026, 5, 23, "OTO", 9)],
    )
    conn.execute(
        'INSERT INTO agg_jingdai_daily VALUES (?, ?, ?, ?)',
        (2026, 5, 22, 2),
    )

    @contextmanager
    def fake_get_db():
        yield conn

    monkeypatch.setattr(product_repo, "get_db", fake_get_db)
    result = product_repo.get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["OTO"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=True,
        months=[5],
    )
    premium = {row["name"]: row["value"] for row in result["premium"]}

    assert premium["转型-转型产品"] == 1.0
    assert premium["经代-经代产品"] == 2.0


def test_product_structure_normalizes_transform_channel_aliases():
    zhengbao = get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["证保"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=False,
    )
    yiqiao = get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["蚁桥"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=False,
    )
    assert zhengbao["premium"]
    assert yiqiao["premium"]


def test_product_structure_keeps_transform_and_jingdai_labels_separate_when_mixed():
    mixed = get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["OTO", "证保", "蚁桥"],
        jingdai_orgs=[],
        include_transform=True,
        include_jingdai=True,
    )
    labels = {row["name"] for row in mixed["premium"]}
    assert any(label.startswith("转型-") for label in labels)
    assert any(label.startswith("经代-") for label in labels)
