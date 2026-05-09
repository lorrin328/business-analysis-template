import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.data_transform import normalize_month
from services.query_service import build_month_daily_cumulative
from validators.org_validator import org_scope_note


def test_normalize_month():
    assert normalize_month("5") == 5
    assert normalize_month(5.0) == 5
    assert normalize_month("2026-05-01") == 5
    assert normalize_month("202605") == 5
    assert normalize_month("13") is None


def test_jingdai_daily_not_double_counted_when_daily_contains_jingdai():
    data = {
        "daily_performance": [
            {"month": "5", "day": 1, "channel": "经代", "qj_premium": 10},
            {"month": 5, "day": 1, "channel": "OTO", "qj_premium": 20},
        ],
        "jingdai_daily": [
            {"month": 5, "day": 1, "qj_premium": 999},
        ],
    }
    result = build_month_daily_cumulative(data, 2026, 5, ["经代", "OTO"], "qj")
    assert result["values"] == [30]
    assert result["jingdaiDeduped"] is True


def test_no_daily_data_does_not_generate_fake_curve():
    data = {"daily_performance": [], "jingdai_daily": []}
    result = build_month_daily_cumulative(data, 2026, 5, ["经代"], "qj")
    assert result["values"] == []
    assert result["hasRealDailyData"] is False
    assert result["message"] == "暂无日累计数据"


def test_jingdai_org_filter_note():
    assert org_scope_note(["经代"], ["上海"]) == "经代暂无机构维度，当前经代数据按整体口径展示。"
    assert org_scope_note(["OTO"], ["上海"]) == ""
