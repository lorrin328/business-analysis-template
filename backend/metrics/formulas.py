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
    """安全除法。自动处理 0、None、NaN、Infinity。

    所有核心指标公式中的除法必须统一使用本函数。
    """
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
    """达成率 = 实绩 / 目标。

    不可计算规则：目标为空或为 0 时返回 None。
    """
    return round_metric(safe_divide(actual, target))


def yoy_rate(current: Any, previous: Any) -> float | None:
    """同比 = 本期 / 去年同期 - 1。

    去年同期定义：相对于当前统计日，上一年的同一日。
    例：当前截至 2026-05-21，则去年同期为 2025-01-01 至 2025-05-21 的累计数据。

    不可计算规则：去年同期为 0 或缺失时返回 None。
    """
    ratio = safe_divide(current, previous)
    return round_metric(ratio - 1) if ratio is not None else None


def mom_rate(current: Any, previous: Any) -> float | None:
    """环比 = 本期 / 上期 - 1。

    不可计算规则：上期为 0 或缺失时返回 None。
    """
    return yoy_rate(current, previous)


def time_progress(
    period_type: str,
    elapsed: int | float | None = None,
    total: int | float | None = None,
    *,
    as_of: date | None = None,
) -> float | None:
    """序时进度 = 已过时间 / 总周期。

    不可计算规则：周期参数缺失时返回 None。
    """
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
    """进度偏差 = 达成率 - 序时进度。

    不可计算规则：达成率或序时进度不可计算时返回 None。
    """
    rate = achievement_rate(actual, target)
    prog = _to_number(progress)
    return round_metric(rate - prog) if rate is not None and prog is not None else None


def activity_rate(active_headcount: Any, employed_headcount: Any) -> float | None:
    """活动率 = 活动人力 / 在职人力。

    不可计算规则：在职人力为 0 或缺失时返回 None。
    """
    return round_metric(safe_divide(active_headcount, employed_headcount))


def avg_premium(premium: Any, avg_headcount: Any) -> float | None:
    """人均保费 = 新单保费 / 月均在职人力。

    不可计算规则：月均在职人力为 0 或缺失时返回 None。单位：万元/人。
    """
    return round_metric(safe_divide(premium, avg_headcount))


def avg_productivity(premium: Any, avg_active_headcount: Any) -> float | None:
    """人均产能 = 新单保费 / 月均活动人力。

    不可计算规则：月均活动人力为 0 或缺失时返回 None。单位：万元/人。
    """
    return round_metric(safe_divide(premium, avg_active_headcount))


def conversion_rate(success_count: Any, base_count: Any) -> float | None:
    """转化率 = 成交数 / 触达或线索数。

    不可计算规则：基数为 0 或缺失时返回 None。
    """
    return round_metric(safe_divide(success_count, base_count))


def expense_rate(expense: Any, premium: Any) -> float | None:
    """费用率 = 费用 / 保费。

    不可计算规则：保费为 0 或缺失时返回 None。
    """
    return round_metric(safe_divide(expense, premium))


def roi(input_value: Any, output_value: Any) -> float | None:
    """投产比 = 产出 / 投入。

    不可计算规则：投入为 0 或缺失时返回 None。单位：倍。
    """
    return round_metric(safe_divide(output_value, input_value))


def metric_payload(code: str, value: float | None, unit: str, definition: str) -> dict:
    """构建统一指标载荷。"""
    return {
        "code": code,
        "value": value,
        "unit": unit,
        "definition": definition,
        "calculable": value is not None,
    }
