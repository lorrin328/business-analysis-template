import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def _patch_db(monkeypatch, path):
    import db.connection as connection

    monkeypatch.setattr(connection, "DB_PATH", str(path))


def _setup_source_tables(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE hr_data (
            "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT, "业务模式名称" TEXT,
            "人员代码" TEXT, "人员姓名" TEXT, "职等" TEXT, "职级" TEXT,
            "入职年" INTEGER, "入职月" INTEGER, "月末在职人力" INTEGER,
            "营业组CODE" TEXT, "营业部CODE" TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE performance (
            "年月" TEXT, "销售机构名称" TEXT, "业务模式" TEXT, "人员工号" TEXT,
            "投保单号" TEXT, "承保时间" TEXT, "回销时间" TEXT, "入账时间" TEXT,
            "长短险" TEXT, "缴费年限" REAL, "折算保费" REAL, "年化规保" REAL,
            "期交保费" REAL, "产品代码" TEXT, "产品名称" TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def test_honor_calculator_excludes_yiqiao_and_calculates_oto_zhengbao(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc.db"
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    staff_rows = [
        (2026, 1, "上海", "OTO", "1001", "张三", "客户经理", "", 2026, 1, 1, "G1", "D1"),
        (2026, 2, "上海", "OTO", "1001", "张三", "客户经理", "", 2026, 1, 1, "G1", "D1"),
        (2026, 1, "上海", "证券", "2001", "李四", "客户经理", "", 2025, 1, 1, "G2", "D2"),
        (2026, 1, "上海", "网服", "3001", "王五", "客户经理", "", 2025, 1, 1, "G2", "D2"),
    ]
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    policy_rows = [
        ("2026-01-01", "上海", "OTO", "1001", "P1", "2026-01-05 00:00:00", "2026-01-10 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "产品A"),
        ("2026-02-01", "上海", "OTO", "1001", "P2", "2026-02-05 00:00:00", "2026-02-10 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "产品A"),
        ("2026-01-01", "上海", "证券", "2001", "P3", "2026-01-05 00:00:00", "2026-01-10 00:00:00", "", "一年期以上", 10, 30000, 30000, 30000, "B", "产品B"),
        ("2026-01-01", "上海", "网服", "3001", "P4", "2026-01-05 00:00:00", "2026-01-10 00:00:00", "", "一年期以上", 10, 999999, 999999, 999999, "C", "产品C"),
    ]
    conn.executemany("INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", policy_rows)
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=2)

    summary_keys = {(row["staff_code"], row["business_line"]) for row in result["person_summary"]}
    assert ("1001", "OTO") in summary_keys
    assert ("2001", "证保") in summary_keys
    assert ("3001", "蚁桥") not in summary_keys
    oto = next(row for row in result["person_summary"] if row["staff_code"] == "1001")
    assert oto["diamond_balance"] == 2
    assert oto["total_gain"] == 2
