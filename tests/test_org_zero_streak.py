import sqlite3
from datetime import date

import pytest

from services.org_zero_streak import get_org_zero_streak


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE agg_org_daily_activity(year,month,day,org,channel,has_positive_qj,uncertain)")
    db.execute("CREATE TABLE target_values(year,org,business_line,target_value,period_type DEFAULT 'year',period_value DEFAULT 0)")
    db.execute("CREATE TABLE agg_org_hr_data(year,month,org,channel,start_headcount,end_headcount)")
    yield db
    db.close()


def add(conn, day, positive=0, uncertain=0, org="上海", channel="OTO"):
    y, m, d = map(int, day.split("-"))
    conn.execute("INSERT INTO agg_org_daily_activity VALUES (?,?,?,?,?,?,?)", (y, m, d, org, channel, positive, uncertain))


def query(conn, end="2026-08-31", today=date(2026, 9, 1)):
    return get_org_zero_streak(conn, int(end[:4]), end, today=today)


def test_positive_issuance_resets_despite_net_refund(conn):
    add(conn, "2026-08-28", 1)
    add(conn, "2026-08-31", 1, 1)
    data = query(conn)["year"]
    assert data["projects"]["上海|OTO"]["days"] == 0
    assert data["orgs"]["上海"]["days"] == 0


def test_weekend_days_and_institution_union(conn):
    add(conn, "2026-08-28", 1, channel="证保")
    add(conn, "2026-08-31", 1)
    data = query(conn)["year"]
    assert data["projects"]["上海|证保"]["days"] == 3
    assert data["projects"]["上海|证保"]["startDate"] == "2026-08-29"
    assert data["orgs"]["上海"]["days"] == 0


def test_global_cutoff_does_not_stop_at_project_last_sale(conn):
    add(conn, "2026-08-20", 1, channel="证保")
    add(conn, "2026-08-31", 1, org="湖北")
    assert query(conn)["year"]["projects"]["上海|证保"]["days"] == 11


def test_cross_month_and_monthly_snapshots_are_not_sums(conn):
    add(conn, "2026-07-30", 1)
    add(conn, "2026-07-31", 1, org="湖北")
    add(conn, "2026-08-31", 1, org="湖北")
    data = query(conn)
    assert data["month"]["7"]["projects"]["上海|OTO"]["days"] == 1
    # Annual target means the project is in observation scope in August too.
    conn.execute("INSERT INTO target_values(year,org,business_line,target_value) VALUES(2026,'上海','OTO',100)")
    assert query(conn)["year"]["projects"]["上海|OTO"]["days"] == 32


def test_cross_year_history_not_truncated(conn):
    add(conn, "2025-12-30", 1)
    add(conn, "2026-01-03", org="湖北")
    conn.execute("INSERT INTO target_values(year,org,business_line,target_value) VALUES(2026,'上海','OTO',100)")
    assert query(conn, "2026-01-03")["year"]["projects"]["上海|OTO"]["days"] == 4


def test_missing_source_month_only_lower_bound(conn):
    add(conn, "2026-06-28", 1)
    add(conn, "2026-08-01", org="湖北")
    add(conn, "2026-08-31", org="湖北")
    item = query(conn)["year"]["projects"]["上海|OTO"]
    assert item["status"] == "lower_bound"
    assert item["days"] == 31


def test_only_refunds_without_last_sale_lower_bound(conn):
    add(conn, "2026-08-28")
    add(conn, "2026-08-31", org="湖北")
    item = query(conn)["year"]["projects"]["上海|OTO"]
    assert item["days"] == 4
    assert item["status"] == "lower_bound"


@pytest.mark.parametrize("bad_day", ["2026-08-29", "2026-08-00"])
def test_ambiguous_rows_block_exact_zero_claim(conn, bad_day):
    add(conn, "2026-08-28", 1)
    add(conn, bad_day, uncertain=1)
    add(conn, "2026-08-31", org="湖北")
    item = query(conn)["year"]["projects"]["上海|OTO"]
    assert item["status"] == "unknown" and item["days"] is None


def test_new_sale_after_ambiguity_resets_it(conn):
    add(conn, "2026-08-28", uncertain=1)
    add(conn, "2026-08-29", 1)
    add(conn, "2026-08-31", org="湖北")
    assert query(conn)["year"]["projects"]["上海|OTO"]["days"] == 2


def test_unobserved_projects_not_fabricated_as_zero(conn):
    add(conn, "2026-08-31", 1)
    item = query(conn)["year"]["projects"]["北京|蚁桥"]
    assert item["status"] == "not_observed" and item["days"] is None
    conn.execute("INSERT INTO target_values(year,org,business_line,target_value) VALUES(2026,'北京','蚁桥',10)")
    item = query(conn)["year"]["projects"]["北京|蚁桥"]
    assert item["status"] == "unknown" and item["days"] is None


def test_unobserved_project_does_not_erase_institution_last_sale(conn):
    add(conn, "2026-08-28", 1)
    add(conn, "2026-08-31", org="湖北")
    conn.execute("INSERT INTO agg_org_hr_data VALUES(2026,8,'上海','证保',1,1)")
    data = query(conn)["year"]
    assert data["orgs"]["上海"]["days"] == 3
    assert data["projects"]["上海|证保"]["status"] == "unknown"
    conn.execute("INSERT INTO agg_org_hr_data VALUES(2026,8,'北京','OTO',1,1)")
    assert query(conn)["year"]["orgs"]["北京"]["status"] == "unknown"
    add(conn, "2026-08-31", 1)
    assert query(conn)["year"]["orgs"]["上海"]["days"] == 0


def test_cutoff_never_extends_unimported_days_or_current_day(conn):
    add(conn, "2026-08-26", 1)
    assert query(conn)["year"]["cutoff"] == "2026-08-26"
    add(conn, "2026-08-31", 1)
    assert query(conn, today=date(2026, 8, 31))["year"]["cutoff"] == "2026-08-30"


def test_missing_table_or_month_only_cannot_show_zero(conn):
    add(conn, "2026-08-00", uncertain=1)
    assert query(conn)["year"]["cutoff"] is None
    conn.execute("DROP TABLE agg_org_daily_activity")
    assert query(conn)["year"]["orgs"]["上海"]["days"] is None


@pytest.mark.parametrize("period,value", [("month", 9), ("quarter", 4)])
def test_future_targets_do_not_change_past_streaks(conn, period, value):
    add(conn, "2026-01-28", 1)
    add(conn, "2026-01-31", org="湖北")
    conn.execute("INSERT INTO target_values VALUES(2026,'上海','证保',100,?,?)", (period, value))
    assert query(conn, "2026-01-31")["year"]["orgs"]["上海"]["days"] == 3
