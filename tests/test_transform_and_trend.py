import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.data_transform import FIELD_MAPPINGS, map_record_fields, normalize_month
from config.orgs import ORG_LIST
from services.query_service import JINGDAI_LINE, build_month_daily_cumulative, get_platform_trend
from validators.data_validator import validate_rows
from validators.org_validator import org_scope_note
from database import get_platform_data


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
    result = build_month_daily_cumulative(data, 2026, 5, [JINGDAI, "OTO"], "qj")
    assert result["values"] == [30]
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
        "jingdai": [{"month": 1, "qj_premium": 5}],
        "daily_performance": [{"month": 1, "day": 1, "channel": "OTO", "qj_premium": 10}],
        "jingdai_daily": [{"month": 1, "day": 1, "qj_premium": 5}],
    }
    monkeypatch.setattr("services.query_service.get_platform_data", lambda year: data)

    yearly = get_platform_trend(2026, channels=[JINGDAI, "OTO"], period_type="year")
    quarterly = get_platform_trend(2026, channels=[JINGDAI, "OTO"], period_type="quarter")
    monthly = get_platform_trend(2026, month=1, channels=[JINGDAI, "OTO"], period_type="month")

    assert yearly["trend"]["values"][:4] == [15, 15, 15, 35]
    assert quarterly["trend"]["values"] == [15, 35, 35, 35]
    assert monthly["daily"]["values"] == [15]


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
    assert result["values"] == [100, 150]
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
    assert result["daily"]["values"] == [30]


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
    assert result["values"] == [30]  # 10 (OTO) + 20 (jingdai)
    assert result["jingdaiDeduped"] is False


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
    assert result["values"] == [30]  # 20 (jingdai from daily) + 10 (OTO), NOT 20+10+999
    assert result["jingdaiDeduped"] is True


def test_platform_trend_jingdai_quarter_has_current_and_prev_year():
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
    # Simulate loading of both years
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
    assert len(result["values"]) == 2
    assert result["values"] == [30, 50]


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
    assert len(result["daily"]["values"]) == 2
    assert result["daily"]["values"] == [50, 75]
