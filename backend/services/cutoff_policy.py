"""Shared cutoff policy for daily-grain business metrics."""
from __future__ import annotations

import sqlite3
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
