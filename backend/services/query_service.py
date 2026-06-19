from collections import defaultdict
import calendar
from datetime import date

from config.business_lines import BUSINESS_LINES
from db import get_platform_data
from services.data_transform import normalize_month
from services.cutoff_policy import parse_as_of


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


def _max_daily_date(rows: list[dict], months: set[int] | None = None, channels: list[str] | None = None):
    dates = []
    for row in rows:
        month = normalize_month(row.get("month"))
        if not month or (months and month not in months):
            continue
        if channels is not None and row.get("channel") not in channels:
            continue
        day = int(row.get("day") or 1)
        dates.append((month, day))
    return max(dates) if dates else None


def _common_mixed_cutoff(
    platform_data: dict,
    channels: list[str],
    months: set[int] | None = None,
):
    """Return the shared source cutoff when transform and jingdai are both selected."""
    selected_transform_channels = [ch for ch in channels if ch != JINGDAI_LINE]
    if JINGDAI_LINE not in channels or not selected_transform_channels:
        return None

    raw_daily = platform_data.get("daily_performance") or []
    jd_daily = platform_data.get("jingdai_daily") or []
    transform_cutoff = _max_daily_date(raw_daily, months, selected_transform_channels)
    if _daily_contains_jingdai(raw_daily):
        jingdai_cutoff = _max_daily_date(raw_daily, months, [JINGDAI_LINE])
    else:
        jingdai_cutoff = _max_daily_date(jd_daily, months)
    if transform_cutoff and jingdai_cutoff:
        return min(transform_cutoff, jingdai_cutoff)
    return None


def _date_lte(month: int, day: int, cutoff: tuple[int, int]) -> bool:
    return (month, day) <= cutoff


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(int(year), int(month))[1]


def _display_days_in_month(year: int, month: int, as_of_date: date | None = None) -> int:
    """Current month trends stop at today; completed months show the full calendar month."""
    year = int(year)
    month = int(month)
    today = as_of_date or date.today()
    if year == today.year and month > today.month:
        return 0
    if year == today.year and month == today.month:
        return min(today.day, _days_in_month(year, month))
    return _days_in_month(year, month)


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
    raw_daily = platform_data.get("daily_performance") or []
    jd_daily = platform_data.get("jingdai_daily") or []
    performance_has_jingdai = _daily_contains_jingdai(raw_performance)
    common_cutoff = _common_mixed_cutoff(platform_data, channels, set(range(1, 13)))

    if common_cutoff:
        daily_has_jingdai = _daily_contains_jingdai(raw_daily)
        for row in raw_daily:
            month = normalize_month(row.get("month"))
            day = int(row.get("day") or 1)
            if not month or row.get("channel") not in channels or not _date_lte(month, day, common_cutoff):
                continue
            period_amounts[_period_index(month, period_type)] += float(row.get(col) or 0)
        if JINGDAI_LINE in channels and not daily_has_jingdai:
            for row in jd_daily:
                month = normalize_month(row.get("month"))
                day = int(row.get("day") or 1)
                if month and _date_lte(month, day, common_cutoff):
                    period_amounts[_period_index(month, period_type)] += float(row.get(col) or 0)
    else:
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
        "commonCutoff": {"month": common_cutoff[0], "day": common_cutoff[1]} if common_cutoff else None,
    }


def build_month_daily_cumulative(
    platform_data: dict,
    year: int,
    month: int,
    channels: list[str],
    metric: str = "qj",
    as_of_date: date | None = None,
) -> dict:
    col = _metric_col(metric)
    month = int(month)
    daily = defaultdict(float)
    raw_daily = platform_data.get("daily_performance") or []
    jd_daily = platform_data.get("jingdai_daily") or []
    daily_has_jingdai = _daily_contains_jingdai(raw_daily, month)

    common_cutoff = _common_mixed_cutoff(platform_data, channels, {month})
    common_cutoff_day = common_cutoff[1] if common_cutoff else None
    has_daily_rows = False

    for row in raw_daily:
        day = int(row.get("day") or 1)
        if normalize_month(row.get("month")) == month and row.get("channel") in channels:
            has_daily_rows = True
            if common_cutoff_day is None or day <= common_cutoff_day:
                daily[day] += float(row.get(col) or 0)

    if JINGDAI_LINE in channels and not daily_has_jingdai:
        for row in jd_daily:
            day = int(row.get("day") or 1)
            if normalize_month(row.get("month")) == month:
                has_daily_rows = True
                if common_cutoff_day is None or day <= common_cutoff_day:
                    daily[day] += float(row.get(col) or 0)

    if not has_daily_rows:
        return {
            "labels": [],
            "values": [],
            "hasRealDailyData": False,
            "jingdaiDeduped": JINGDAI_LINE in channels and daily_has_jingdai,
            "commonCutoffDay": common_cutoff_day,
            "message": "No daily cumulative data",
        }

    labels, values = [], []
    running = 0.0
    for day in range(1, _display_days_in_month(year, month, as_of_date) + 1):
        running += daily[day]
        labels.append(f"{month}-{day}")
        values.append(round(running, 2))

    return {
        "labels": labels,
        "values": values,
        "hasRealDailyData": True,
        "jingdaiDeduped": JINGDAI_LINE in channels and daily_has_jingdai,
        "commonCutoffDay": common_cutoff_day,
        "message": "",
    }


