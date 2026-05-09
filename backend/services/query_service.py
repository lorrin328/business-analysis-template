from collections import defaultdict

from config.business_lines import BUSINESS_LINES
from database import get_platform_data
from services.data_transform import normalize_month


def _metric_col(metric: str) -> str:
    return {
        "qj": "qj_premium",
        "gm": "gm_premium",
        "zs": "zs_premium",
    }.get(metric, "qj_premium")


def _line_name(code: str) -> str:
    for item in BUSINESS_LINES:
        if item.get("code") == code:
            return item["name"]
    return code


JINGDAI_LINE = _line_name("jingdai")
DEFAULT_TREND_LINES = [
    item["name"]
    for item in BUSINESS_LINES
    if item.get("code") in {"jingdai", "oto", "zhengbao", "yiqiao"}
]


def _daily_contains_jingdai(rows: list[dict], month: int | None = None) -> bool:
    for row in rows:
        row_month = normalize_month(row.get("month"))
        if row.get("channel") == JINGDAI_LINE and (month is None or row_month == month):
            return True
    return False


def _period_index(month: int, period_type: str) -> int:
    if period_type == "quarter":
        return ((month - 1) // 3) + 1
    return month


def _period_labels(period_type: str) -> list[str]:
    if period_type == "quarter":
        return [f"Q{i}" for i in range(1, 5)]
    return [str(i) for i in range(1, 13)]


def build_period_cumulative(
    platform_data: dict,
    channels: list[str],
    metric: str = "qj",
    period_type: str = "year",
) -> dict:
    col = _metric_col(metric)
    max_period = 4 if period_type == "quarter" else 12
    period_amounts = defaultdict(float)
    raw_performance = platform_data.get("performance") or []
    jingdai_rows = platform_data.get("jingdai") or []
    performance_has_jingdai = _daily_contains_jingdai(raw_performance)

    for row in raw_performance:
        month = normalize_month(row.get("month"))
        if not month or row.get("channel") not in channels:
            continue
        period_amounts[_period_index(month, period_type)] += float(row.get(col) or 0)

    if JINGDAI_LINE in channels and not performance_has_jingdai:
        for row in jingdai_rows:
            month = normalize_month(row.get("month"))
            if not month:
                continue
            period_amounts[_period_index(month, period_type)] += float(row.get(col) or 0)

    values = []
    running = 0.0
    for idx in range(1, max_period + 1):
        running += period_amounts[idx]
        values.append(round(running, 2))

    has_data = any(value != 0 for value in values)
    return {
        "periodType": period_type,
        "labels": _period_labels(period_type),
        "values": values,
        "hasData": has_data,
        "message": "" if has_data else "No period trend data",
        "jingdaiDeduped": JINGDAI_LINE in channels and performance_has_jingdai,
    }


def build_month_daily_cumulative(
    platform_data: dict,
    year: int,
    month: int,
    channels: list[str],
    metric: str = "qj",
) -> dict:
    col = _metric_col(metric)
    month = int(month)
    daily = defaultdict(float)
    raw_daily = platform_data.get("daily_performance") or []
    jd_daily = platform_data.get("jingdai_daily") or []
    daily_has_jingdai = _daily_contains_jingdai(raw_daily, month)

    for row in raw_daily:
        if normalize_month(row.get("month")) == month and row.get("channel") in channels:
            daily[int(row.get("day") or 1)] += float(row.get(col) or 0)

    if JINGDAI_LINE in channels and not daily_has_jingdai:
        for row in jd_daily:
            if normalize_month(row.get("month")) == month:
                daily[int(row.get("day") or 1)] += float(row.get(col) or 0)

    labels, values = [], []
    running = 0.0
    for day in sorted(daily):
        running += daily[day]
        if running > 0:
            labels.append(f"{month}-{day}")
            values.append(round(running, 2))

    return {
        "labels": labels,
        "values": values,
        "hasRealDailyData": bool(values),
        "jingdaiDeduped": JINGDAI_LINE in channels and daily_has_jingdai,
        "message": "" if values else "No daily cumulative data",
    }


def get_platform_trend(
    year: int,
    month: int | None = None,
    channels: list[str] | None = None,
    metric: str = "qj",
    period_type: str = "year",
    period_value: int | None = None,
) -> dict:
    data = get_platform_data(year)
    channels = channels or DEFAULT_TREND_LINES
    period_type = period_type if period_type in {"year", "quarter", "month"} else "year"
    selected_month = month or (period_value if period_type == "month" else None)

    result = {
        "year": year,
        "periodType": period_type,
        "periodValue": selected_month or period_value or 0,
        "businessLines": channels,
        "trend": build_period_cumulative(data, channels, metric, "quarter" if period_type == "quarter" else "year"),
        "raw": data,
    }
    if period_type == "month" and selected_month:
        result["daily"] = build_month_daily_cumulative(data, year, selected_month, channels, metric)
    return result
