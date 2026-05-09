import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.data_transform import FIELD_MAPPINGS, map_record_fields, normalize_month
from config.orgs import ORG_LIST
from services.query_service import JINGDAI_LINE, build_month_daily_cumulative, get_platform_trend
from validators.data_validator import validate_rows
from validators.org_validator import org_scope_note


JINGDAI = JINGDAI_LINE
SHANGHAI = ORG_LIST[0]


def test_normalize_month():
    assert normalize_month("5") == 5
    assert normalize_month(5.0) == 5
    assert normalize_month("2026-05-01") == 5
    assert normalize_month("202605") == 5
    assert normalize_month("13") is None


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