def build_quarter_daily_cumulative(
    platform_data: dict,
    year: int,
    quarter: int,
    channels: list[str],
    metric: str = "qj",
    as_of_date: date | None = None,
) -> dict:
    """Generate daily cumulative for a specific quarter (e.g. Q2 = months 4,5,6)."""
    quarter = int(quarter)
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    col = _metric_col(metric)
    all_daily = defaultdict(float)
    raw_daily = platform_data.get("daily_performance") or []
    jd_daily = platform_data.get("jingdai_daily") or []
    has_daily_rows = False

    common_cutoff = _common_mixed_cutoff(
        platform_data,
        channels,
        set(range(start_month, end_month + 1)),
    )

    for month in range(start_month, end_month + 1):
        daily_has_jingdai = _daily_contains_jingdai(raw_daily, month)

        for row in raw_daily:
            day = int(row.get("day") or 1)
            if normalize_month(row.get("month")) == month and row.get("channel") in channels:
                has_daily_rows = True
                if common_cutoff is None or (month, day) <= common_cutoff:
                    all_daily[(month, day)] += float(row.get(col) or 0)

        if JINGDAI_LINE in channels and not daily_has_jingdai:
            for row in jd_daily:
                day = int(row.get("day") or 1)
                if normalize_month(row.get("month")) == month:
                    has_daily_rows = True
                    if common_cutoff is None or (month, day) <= common_cutoff:
                        all_daily[(month, day)] += float(row.get(col) or 0)

    if not has_daily_rows:
        return {
            "labels": [],
            "values": [],
            "hasRealDailyData": False,
            "quarterMonths": list(range(start_month, end_month + 1)),
            "commonCutoff": {"month": common_cutoff[0], "day": common_cutoff[1]} if common_cutoff else None,
            "message": "No quarter daily cumulative data",
        }

    labels, values = [], []
    running = 0.0
    for month in range(start_month, end_month + 1):
        for day in range(1, _display_days_in_month(year, month, as_of_date) + 1):
            running += all_daily[(month, day)]
            labels.append(f"{month}-{day}")
            values.append(round(running, 2))

    return {
        "labels": labels,
        "values": values,
        "hasRealDailyData": True,
        "quarterMonths": list(range(start_month, end_month + 1)),
        "commonCutoff": {"month": common_cutoff[0], "day": common_cutoff[1]} if common_cutoff else None,
        "message": "",
    }


def get_platform_trend(
    year: int,
    month: int | None = None,
    channels: list[str] | None = None,
    metric: str = "qj",
    period_type: str = "year",
    period_value: int | None = None,
    as_of: str | None = None,
) -> dict:
    data = get_platform_data(year, as_of=as_of)
    channels = channels or DEFAULT_TREND_LINES
    period_type = period_type if period_type in {"year", "quarter", "month"} else "year"
    selected_month = month or (period_value if period_type == "month" else None)
    as_of_date = parse_as_of(data.get("as_of", {}).get("selectedDate") or as_of)

    result = {
        "year": year,
        "periodType": period_type,
        "periodValue": selected_month or period_value or 0,
        "businessLines": channels,
        "trend": build_period_cumulative(data, channels, metric, "quarter" if period_type == "quarter" else "year"),
        "raw": data,
    }
    if period_type == "month" and selected_month:
        result["daily"] = build_month_daily_cumulative(data, year, selected_month, channels, metric, as_of_date=as_of_date)
    elif period_type == "quarter" and period_value:
        result["daily"] = build_quarter_daily_cumulative(data, year, period_value, channels, metric, as_of_date=as_of_date)
    return result
