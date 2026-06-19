"""Shared cutoff policy for daily-grain business metrics."""
from __future__ import annotations

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
