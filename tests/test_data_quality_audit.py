import os
import sqlite3
import sys

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def test_data_quality_audit_detects_duplicated_hr_aggregate(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db import init_db
    from services.data_quality_audit import run_data_quality_audit

    db_path = tmp_path / "audit.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    hr = pd.DataFrame(
        [
            {
                "统计年": 2026,
                "统计日期": "2026-05-01",
                "业务模式名称": "OTO",
                "销售机构名称": "上海",
                "月初在职人力": 10,
                "月末在职人力": 12,
            }
        ]
    )
    perf = pd.DataFrame(
        [
            {
                "年": 2026,
                "年月": "202605",
                "年月日": "2026-05-24",
                "业务模式": "OTO",
                "销售机构名称": "上海",
                "产品代码": "4281",
                "长短险": "一年期以上",
                "缴费年限": 10,
                "人员工号": "A001",
                "期交保费": 10000,
                "年化规保": 10000,
                "折算保费": 10000,
            }
        ]
    )
    with sqlite3.connect(db_path) as conn:
        hr.to_sql("hr_data", conn, if_exists="replace", index=False)
        perf.to_sql("performance", conn, if_exists="replace", index=False)
        conn.execute("DELETE FROM agg_hr_data WHERE year = 2026")
        conn.execute(
            """
            INSERT INTO agg_hr_data
                (year, month, channel, start_headcount, end_headcount, active_headcount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (2026, 5, "OTO", 20, 24, 1),
        )
        conn.execute(
            """
            INSERT INTO agg_daily_performance
                (year, month, day, channel, qj_premium, gm_premium, zs_premium)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (2026, 5, 24, "OTO", 1, 1, 1),
        )
        conn.commit()

    result = run_data_quality_audit(2026)

    assert result["status"] == "fail"
    assert any(
        issue["code"] == "aggregate_sum_mismatch" and issue["context"]["table"] == "agg_hr_data"
        for issue in result["issues"]
    )
