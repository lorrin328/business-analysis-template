import os
import sqlite3
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.cutoff_policy import build_source_cutoff_policy, date_filter_sql, latest_daily_cutoff


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
    assert date_filter_sql(policy["common"]) == (
        "(month < ? OR (month = ? AND day <= ?))",
        [5, 5, 22],
    )
