import os
import sqlite3
import sys

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def test_rebuild_aggregates_from_raw_tables_recreates_sqlite_aggregates(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db import init_db
    from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables

    db_path = tmp_path / "business.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    performance = pd.DataFrame(
        [
            {
                "年": 2026,
                "年月": "202605",
                "年月日": "2026-05-23",
                "业务模式": "OTO",
                "销售机构名称": "上海",
                "产品代码": "4281",
                "产品名称": "测试长期险",
                "长短险": "一年期以上",
                "缴费年限": 10,
                "人员工号": "A001",
                "期交保费": 10000,
                "年化规保": 12000,
                "折算保费": 10000,
            },
            {
                "年": 2026,
                "年月": "202605",
                "年月日": "2026-05-23",
                "业务模式": "证保",
                "销售机构名称": "湖北",
                "产品代码": "7001",
                "产品名称": "测试短险",
                "长短险": "一年期",
                "缴费年限": 1,
                "人员工号": "A002",
                "期交保费": 20000,
                "年化规保": 20000,
                "折算保费": 20000,
            },
        ]
    )
    jingdai = pd.DataFrame(
        [
            {
                "时间": "2026-05-22",
                "经代机构": "测试经代",
                "产品名称": "经代长期险",
                "当前缴别大类": "5年交",
                "缴费年限": 5,
                "缴费年限范围": "一年期以上",
                "期交保费": 30000,
                "承保年化规保": 30000,
            }
        ]
    )
    hr_data = pd.DataFrame(
        [
            {
                "统计年": 2026,
                "统计日期": "202605",
                "业务模式名称": "OTO",
                "销售机构名称": "上海",
                "月初在职人力": 10,
                "月末在职人力": 12,
            }
        ]
    )
    value_data = pd.DataFrame(
        [
            {
                "年月": "202605",
                "业务模式名称": "OTO",
                "销售机构名称": "上海",
                "价值": 5000,
            }
        ]
    )

    with sqlite3.connect(db_path) as conn:
        pd.concat([performance, performance.iloc[[0]]], ignore_index=True).to_sql(
            "performance",
            conn,
            if_exists="replace",
            index=False,
        )
        jingdai.to_sql("jingdai", conn, if_exists="replace", index=False)
        hr_data.to_sql("hr_data", conn, if_exists="replace", index=False)
        value_data.to_sql("value_data", conn, if_exists="replace", index=False)

    result = rebuild_aggregates_from_raw_tables()

    assert result.years == [2026]
    assert result.raw_counts == {
        "performance": 2,
        "jingdai": 1,
        "hr_data": 1,
        "value_data": 1,
    }
    assert result.table_counts["agg_daily_performance"] == 2
    assert result.table_counts["agg_jingdai_daily"] == 1
    assert result.table_counts["agg_longterm_qj"] == 2

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] >= 1
        assert conn.execute("SELECT ROUND(SUM(qj_premium), 2) FROM agg_daily_performance").fetchone()[0] == 3
        assert conn.execute("SELECT ROUND(SUM(qj_premium), 2) FROM agg_jingdai_daily").fetchone()[0] == 3
        assert conn.execute("SELECT ROUND(SUM(value_premium), 2) FROM agg_value_data").fetchone()[0] == 0.5
