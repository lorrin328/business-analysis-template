import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from services.team_analysis_utils import (
    band_label,
    clean_staff_id,
    clean_text,
    normalize_line,
    percentile,
    performance_year_month,
    ratio,
    threshold_count,
)


def test_team_utils_normalize_common_source_values():
    assert clean_text(" nan ") == ""
    assert clean_staff_id("1001.0") == "1001"
    assert normalize_line("证券") == "证保"
    assert normalize_line("网服") == "蚁桥"


def test_team_utils_parse_performance_period_from_compact_or_date_text():
    assert performance_year_month({"年": None, "年月日": "2026-05-18"}) == (2026, 5)
    assert performance_year_month({"年": "2026", "年月": "202605"}) == (2026, 5)


def test_team_utils_distribution_helpers():
    values = [0.0, 1.0, 2.0, 4.0]
    assert percentile(values, 0.25) == 0.75
    assert percentile(values, 0.5) == 1.5
    assert threshold_count(values, 1.5) == 2
    assert ratio(2, 4) == 50
    assert ratio(1, 0) is None
    assert band_label(0) == "0及以下"
    assert band_label(0.5) == "0-0.5万"
    assert band_label(10.01) == "10万以上"
