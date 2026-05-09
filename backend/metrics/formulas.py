import math
from calendar import monthrange
from datetime import date
from typing import Any


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_divide(numerator: Any, denominator: Any, default: float | None = None) -> float | None:
    num = _to_number(numerator)
    den = _to_number(denominator)
    if num is None or den is None or den == 0:
        return default
    result = num / den
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def round_metric(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def achievement_rate(actual: Any, target: Any) -> float | None:
    return round_metric(safe_divide(actual, target))


def yoy_rate(current: Any, previous: Any) -> float | None:
    ratio = safe_divide(current, previous)
    return round_metric(ratio - 1) if ratio is not None else None


def mom_rate(current: Any, previous: Any) -> float | None:
    return yoy_rate(current, previous)


def time_progress(
    period_type: str,
    elapsed: int | float | None = None,
    total: int | float | None = None,
    *,
    as_of: date | None = None,
) -> float | None:
    if elapsed is not None or total is not None:
        return round_metric(safe_divide(elapsed, total))
    if period_type == "year":
        return None
    if period_type == "quarter":
        return None
    if period_type == "month" and as_of:
        return round_metric(safe_divide(as_of.day, monthrange(as_of.year, as_of.month)[1]))
    if period_type == "day" and as_of:
        return round_metric(safe_divide(as_of.timetuple().tm_yday, 366 if as_of.year % 4 == 0 else 365))
    return None


def progress_gap(actual: Any, target: Any, progress: Any) -> float | None:
    rate = achievement_rate(actual, target)
    prog = _to_number(progress)
    return round_metric(rate - prog) if rate is not None and prog is not None else None


def activity_rate(active_headcount: Any, employed_headcount: Any) -> float | None:
    return round_metric(safe_divide(active_headcount, employed_headcount))


def avg_premium(premium: Any, avg_headcount: Any) -> float | None:
    return round_metric(safe_divide(premium, avg_headcount))


def avg_productivity(premium: Any, avg_active_headcount: Any) -> float | None:
    return round_metric(safe_divide(premium, avg_active_headcount))


def conversion_rate(success_count: Any, base_count: Any) -> float | None:
    return round_metric(safe_divide(success_count, base_count))


def expense_rate(expense: Any, premium: Any) -> float | None:
    return round_metric(safe_divide(expense, premium))


def roi(input_value: Any, output_value: Any) -> float | None:
    return round_metric(safe_divide(output_value, input_value))


def metric_payload(code: str, value: float | None, unit: str, definition: str) -> dict:
    return {
        "code": code,
        "value": value,
        "unit": unit,
        "definition": definition,
        "calculable": value is not None,
    }
