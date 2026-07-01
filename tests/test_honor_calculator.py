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
    assert ("00001001", "OTO") in summary_keys
    assert ("00002001", "证保") in summary_keys
    assert ("00003001", "蚁桥") not in summary_keys
    oto = next(row for row in result["person_summary"] if row["staff_code"] == "00001001")
    assert oto["diamond_balance"] == 2
    assert oto["total_gain"] == 2
    zhengbao = next(row for row in result["person_summary"] if row["staff_code"] == "00002001")
    assert zhengbao["diamond_balance"] == 0
    assert zhengbao["total_deduct"] == 1
    departure_month = next(row for row in result["person_month"] if row["staff_code"] == "00002001" and row["month"] == 2)
    assert departure_month["is_employed_end_month"] == 0
    assert departure_month["diamond_delta"] == -1


def test_honor_calculator_uses_issue_date_before_account_month(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_issue_date.db"
    monkeypatch.setenv("HONOR_AS_OF_DATE", "2026-06-03")
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    staff_rows = [
        (2026, 5, "涓婃捣", "OTO", "1001", "寮犱笁", "瀹㈡埛缁忕悊", "", 2025, 1, 1, "G1", "D1"),
        (2026, 5, "涓婃捣", "OTO", "1002", "鏉庡洓", "瀹㈡埛缁忕悊", "", 2025, 1, 1, "G1", "D1"),
    ]
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    policy_rows = [
        ("2026-06-01", "涓婃捣", "OTO", "1001", "P_ISSUE_MAY_ACCOUNT_JUNE", "2026-05-20 00:00:00", "", "2026-06-01 00:00:00", "涓€骞存湡浠ヤ笂", 10, 20000, 20000, 20000, "A", "浜у搧A"),
        ("2026-05-01", "涓婃捣", "OTO", "1002", "P_ISSUE_JUNE_ACCOUNT_MAY", "2026-06-01 00:00:00", "", "2026-05-31 00:00:00", "涓€骞存湡浠ヤ笂", 10, 20000, 20000, 20000, "A", "浜у搧A"),
    ]
    conn.executemany("INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", policy_rows)
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=5)
    by_code = {row["staff_code"]: row for row in result["person_summary"]}
    month_by_code = {row["staff_code"]: row for row in result["person_month"] if row["year"] == 2026 and row["month"] == 5}
    may_sources = {row["policy_no"] for row in result["source_policy"] if row["year"] == 2026 and row["month"] == 5}

    assert by_code["00001001"]["diamond_balance"] == 1
    assert month_by_code["00001001"]["standard_premium"] == 20000
    assert by_code["00001002"]["diamond_balance"] == 0
    assert month_by_code["00001002"]["standard_premium"] == 0
    assert "P_ISSUE_MAY_ACCOUNT_JUNE" in may_sources
    assert "P_ISSUE_JUNE_ACCOUNT_MAY" not in may_sources


def test_honor_calculator_excludes_short_term_policy_from_qualification(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_short_term.db"
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (2026, 1, "上海", "OTO", "1001", "张三", "客户经理", "", 2025, 1, 1, "G1", "D1"),
    )
    conn.execute(
        "INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("2026-01-01", "上海", "OTO", "1001", "P_SHORT", "2026-01-05 00:00:00", "2026-01-10 00:00:00", "", "短期险", 1, 200000, 200000, 200000, "A", "短险产品"),
    )
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=1)
    month = next(row for row in result["person_month"] if row["staff_code"] == "00001001")

    assert month["standard_premium"] == 0
    assert month["longterm_policy_count"] == 0
    assert month["monthly_qualified"] == 0
    assert month["diamond_balance"] == 0


