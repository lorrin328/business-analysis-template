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
    zhengbao = next(row for row in result["person_summary"] if row["staff_code"] == "2001")
    assert zhengbao["diamond_balance"] == 0
    assert zhengbao["total_deduct"] == 1
    departure_month = next(row for row in result["person_month"] if row["staff_code"] == "2001" and row["month"] == 2)
    assert departure_month["is_employed_end_month"] == 0
    assert departure_month["diamond_delta"] == -1


def test_honor_calculator_uses_45_day_callback_and_latest_staff_status(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_callback.db"
    monkeypatch.setenv("HONOR_AS_OF_DATE", "2026-06-03")
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    staff_rows = [
        (2026, 5, "上海", "OTO", "1001", "张三", "客户经理", "", 2025, 1, 1, "G1", "D1"),
        (2026, 5, "上海", "OTO", "1002", "李四", "客户经理", "", 2025, 1, 1, "G1", "D1"),
        (2026, 5, "上海", "OTO", "1003", "王五", "客户经理", "", 2025, 1, 1, "G1", "D1"),
        (2026, 5, "上海", "OTO", "1004", "赵六", "客户经理", "", 2025, 1, 1, "G1", "D1"),
        (2026, 6, "上海", "OTO", "1001", "张三", "客户经理", "", 2025, 1, 1, "G1", "D1"),
        (2026, 6, "上海", "OTO", "1002", "李四", "客户经理", "", 2025, 1, 1, "G1", "D1"),
        (2026, 6, "上海", "OTO", "1004", "赵六", "客户经理", "", 2025, 1, 1, "G1", "D1"),
    ]
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    policy_rows = [
        ("2026-05-01", "上海", "OTO", "1001", "P1", "2026-05-01 00:00:00", "2026-06-15 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "45天内"),
        ("2026-05-01", "上海", "OTO", "1002", "P2", "2026-05-01 00:00:00", "2026-06-16 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "46天"),
        ("2026-05-01", "上海", "OTO", "1003", "P3", "2026-05-01 00:00:00", "2026-05-10 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "已离职"),
        ("2026-05-01", "上海", "OTO", "1004", "P4", "2026-05-20 00:00:00", "", "", "一年期以上", 10, 20000, 20000, 20000, "A", "观察期内未回销"),
    ]
    conn.executemany("INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", policy_rows)
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=5)
    by_code = {row["staff_code"]: row for row in result["person_summary"]}

    assert by_code["1001"]["diamond_balance"] == 1
    assert by_code["1001"]["total_gain"] == 1
    assert by_code["1002"]["diamond_balance"] == 0
    assert any(row["exception_type"] == "callback_overdue_or_missing" and row["policy_no"] == "P2" for row in result["exceptions"])
    assert by_code["1004"]["diamond_balance"] == 1
    assert not any(row["policy_no"] == "P4" for row in result["exceptions"])
    departed = next(row for row in result["person_month"] if row["staff_code"] == "1003" and row["month"] == 5)
    assert departed["is_employed_end_month"] == 0
    assert departed["diamond_balance"] == 0
    assert "最新人力清单不存在" in departed["exception_flags"]
