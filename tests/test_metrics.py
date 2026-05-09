import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from datetime import date

from metrics.formulas import achievement_rate, safe_divide, time_progress, yoy_rate


def test_safe_divide_handles_zero_none_and_nan():
    assert safe_divide(10, 2) == 5
    assert safe_divide(10, 0) is None
    assert safe_divide(None, 2) is None
    assert safe_divide(math.nan, 2) is None


def test_achievement_rate():
    assert achievement_rate(50, 100) == 0.5
    assert achievement_rate(50, 0) is None


def test_yoy_rate():
    assert yoy_rate(120, 100) == 0.2
    assert yoy_rate(120, 0) is None


def test_time_progress_elapsed_total_mode():
    assert time_progress("year", elapsed=5, total=12) == 0.4167
    assert time_progress("quarter", elapsed=2, total=4) == 0.5
    assert time_progress("month", as_of=date(2026, 5, 15)) == 0.4839
    assert time_progress("year") is None
