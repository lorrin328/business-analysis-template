"""测试 metrics/formulas.py 中未覆盖的公式函数。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pytest
from metrics.formulas import (
    safe_divide, achievement_rate, yoy_rate, mom_rate,
    progress_gap, activity_rate, avg_premium, avg_productivity,
)


class TestSafeDivide:
    def test_normal(self):
        assert safe_divide(10, 2) == 5.0

    def test_zero_denominator(self):
        assert safe_divide(10, 0) is None

    def test_none_numerator(self):
        assert safe_divide(None, 2) is None


class TestAchievementRate:
    def test_normal(self):
        assert achievement_rate(50, 100) == 0.5

    def test_zero_target(self):
        assert achievement_rate(50, 0) is None

    def test_none_actual(self):
        assert achievement_rate(None, 100) is None


class TestYoyRate:
    def test_growth(self):
        assert yoy_rate(120, 100) == 0.2

    def test_decline(self):
        assert yoy_rate(80, 100) == -0.2

    def test_zero_prev(self):
        assert yoy_rate(120, 0) is None

    def test_none(self):
        assert yoy_rate(None, 100) is None


class TestMomRate:
    def test_growth(self):
        assert mom_rate(120, 100) == 0.2

    def test_zero_prev(self):
        assert mom_rate(120, 0) is None

    def test_none(self):
        assert mom_rate(None, 100) is None


class TestProgressGap:
    def test_behind(self):
        gap = progress_gap(actual=30, target=100, progress=0.4)
        assert gap < 0

    def test_ahead(self):
        gap = progress_gap(actual=50, target=100, progress=0.4)
        assert gap > 0


class TestActivityRate:
    def test_normal(self):
        assert activity_rate(80, 100) == 0.8

    def test_zero_headcount(self):
        assert activity_rate(80, 0) is None

    def test_none(self):
        assert activity_rate(None, 100) is None


class TestAvgPremium:
    def test_normal(self):
        assert avg_premium(1000000, 50) == 20000.0

    def test_zero_people(self):
        assert avg_premium(1000000, 0) is None

    def test_none(self):
        assert avg_premium(None, 50) is None


class TestAvgProductivity:
    def test_normal(self):
        assert avg_productivity(1000000, 40) == 25000.0

    def test_zero_people(self):
        assert avg_productivity(1000000, 0) is None

    def test_none(self):
        assert avg_productivity(None, 40) is None
