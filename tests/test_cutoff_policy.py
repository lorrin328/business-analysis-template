import os
import sqlite3
import sys
from datetime import date


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.cutoff_policy import (
    build_period_context,
    build_source_cutoff_policy,
    channel_cutoff_filter_sql,
    date_filter_sql,
    latest_daily_cutoff,
)


def _period_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE agg_daily_performance (year INTEGER, month INTEGER, day INTEGER, channel TEXT)")
    conn.execute("INSERT INTO agg_daily_performance VALUES (2026, 7, 13, 'OTO')")
    return conn


def test_period_context_supports_ytd_month_day_and_custom_ranges():
    conn = _period_conn()

    ytd = build_period_context(conn, 2026, range_type="ytd", today=date(2026, 7, 14))
    month = build_period_context(conn, 2026, range_type="month", end_date="2026-06-18")
    day = build_period_context(conn, 2026, range_type="day", end_date="2026-07-05")
    custom = build_period_context(
        conn, 2026, range_type="custom", start_date="2026-06-20", end_date="2026-07-20"
    )

    assert (ytd["startDate"], ytd["endDate"], ytd["targetMode"]) == ("2026-01-01", "2026-07-13", "year")
    assert (month["startDate"], month["endDate"], month["targetMode"]) == ("2026-06-01", "2026-06-30", "month")
    assert (day["startDate"], day["endDate"], day["targetMode"]) == ("2026-07-05", "2026-07-05", "none")
    assert (custom["startDate"], custom["endDate"]) == ("2026-06-20", "2026-07-13")
    assert custom["comparison"] == {"startDate": "2025-06-20", "endDate": "2025-07-13"}
    assert custom["precision"]["headcount"] == "month"


def test_cutoff_policy_keeps_source_cutoffs_and_exposes_common_cutoff():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE agg_daily_performance (year INTEGER, month INTEGER, day INTEGER, channel TEXT)")
    conn.executemany(
        "INSERT INTO agg_daily_performance VALUES (?, ?, ?, ?)",
        [(2026, 5, 23, "OTO"), (2026, 5, 21, "证保")],
    )

    transform = latest_daily_cutoff(conn, "agg_daily_performance", 2026)
    jingdai = {"month": 5, "day": 22}
    policy = build_source_cutoff_policy(transform, jingdai)

    assert policy["transform"] == {"month": 5, "day": 23}
    assert policy["jingdai"] == {"month": 5, "day": 22}
    assert policy["latest"] == {"month": 5, "day": 23}
    assert policy["common"] == {"month": 5, "day": 22}
    assert policy["use_daily"] is True
    assert policy["partial_daily"] is False
    assert policy["mode"] == "daily_by_source"
    assert date_filter_sql(policy["common"]) == (
        "(month < ? OR (month = ? AND day <= ?))",
        [5, 5, 22],
    )


def test_cutoff_policy_marks_partial_daily_without_enabling_daily_reads():
    policy = build_source_cutoff_policy({"month": 5, "day": 23}, None)

    assert policy["use_daily"] is False
    assert policy["partial_daily"] is True
    assert policy["mode"] == "monthly_complete_fallback"
    assert policy["latest"] == {"month": 5, "day": 23}
    assert policy["common"] is None


def test_channel_cutoff_filter_sql_builds_per_channel_ytd_condition():
    sql, params = channel_cutoff_filter_sql(
        {
            "OTO": {"month": 5, "day": 23},
            "证保": (5, 21),
        }
    )

    assert sql == (
        "((channel = ? AND (month < ? OR (month = ? AND day <= ?))) OR "
        "(channel = ? AND (month < ? OR (month = ? AND day <= ?))))"
    )
    assert params == ["OTO", 5, 5, 23, "证保", 5, 5, 21]
