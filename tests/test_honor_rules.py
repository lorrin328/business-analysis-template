import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from honor.rules import diamond_delta, diamond_delta_units, is_longterm_policy, is_new_star, membership_level, monthly_result, premium_factor


def test_membership_thresholds():
    assert membership_level(2) == "未入会"
    assert membership_level(3) == "初级会员"
    assert membership_level(6) == "中级会员"
    assert membership_level(12) == "资深会员"
    assert membership_level(100) == "星曜会员"
    assert membership_level(100, employed=False) == "未入会"


def test_monthly_qualification_and_protection():
    assert monthly_result("OTO", 20000, 1) == (True, False)
    assert monthly_result("OTO", 19999, 1) == (False, False)
    assert monthly_result("证保", 30000, 1) == (True, False)
    assert monthly_result("证保", 10000, 1) == (False, True)
    assert monthly_result("蚁桥", 100000, 3) == (False, False)


def test_diamond_delta_never_negative_and_clears_when_inactive():
    assert diamond_delta(0, qualified=False, protected_month=False, employed=True) == (0, 0)
    assert diamond_delta(3, qualified=False, protected_month=False, employed=True) == (-1, 2)
    assert diamond_delta(3, qualified=False, protected_month=True, employed=True) == (0, 3)
    assert diamond_delta(3, qualified=True, protected_month=False, employed=True) == (1, 4)
    assert diamond_delta(3, qualified=True, protected_month=False, employed=False) == (-3, 0)
    assert diamond_delta_units(3, earned_units=2, protected_month=False, employed=True) == (2, 5)


def test_new_star_requires_entry_month():
    assert is_new_star(2026, 3, 2026, 5, 3) is True
    assert is_new_star(2026, 1, 2026, 4, 3) is True
    assert is_new_star(2026, 1, 2026, 5, 3) is False
    assert is_new_star(None, 3, 2026, 5, 3) is False


def test_honor_premium_factor_and_longterm_policy():
    assert premium_factor(1, "短期险") == 0
    assert premium_factor(1, "趸交") == 0.1
    assert premium_factor(3, "一年期以上") == 0.3
    assert premium_factor(6, "一年期以上") == 0.5
    assert premium_factor(10, "一年期以上") == 1
    assert is_longterm_policy("短期险", 10) is False
    assert is_longterm_policy("一年期以上", 1) is True
