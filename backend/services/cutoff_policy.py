"""Shared cutoff policy for daily-grain business metrics."""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime, timedelta
from typing import Iterable


Cutoff = dict[str, int]


def latest_daily_cutoff(
    conn: sqlite3.Connection,
    table: str,
    year: int,
    channels: Iterable[str] | None = None,
) -> Cutoff | None:
    """Return the latest available (month, day) in a daily aggregate table."""
    params: list[object] = [year]
    channel_sql = ""
    if channels:
        channel_list = [str(ch) for ch in channels]
        placeholders = ",".join(["?"] * len(channel_list))
        channel_sql = f" AND channel IN ({placeholders})"
        params.extend(channel_list)
    try:
        row = conn.execute(
            f"""
            SELECT month, MAX(day) AS max_day
            FROM {table}
            WHERE year = ?{channel_sql}
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or not row["month"]:
        return None
    return {"month": int(row["month"]), "day": int(row["max_day"] or 31)}


def min_cutoff(*cutoffs: Cutoff | None) -> Cutoff | None:
    valid = [c for c in cutoffs if c]
    if not valid:
        return None
    return min(valid, key=lambda c: (c["month"], c["day"]))


def max_cutoff(*cutoffs: Cutoff | None) -> Cutoff | None:
    valid = [c for c in cutoffs if c]
    if not valid:
        return None
    return max(valid, key=lambda c: (c["month"], c["day"]))


def date_filter_sql(cutoff: Cutoff) -> tuple[str, list[int]]:
    """SQL condition and params for inclusive YTD cutoff on month/day columns."""
    return "(month < ? OR (month = ? AND day <= ?))", [
        cutoff["month"],
        cutoff["month"],
        cutoff["day"],
    ]


def date_start_filter_sql(cutoff: Cutoff) -> tuple[str, list[int]]:
    """SQL condition and params for an inclusive lower month/day bound."""
    return "(month > ? OR (month = ? AND day >= ?))", [
        cutoff["month"],
        cutoff["month"],
        cutoff["day"],
    ]


def date_range_filter_sql(start: Cutoff, end: Cutoff) -> tuple[str, list[int]]:
    """SQL condition and params for an inclusive month/day range."""
    start_sql, start_params = date_start_filter_sql(start)
    end_sql, end_params = date_filter_sql(end)
    return f"({start_sql}) AND ({end_sql})", [*start_params, *end_params]


def channel_cutoff_filter_sql(
    channel_cutoffs: dict[str, Cutoff | tuple[int, int]],
    *,
    channel_column: str = "channel",
) -> tuple[str, list[object]]:
    """SQL condition and params for per-channel inclusive YTD cutoffs."""
    clauses = []
    params: list[object] = []
    for channel, cutoff in channel_cutoffs.items():
        if isinstance(cutoff, dict):
            month = int(cutoff["month"])
            day = int(cutoff["day"])
        else:
            month = int(cutoff[0])
            day = int(cutoff[1])
        clauses.append(f"({channel_column} = ? AND (month < ? OR (month = ? AND day <= ?)))")
        params.extend([channel, month, month, day])
    if not clauses:
        return "", []
    return f"({' OR '.join(clauses)})", params


def parse_as_of(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def cutoff_from_date(value: date | None) -> Cutoff | None:
    if not value:
        return None
    return {"month": int(value.month), "day": int(value.day)}


def cutoff_to_date(year: int, cutoff: Cutoff | None) -> date | None:
    if not cutoff:
        return None
    try:
        return date(int(year), int(cutoff["month"]), int(cutoff["day"]))
    except ValueError:
        return None


def cutoff_min(a: Cutoff | None, b: Cutoff | None) -> Cutoff | None:
    if not a:
        return b
    if not b:
        return a
    return min_cutoff(a, b)


def latest_dashboard_cutoff(conn: sqlite3.Connection, year: int) -> Cutoff | None:
    """Latest available daily cutoff across dashboard business sources."""
    return max_cutoff(
        latest_daily_cutoff(conn, "agg_daily_performance", year),
        latest_daily_cutoff(conn, "agg_jingdai_daily", year),
        latest_daily_cutoff(conn, "agg_org_daily_performance", year),
    )


def _option_dates(latest_date: date | None, days: int = 3) -> list[str]:
    if not latest_date:
        return []
    start = latest_date - timedelta(days=max(days - 1, 0))
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def _date_for_year(value: date | None, year: int) -> date | None:
    if not value:
        return None
    day = min(value.day, calendar.monthrange(year, value.month)[1])
    return date(year, value.month, day)


def _range_label(range_type: str, start: date, end: date) -> str:
    if range_type == "day":
        return f"{end.year}年{end.month}月{end.day}日"
    if range_type == "month":
        suffix = "" if end.day == calendar.monthrange(end.year, end.month)[1] else f"（截至{end.day}日）"
        return f"{end.year}年{end.month}月{suffix}"
    if range_type == "ytd":
        return f"{end.year}年累计至{end.month}月{end.day}日"
    return f"{start.year}年{start.month}月{start.day}日至{end.year}年{end.month}月{end.day}日"


def build_period_context(
    conn: sqlite3.Connection,
    year: int,
    *,
    range_type: str | None = None,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    as_of: str | date | None = None,
    today: date | None = None,
) -> dict:
    """Build a normalized dashboard period while preserving the legacy ``asOf`` contract.

    ``ytd`` is the backwards-compatible default. ``month`` and ``day`` derive
    their bounds from the supplied end/start date. ``custom`` is an inclusive
    range. All ranges are constrained to the selected dashboard year and the
    latest available daily business date.
    """
    year = int(year)
    mode = str(range_type or "ytd").strip().lower()
    if mode not in {"ytd", "month", "day", "custom"}:
        mode = "ytd"

    def _parse(value: str | date | None) -> date | None:
        parsed = parse_as_of(value) if isinstance(value, str) else value
        return _date_for_year(parsed, year)

    requested_start = _parse(start_date)
    requested_end = _parse(end_date) or _parse(as_of)
    as_of_context = build_as_of_context(conn, year, requested_end, today=today)
    latest = parse_as_of(as_of_context.get("latestDataDate"))
    default_end = parse_as_of(as_of_context.get("selectedDate")) or date(year, 12, 31)
    anchor = requested_end or requested_start or default_end

    if mode == "month":
        start = date(year, anchor.month, 1)
        end = date(year, anchor.month, calendar.monthrange(year, anchor.month)[1])
    elif mode == "day":
        start = anchor
        end = anchor
    elif mode == "custom":
        start = requested_start or date(year, 1, 1)
        end = requested_end or default_end
    else:
        start = date(year, 1, 1)
        end = requested_end or default_end

    if start > end:
        start, end = end, start
    if latest and end > latest:
        end = latest
    if latest and start > latest:
        start = latest
    if start > end:
        start = end

    start_cutoff = cutoff_from_date(start)
    end_cutoff = cutoff_from_date(end)
    previous_start = _date_for_year(start, year - 1)
    previous_end = _date_for_year(end, year - 1)
    target_mode = "year" if mode == "ytd" else "month" if mode == "month" else "none"

    as_of_context.update(
        {
            "selectedDate": end.isoformat(),
            "selectedCutoff": end_cutoff,
            "options": [],
        }
    )
    return {
        "year": year,
        "rangeType": mode,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "startCutoff": start_cutoff,
        "endCutoff": end_cutoff,
        "label": _range_label(mode, start, end),
        "comparison": {
            "startDate": previous_start.isoformat() if previous_start else None,
            "endDate": previous_end.isoformat() if previous_end else None,
        },
        "targetMode": target_mode,
        "precision": {
            "premium": "day",
            "product": "day",
            "paymentPeriod": "day",
            "headcount": "month",
            "value": "month",
        },
        "latestDataDate": latest.isoformat() if latest else None,
        "warning": bool(as_of_context.get("warning")),
        "warningText": as_of_context.get("warningText") or "",
        "asOf": as_of_context,
    }


def build_as_of_context(
    conn: sqlite3.Connection,
    year: int,
    as_of: str | date | None = None,
    *,
    today: date | None = None,
) -> dict:
    """Build dashboard cutoff context.

    Default is yesterday. If imported data lags system date by at least two days,
    use the imported cutoff and require a data-scope warning.
    """
    today = today or date.today()
    latest_cutoff = latest_dashboard_cutoff(conn, year)
    latest_date = cutoff_to_date(year, latest_cutoff)
    requested_date = parse_as_of(as_of) if isinstance(as_of, str) else as_of
    if requested_date and requested_date.year != int(year):
        try:
            requested_date = date(int(year), requested_date.month, requested_date.day)
        except ValueError:
            requested_date = None

    if requested_date:
        effective_date = requested_date
        if latest_date and effective_date > latest_date:
            effective_date = latest_date
    else:
        default_date = today - timedelta(days=1)
        warn = bool(latest_date and (today - latest_date).days >= 2)
        effective_date = latest_date if warn else default_date
        if latest_date and effective_date > latest_date:
            effective_date = latest_date

    warning = bool(latest_date and (today - latest_date).days >= 2)
    effective_cutoff = cutoff_min(cutoff_from_date(effective_date), latest_cutoff)
    effective_date = cutoff_to_date(year, effective_cutoff)
    return {
        "year": int(year),
        "systemDate": today.isoformat(),
        "latestDataDate": latest_date.isoformat() if latest_date else None,
        "defaultDate": effective_date.isoformat() if effective_date else None,
        "selectedDate": effective_date.isoformat() if effective_date else None,
        "selectedCutoff": effective_cutoff,
        "options": _option_dates(latest_date),
        "warning": warning,
        "warningText": "请注意数据口径" if warning else "",
    }


def build_source_cutoff_policy(
    transform_cutoff: Cutoff | None,
    jingdai_cutoff: Cutoff | None,
) -> dict:
    """Describe how transform and jingdai should be read for KPI-style YTD metrics.

    Transform and jingdai keep their own source cutoffs because their source
    reports are generated on different schedules. The common cutoff is exposed
    for comparison views that intentionally require same-day mixed-source lines.
    """
    latest = max_cutoff(transform_cutoff, jingdai_cutoff)
    use_daily = bool(transform_cutoff and jingdai_cutoff)
    common = min_cutoff(transform_cutoff, jingdai_cutoff) if use_daily else None
    partial_daily = bool(latest and not use_daily)
    if use_daily:
        mode = "daily_by_source"
    elif partial_daily:
        mode = "monthly_complete_fallback"
    else:
        mode = "monthly"
    return {
        "use_daily": use_daily,
        "partial_daily": partial_daily,
        "mode": mode,
        "latest": latest,
        "common": common,
        "transform": transform_cutoff,
        "jingdai": jingdai_cutoff,
    }