def test_honor_calculator_keeps_diamond_balance_when_business_line_changes(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_business_switch.db"
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    staff_rows = [
        (2026, 1, "山东", "证券", "1001", "成妤", "创新专员", "", 2025, 1, 1, "G1", "D1"),
        (2026, 2, "山东", "证券", "1001", "成妤", "创新专员", "", 2025, 1, 1, "G1", "D1"),
        (2026, 3, "山东", "OTO", "1001", "成妤", "创新专员", "", 2025, 1, 1, "G1", "D1"),
    ]
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    policy_rows = [
        ("2026-01-01", "山东", "证券", "1001", "P1", "2026-01-05 00:00:00", "2026-01-06 00:00:00", "", "一年期以上", 10, 30000, 30000, 30000, "A", "产品A"),
        ("2026-02-01", "山东", "证券", "1001", "P2", "2026-02-05 00:00:00", "2026-02-06 00:00:00", "", "一年期以上", 10, 30000, 30000, 30000, "A", "产品A"),
        ("2026-03-01", "山东", "OTO", "1001", "P3", "2026-03-05 00:00:00", "2026-03-06 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "产品A"),
    ]
    conn.executemany("INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", policy_rows)
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=3)
    summaries = [row for row in result["person_summary"] if row["staff_code"] == "00001001"]
    months = [row for row in result["person_month"] if row["staff_code"] == "00001001"]

    assert len(summaries) == 1
    assert summaries[0]["business_line"] == "OTO"
    assert summaries[0]["diamond_balance"] == 3
    assert summaries[0]["membership_level"] == "初级会员"
    assert [row["diamond_balance"] for row in months] == [1, 2, 3]


def test_honor_calculator_applies_zhengbao_quarter_average_by_in_service_months(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_zhengbao_quarter.db"
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    staff_rows = [
        (2026, 1, "山东", "证券", "1001", "成妤", "创新专员", "", 2025, 1, 1, "G1", "D1"),
        (2026, 2, "山东", "证券", "1001", "成妤", "创新专员", "", 2025, 1, 1, "G1", "D1"),
    ]
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    policy_rows = [
        ("2026-01-01", "山东", "证券", "1001", "P1", "2026-01-05 00:00:00", "2026-01-06 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "产品A"),
        ("2026-02-01", "山东", "证券", "1001", "P2", "2026-02-05 00:00:00", "2026-02-06 00:00:00", "", "一年期以上", 10, 40000, 40000, 40000, "A", "产品A"),
    ]
    conn.executemany("INSERT INTO performance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", policy_rows)
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=3)
    months = [row for row in result["person_month"] if row["staff_code"] == "00001001"]
    summary = next(row for row in result["person_summary"] if row["staff_code"] == "00001001")

    assert [(row["month"], row["monthly_qualified"], row["diamond_delta"], row["diamond_balance"]) for row in months] == [
        (1, 1, 1, 1),
        (2, 1, 1, 2),
    ]
    assert "证保季度通算达标" in months[0]["exception_flags"]
    assert summary["diamond_balance"] == 2
    assert summary["qualified_months"] == 2


def test_honor_calculator_counts_zhengbao_quarter_rollup_in_team_star_count(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_zhengbao_team_quarter.db"
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute('ALTER TABLE performance ADD COLUMN "主管工号" TEXT')
    conn.execute('ALTER TABLE performance ADD COLUMN "经理工号" TEXT')
    staff_rows = [
        (2026, 1, "山东", "证券", "9001", "主管", "创新主管", "", 2025, 1, 1, "G1", "D1"),
        (2026, 2, "山东", "证券", "9001", "主管", "创新主管", "", 2025, 1, 1, "G1", "D1"),
    ]
    for code in ["9101", "9102", "9103", "9104"]:
        staff_rows.extend(
            [
                (2026, 1, "山东", "证券", code, f"专员{code[-1]}", "创新专员", "", 2025, 1, 1, "G1", "D1"),
                (2026, 2, "山东", "证券", code, f"专员{code[-1]}", "创新专员", "", 2025, 1, 1, "G1", "D1"),
            ]
        )
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    for code in ["9101", "9102", "9103", "9104"]:
        for month, premium in [(1, 20_000), (2, 40_000)]:
            conn.execute(
                """
                INSERT INTO performance (
                    "年月", "销售机构名称", "业务模式", "人员工号", "投保单号", "承保时间",
                    "回销时间", "入账时间", "长短险", "缴费年限", "折算保费", "年化规保",
                    "期交保费", "产品代码", "产品名称", "主管工号", "经理工号"
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (f"2026-{month:02d}-01", "山东", "证券", code, f"P{code}_{month}", f"2026-{month:02d}-05 00:00:00", f"2026-{month:02d}-06 00:00:00", "", "一年期以上", 10, premium, premium, premium, "A", "产品A", "9001", ""),
            )
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=3)
    supervisor_months = [row for row in result["person_month"] if row["staff_code"] == "00009001"]

    assert [(row["month"], row["standard_premium"], row["longterm_policy_count"], row["monthly_qualified"], row["diamond_delta"]) for row in supervisor_months] == [
        (1, 0, 0, 0, 0),
        (2, 160000, 4, 1, 1),
    ]
    assert "团队星钻达标" in supervisor_months[1]["exception_flags"]


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

    assert by_code["00001001"]["diamond_balance"] == 1
    assert by_code["00001001"]["total_gain"] == 1
    assert by_code["00001002"]["diamond_balance"] == 0
    assert any(row["exception_type"] == "callback_overdue_or_missing" and row["policy_no"] == "P2" for row in result["exceptions"])
    assert by_code["00001004"]["diamond_balance"] == 1
    assert not any(row["policy_no"] == "P4" for row in result["exceptions"])
    may_active = next(row for row in result["person_month"] if row["staff_code"] == "00001003" and row["month"] == 5)
    assert may_active["is_employed_end_month"] == 1
    assert may_active["diamond_balance"] == 1


def test_honor_calculator_uses_excel_team_logic_for_supervisor(tmp_path, monkeypatch):
    db_path = tmp_path / "honor_calc_supervisor.db"
    _setup_source_tables(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute('ALTER TABLE performance ADD COLUMN "主管工号" TEXT')
    conn.execute('ALTER TABLE performance ADD COLUMN "经理工号" TEXT')
    conn.execute('ALTER TABLE performance ADD COLUMN "承保件数" INTEGER')
    staff_rows = [
        (2026, 1, "四川", "OTO", "9001", "主管", "创新主管", "", 2025, 1, 1, "G1", "D1"),
        (2026, 1, "四川", "OTO", "9101", "专员1", "创新专员", "", 2025, 1, 1, "G1", "D1"),
        (2026, 1, "四川", "OTO", "9102", "专员2", "创新专员", "", 2025, 1, 1, "G1", "D1"),
        (2026, 1, "四川", "OTO", "9103", "专员3", "创新专员", "", 2025, 1, 1, "G1", "D1"),
        (2026, 1, "四川", "OTO", "9104", "专员4", "创新专员", "", 2025, 1, 1, "G1", "D1"),
    ]
    conn.executemany("INSERT INTO hr_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", staff_rows)
    conn.execute(
        """
        INSERT INTO performance (
            "年月", "销售机构名称", "业务模式", "人员工号", "投保单号", "承保时间",
            "回销时间", "入账时间", "长短险", "缴费年限", "折算保费", "年化规保",
            "期交保费", "产品代码", "产品名称", "主管工号", "经理工号", "承保件数"
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-01-01", "四川", "OTO", "9001", "P_SUP", "2026-01-05 00:00:00", "2026-01-10 00:00:00", "", "一年期以上", 10, 20000, 20000, 20000, "A", "主管个人件", "", "", 1),
    )
    for idx, code in enumerate(["9101", "9102", "9103", "9104"], start=1):
        conn.execute(
            """
            INSERT INTO performance (
                "年月", "销售机构名称", "业务模式", "人员工号", "投保单号", "承保时间",
                "回销时间", "入账时间", "长短险", "缴费年限", "折算保费", "年化规保",
                "期交保费", "产品代码", "产品名称", "主管工号", "经理工号", "承保件数"
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("2026-01-01", "四川", "OTO", code, f"P{idx}", "2026-01-05 00:00:00", "2026-01-10 00:00:00", "", "一年期以上", 10, 25000, 25000, 25000, "A", "产品A", "9001", "", 1),
        )
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.calculator import calculate_personal_mvp

    result = calculate_personal_mvp(batch_id=1, year=2026, month=1)
    supervisor = next(row for row in result["person_month"] if row["staff_code"] == "00009001")

    assert supervisor["role_type"] == "主管"
    assert supervisor["standard_premium"] == 120000
    assert supervisor["longterm_policy_count"] == 5
    assert supervisor["monthly_qualified"] == 1
    assert supervisor["diamond_delta"] == 2
    assert supervisor["diamond_balance"] == 2
