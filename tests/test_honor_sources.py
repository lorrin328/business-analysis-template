import sqlite3

from honor.sources import _performance_year_filter, metric_for_staff


def test_honor_performance_filter_uses_indexed_iso_period_range():
    conn = sqlite3.connect(":memory:")
    conn.execute('CREATE TABLE performance ("年月" TEXT)')
    conn.execute('CREATE INDEX ix_performance_period ON performance("年月")')
    conn.execute('INSERT INTO performance VALUES ("2007-07-01")')

    where, params = _performance_year_filter(conn, 2026)
    plan = conn.execute(
        f"EXPLAIN QUERY PLAN SELECT \"年月\" FROM performance WHERE {where}",
        params,
    ).fetchall()

    assert where == '"年月" >= ? AND "年月" < ?'
    assert params == ["2025-12", "2027-02"]
    assert any("ix_performance_period" in str(row) for row in plan)


def test_honor_performance_filter_supports_compact_period_values():
    conn = sqlite3.connect(":memory:")
    conn.execute('CREATE TABLE performance ("年月" TEXT)')
    conn.execute('INSERT INTO performance VALUES ("202607")')

    where, params = _performance_year_filter(conn, 2026)

    assert "CAST(substr" in where
    assert params == [202512, 202701]


def test_honor_metric_for_staff_combines_personal_and_qualified_team_metric():
    policy_index = {
        "personal": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 20_000,
                "policy_count": 1,
                "qualified": True,
                "protected": False,
            }
        },
        "supervisor": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 100_000,
                "policy_count": 4,
                "qualified": True,
                "protected": False,
            }
        },
        "manager": {},
    }

    metric = metric_for_staff(policy_index, 2026, 5, "00001001", "OTO", "主管")

    assert metric["premium"] == 120_000
    assert metric["policy_count"] == 5
    assert metric["earned_diamonds"] == 2
    assert metric["personal_qualified"] is True
    assert metric["team_qualified"] is True


def test_honor_metric_for_staff_falls_back_to_personal_metric():
    policy_index = {
        "personal": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 20_000,
                "policy_count": 1,
                "qualified": True,
                "protected": False,
            }
        },
        "supervisor": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 90_000,
                "policy_count": 3,
                "qualified": False,
                "protected": False,
            }
        },
        "manager": {},
    }

    metric = metric_for_staff(policy_index, 2026, 5, "00001001", "OTO", "主管")

    assert metric["premium"] == 20_000
    assert metric["policy_count"] == 1
    assert metric["earned_diamonds"] == 1
