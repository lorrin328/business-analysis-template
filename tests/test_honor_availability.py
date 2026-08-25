import sqlite3
from datetime import date

from honor.availability import latest_honor_data_availability


def _availability_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE agg_org_daily_performance (
            year INTEGER, month INTEGER, day INTEGER, org TEXT, channel TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE agg_org_hr_data (
            year INTEGER, month INTEGER, org TEXT, channel TEXT, end_headcount INTEGER
        )
        """
    )
    return conn


def test_latest_honor_data_availability_uses_latest_business_day_and_staff_month():
    conn = _availability_db()
    conn.executemany(
        "INSERT INTO agg_org_daily_performance VALUES (?,?,?,?,?)",
        [
            (2026, 7, 31, "上海", "OTO"),
            (2026, 8, 25, "上海", "OTO"),
            (2026, 8, 21, "上海", "证保"),
        ],
    )
    conn.executemany(
        "INSERT INTO agg_org_hr_data VALUES (?,?,?,?,?)",
        [
            (2026, 8, "上海", "OTO", 10),
            (2026, 8, "上海", "证保", 5),
        ],
    )

    result = latest_honor_data_availability(conn, year=2026, today=date(2026, 8, 25))

    assert result["year"] == 2026
    assert result["month"] == 8
    assert result["latestDataCutoff"] == "2026-08-25"
    assert result["channelCutoffs"] == {"OTO": "2026-08-25", "证保": "2026-08-21"}
    assert result["canCalculate"] is True
    assert result["missingStaffChannels"] == []
    assert result["staleDays"] == 0


def test_latest_honor_data_availability_blocks_when_current_staff_month_is_missing():
    conn = _availability_db()
    conn.execute(
        "INSERT INTO agg_org_daily_performance VALUES (?,?,?,?,?)",
        (2026, 8, 25, "上海", "OTO"),
    )
    conn.executemany(
        "INSERT INTO agg_org_hr_data VALUES (?,?,?,?,?)",
        [
            (2026, 8, "上海", "OTO", 10),
            (2026, 7, "上海", "证保", 5),
        ],
    )

    result = latest_honor_data_availability(conn, year=2026, today=date(2026, 8, 25))

    assert result["canCalculate"] is False
    assert result["missingStaffChannels"] == ["证保"]
