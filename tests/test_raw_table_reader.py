import os
import sqlite3
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from services.raw_table_reader import append_cutoff_filter, append_period_filter, compact_period_expr, pick_existing_column


def test_pick_existing_column_returns_first_available_candidate():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute('CREATE TABLE performance ("年月日" TEXT, "期交保费" REAL)')

        assert pick_existing_column(conn, "performance", ["时间", "年月日"]) == "年月日"
        assert pick_existing_column(conn, "performance", ["时间", "年月"]) is None
    finally:
        conn.close()


def test_append_period_filter_handles_separated_date_text():
    params = []
    clause = append_period_filter("年月日", 2026, [5, 6], params)

    assert "CAST(substr(" in clause
    assert "IN (?,?)" in clause
    assert params == [2026, 5, 6]


def test_compact_period_expr_strips_datetime_separators():
    expr = compact_period_expr("时间")

    for token in ["'-'", "'/'", "'.'", "'年'", "'月'", "'日'", "' '", "':'"]:
        assert token in expr


def test_append_cutoff_filter_uses_month_day_ytd_params():
    params = []
    clause = append_cutoff_filter("年月日", (6, 18), params)

    assert "day" not in clause
    assert "CAST(substr(" in clause
    assert params == [6, 6, 18]
