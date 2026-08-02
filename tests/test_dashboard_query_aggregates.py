from contextlib import contextmanager
import os
import sqlite3
import sys

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _performance_frame():
    return pd.DataFrame(
        [
            {
                "年": 2026, "年月": "2026-05", "年月日": "2026-05-10",
                "人员工号": "001.0", "业务模式": "OTO", "销售机构名称": "上海",
                "产品代码": "4281", "产品名称": "产品甲", "产品类型": "年金",
                "期交保费": 10000, "折算保费": 1000, "年化规保": 8000,
                "承保件数": 1, "投保单号": "P1",
            },
            {
                "年": 2026, "年月": "2026-05", "年月日": "2026-05-11",
                "人员工号": "001", "业务模式": "证券", "销售机构名称": "上海",
                "产品代码": "A2", "产品名称": "产品乙", "产品类型": "寿险",
                "期交保费": 20000, "折算保费": 6000, "年化规保": 15000,
                "承保件数": 1, "投保单号": "P2",
            },
        ]
    )


def test_dashboard_aggregators_preserve_team_and_product_grains():
    from etl.aggregates.dashboard import (
        aggregate_staff_month_performance,
        aggregate_transform_product_daily,
    )

    staff = aggregate_staff_month_performance(_performance_frame())
    products = aggregate_transform_product_daily(_performance_frame())

    assert len(staff) == 2
    oto = next(row for row in staff if row["channel"] == "OTO")
    assert oto["staff_id"] == "1"
    assert oto["qj_premium"] == 1.0
    assert oto["standard_premium"] == 1.0
    assert oto["policy_count"] == 1
    assert {(row["day"], row["channel"], row["product_name"]) for row in products} == {
        (10, "OTO", "产品甲"),
        (11, "证保", "产品乙"),
    }


def test_team_repository_prefers_staff_month_aggregate():
    from db.repositories.team_enhanced import _load_performance

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''CREATE TABLE agg_staff_month_performance (
            year INTEGER, month INTEGER, channel TEXT, org TEXT, staff_id TEXT,
            qj_premium REAL, standard_premium REAL, policy_count INTEGER
        )'''
    )
    conn.execute(
        "INSERT INTO agg_staff_month_performance VALUES (2026,5,'OTO','上海','1',1.5,1.2,2)"
    )
    conn.execute('CREATE TABLE performance ("年月" TEXT, "期交保费" REAL)')
    conn.execute("INSERT INTO performance VALUES ('2026-05',99999999)")

    result = _load_performance(conn, 2026, {"OTO"}, {"上海"})

    assert result == {
        (2026, 5, "1"): {"qj_premium": 1.5, "standard_premium": 1.2, "policy_count": 2}
    }
    conn.close()


def test_product_repository_prefers_daily_aggregate(monkeypatch):
    from db.repositories import product as product_repo

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''CREATE TABLE agg_product_daily (
            year INTEGER, month INTEGER, day INTEGER, business_type TEXT,
            channel TEXT, org TEXT, product_category TEXT, product_name TEXT,
            qj_premium REAL, gm_premium REAL, count INTEGER
        )'''
    )
    conn.executemany(
        "INSERT INTO agg_product_daily VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (2026, 5, 10, "转型", "OTO", "上海", "年金", "产品甲", 8.0, 7.0, 1),
            (2026, 5, 11, "转型", "OTO", "上海", "年金", "产品乙", 2.0, 1.0, 1),
            (2026, 5, 12, "经代", "经代", "经代甲", "经代产品", "经代产品", 3.0, 2.0, 1),
        ],
    )
    conn.execute('CREATE TABLE performance ("年月" TEXT, "期交保费" REAL)')
    conn.execute('CREATE TABLE jingdai ("时间" TEXT, "经代机构" TEXT, "期交保费" REAL)')

    @contextmanager
    def fake_get_db():
        yield conn

    monkeypatch.setattr(product_repo, "get_db", fake_get_db)
    result = product_repo.get_product_structure(
        2026,
        dimension="product_mix",
        transform_lines=["OTO"],
        include_transform=True,
        include_jingdai=True,
        months=[5],
    )

    assert {row["name"]: row["value"] for row in result["premium"]} == {
        "转型-年金": 10.0,
        "经代-经代产品": 3.0,
    }
    assert result["topProducts"][0]["productName"] == "产品甲"
    assert result["jingdaiOrgs"] == ["经代甲"]
    conn.close()
