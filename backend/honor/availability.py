"""Read-only availability metadata for honor calculation periods."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any


HONOR_CHANNELS = ("OTO", "证保")


def latest_honor_data_availability(
    conn,
    *,
    year: int | None = None,
    today: date | None = None,
) -> dict[str, Any] | None:
    """Return the latest calculable honor period without creating a batch."""
    params: list[Any] = [*HONOR_CHANNELS]
    year_sql = ""
    if year is not None:
        year_sql = " AND year = ?"
        params.append(int(year))
    placeholders = ",".join(["?"] * len(HONOR_CHANNELS))
    try:
        rows = conn.execute(
            f"""
            SELECT year, month, channel, MAX(day) AS max_day
            FROM agg_org_daily_performance
            WHERE channel IN ({placeholders}){year_sql}
            GROUP BY year, month, channel
            ORDER BY year DESC, month DESC, channel
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    if not rows:
        return None

    latest_period = max((int(row["year"]), int(row["month"])) for row in rows)
    current_rows = [
        row
        for row in rows
        if (int(row["year"]), int(row["month"])) == latest_period
    ]
    latest_day = max(int(row["max_day"] or 1) for row in current_rows)
    latest_date = date(latest_period[0], latest_period[1], latest_day)
    channel_cutoffs = {
        str(row["channel"]): date(
            latest_period[0],
            latest_period[1],
            int(row["max_day"] or 1),
        ).isoformat()
        for row in current_rows
    }

    staff_periods: dict[str, int] = {}
    try:
        staff_rows = conn.execute(
            f"""
            SELECT channel, MAX(year * 100 + month) AS latest_period
            FROM agg_org_hr_data
            WHERE channel IN ({placeholders})
            GROUP BY channel
            """,
            HONOR_CHANNELS,
        ).fetchall()
        staff_periods = {
            str(row["channel"]): int(row["latest_period"] or 0)
            for row in staff_rows
        }
    except sqlite3.OperationalError:
        staff_periods = {}

    required_period = latest_period[0] * 100 + latest_period[1]
    missing_staff_channels = [
        channel
        for channel in HONOR_CHANNELS
        if int(staff_periods.get(channel) or 0) < required_period
    ]
    current_date = today or date.today()
    return {
        "year": latest_period[0],
        "month": latest_period[1],
        "latestDataCutoff": latest_date.isoformat(),
        "channelCutoffs": channel_cutoffs,
        "staffPeriods": staff_periods,
        "canCalculate": latest_date <= current_date and not missing_staff_channels,
        "missingStaffChannels": missing_staff_channels,
        "isCurrentMonth": (latest_period[0], latest_period[1]) == (current_date.year, current_date.month),
        "staleDays": max(0, (current_date - latest_date).days),
    }
