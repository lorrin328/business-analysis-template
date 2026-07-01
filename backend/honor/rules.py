"""Pure honor alliance rule functions."""
from __future__ import annotations

from .config import MEMBERSHIP_LEVELS, MONTHLY_RULES, PREMIUM_FACTORS, REWARD_RULES


def membership_level(diamond_balance: int | float | None, *, employed: bool = True) -> str:
    if not employed:
        return "未入会"
    balance = int(diamond_balance or 0)
    for level, threshold in MEMBERSHIP_LEVELS:
        if balance >= threshold:
            return level
    return "未入会"


def monthly_result(business_line: str, standard_premium: float, longterm_policy_count: int) -> tuple[bool, bool]:
    """Return (qualified, protected_month)."""
    rule = MONTHLY_RULES.get(business_line)
    if not rule:
        return False, False
    qualified = (
        float(standard_premium or 0) >= rule["premium_threshold"]
        and int(longterm_policy_count or 0) >= rule["longterm_count_threshold"]
    )
    protected = business_line == "证保" and not qualified and int(longterm_policy_count or 0) >= 1
    return qualified, protected


def diamond_delta(previous_balance: int, *, qualified: bool, protected_month: bool, employed: bool) -> tuple[int, int]:
    if not employed:
        return -int(previous_balance or 0), 0
    if qualified:
        return 1, int(previous_balance or 0) + 1
    if protected_month:
        return 0, int(previous_balance or 0)
    new_balance = max(0, int(previous_balance or 0) - 1)
    return new_balance - int(previous_balance or 0), new_balance


def diamond_delta_units(previous_balance: int, *, earned_units: int, protected_month: bool, employed: bool) -> tuple[int, int]:
    if not employed:
        return -int(previous_balance or 0), 0
    units = max(0, int(earned_units or 0))
    if units > 0:
        return units, int(previous_balance or 0) + units
    if protected_month:
        return 0, int(previous_balance or 0)
    new_balance = max(0, int(previous_balance or 0) - 1)
    return new_balance - int(previous_balance or 0), new_balance


def is_new_star(entry_year: int | None, entry_month: int | None, year: int, month: int, diamond_balance: int) -> bool:
    if not entry_year or not entry_month:
        return False
    months_since_entry = (int(year) - int(entry_year)) * 12 + (int(month) - int(entry_month))
    return int(entry_year) == int(year) and 0 <= months_since_entry <= 3 and int(diamond_balance or 0) >= 3


def premium_factor(payment_years: int | float | None, term_text: str | None = "") -> float:
    text = str(term_text or "").strip()
    if "短" in text:
        return PREMIUM_FACTORS["short"]
    if "趸" in text:
        return PREMIUM_FACTORS["single"]
    years = float(payment_years or 0)
    if years >= 10:
        return PREMIUM_FACTORS["ge_10"]
    if years >= 5:
        return PREMIUM_FACTORS["5_9"]
    if years >= 2:
        return PREMIUM_FACTORS["2_4"]
    if years > 0:
        return PREMIUM_FACTORS["single"]
    return PREMIUM_FACTORS["unknown"]


def is_longterm_policy(term_text: str | None, payment_years: int | float | None = None) -> bool:
    text = str(term_text or "").strip()
    if "短" in text:
        return False
    if "长" in text or "长期" in text or "一年期以上" in text:
        return True
    return premium_factor(payment_years, text) > 0


def reward_for_level(level: str) -> tuple[float, str]:
    for levels, amount, label in REWARD_RULES:
        if level in levels:
            return float(amount), label
    return 0.0, "未入会/已清零"
