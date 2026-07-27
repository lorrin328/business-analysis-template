import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def test_team_enhanced_keeps_zero_productivity_staff(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "人员姓名" TEXT, "月末司龄区间" TEXT,
                "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 5, "上海", "OTO", "F1", "A001", "甲", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A002", "乙", "1年以内", 1, 1),
                (2026, 5, "上海", "证券", "F2", "A003", "丙", "1-3年", 1, 1),
                (2026, 5, "上海", "网服", "F3", "A004", "丁", "3年以上", 1, 1),
                (2026, 5, "上海", "OTO", "小计", "A999", "小计", "小计", 1, 1),
            ],
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202605", "OTO", "上海", "A001", "P1", 10000),
                (2026, "202605", "证券", "上海", "A003", "P2", 30000),
                (2026, "202605", "网服", "上海", "A004", "P3", 60000),
            ],
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, month=5)

    assert result["summary"]["sampleCount"] == 4
    assert result["summary"]["activeCount"] == 3
    assert result["summary"]["zeroRate"] == 25.0
    assert result["summary"]["p25"] == 0.75
    assert result["summary"]["p25Count"] == 3
    assert result["summary"]["p50"] == 2.0
    assert result["summary"]["p50Count"] == 2
    assert result["summary"]["p75"] == 3.75
    assert result["summary"]["p75Count"] == 1
    zero_band = next(row for row in result["productivityBands"] if row["label"] == "0及以下")
    assert zero_band["count"] == 1
    assert {row["label"] for row in result["percentiles"]} == {"整体", "OTO", "证保", "蚁桥"}
    assert result["tenureStructure"][0]["count"] == 2
    assert len(result["orgPercentiles"]) == 1


def test_team_enhanced_empty_response_without_hr_table(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_empty.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute("CREATE TABLE performance (dummy TEXT)")
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="quarter", period_value=2, business_lines=["证券"])

    assert result["months"] == []
    assert result["summary"]["sampleCount"] == 0
    assert result["standardManpower"]["periodMonths"] == 0
    assert result["filters"]["businessLines"] == ["证保"]


def test_team_enhanced_empty_response_without_selected_months(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_no_month.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="month", period_value=6, scope="active")

    assert result["month"] is None
    assert result["months"] == []
    assert result["summary"]["sampleCount"] == 0
    assert result["filters"]["scope"] == "active"


def test_team_enhanced_quarter_deduplicates_staff_across_months(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_quarter.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 4, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "北京", "OTO", "F1", "A002", "1年以内", 1, 1),
            ],
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202604", "OTO", "上海", "A001", "P1", 10000),
                (2026, "202605", "OTO", "上海", "A001", "P2", 20000),
                (2026, "202605", "OTO", "北京", "A002", "P3", 40000),
            ],
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="quarter", period_value=2)

    assert result["months"] == [4, 5]
    assert result["summary"]["sampleCount"] == 2
    assert result["summary"]["qjPremium"] == 7.0
    assert {row["label"] for row in result["orgPercentiles"]} == {"上海", "北京"}


def test_team_enhanced_scope_active_excludes_zero_productivity(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_active.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A002", "1年以内", 1, 1),
            ],
        )
        conn.execute('INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?)', (2026, "202605", "OTO", "上海", "A001", "P1", 10000))
        conn.commit()

    result = get_team_enhanced_analysis(2026, month=5, scope="active")

    assert result["summary"]["sampleCount"] == 1
    assert result["summary"]["zeroRate"] == 0.0


def test_team_enhanced_business_line_filter(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_line.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "上海", "证券", "F1", "A002", "1年以内", 1, 1),
                (2026, 5, "上海", "网服", "F1", "A003", "1年以内", 1, 1),
            ],
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202605", "OTO", "上海", "A001", "P1", 10000),
                (2026, "202605", "证券", "上海", "A002", "P2", 20000),
                (2026, "202605", "网服", "上海", "A003", "P3", 30000),
            ],
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="month", period_value=5, business_lines=["证保"])

    assert result["summary"]["sampleCount"] == 1
    assert result["summary"]["qjPremium"] == 2.0
    assert result["filters"]["businessLines"] == ["证保"]


def test_team_enhanced_high_productivity_by_line_and_org_uses_full_group_denominators(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_high_productivity.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL
            )"""
        )
        staff_rows = [
            (2026, 5, "上海", "OTO", "F1", "A000", "1年以内", 1, 1),
            (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
            (2026, 5, "上海", "OTO", "F1", "A002", "1年以内", 1, 1),
            (2026, 5, "上海", "证券", "F2", "B001", "1年以内", 1, 1),
            (2026, 5, "北京", "证券", "F2", "B002", "1年以内", 1, 1),
            (2026, 5, "上海", "网服", "F3", "C001", "1年以内", 1, 1),
        ]
        conn.executemany('INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', staff_rows)
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202605", "OTO", "上海", "A000", "P0", 500000),
                (2026, "202605", "OTO", "上海", "A001", "P1", 600000),
                (2026, "202605", "OTO", "上海", "A002", "P2", 1000000),
                (2026, "202605", "证券", "上海", "B001", "P3", 1490000),
                (2026, "202605", "证券", "北京", "B002", "P4", 10000000),
                (2026, "202605", "网服", "上海", "C001", "P5", 20000000),
            ],
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="month", period_value=5)
    high = result["highProductivity"]

    by_line = {row["businessLine"]: row for row in high["byBusinessLine"]}
    assert set(by_line) == {"OTO", "证保"}
    assert by_line["OTO"]["trackedHeadcount"] == 3
    assert by_line["OTO"]["qjPremium"] == 210.0
    oto_bands = {row["label"]: row for row in by_line["OTO"]["bands"]}
    assert oto_bands["[60万,100万)"] == {
        "label": "[60万,100万)",
        "count": 1,
        "headcountShare": 33.3,
        "qjPremium": 60.0,
        "premiumShare": 28.6,
    }
    assert oto_bands["[100万,150万)"]["count"] == 1
    assert oto_bands["[100万,150万)"]["qjPremium"] == 100.0
    assert oto_bands["[1000万,+)"]["count"] == 0

    by_org_line = {(row["org"], row["businessLine"]): row for row in high["byOrgBusinessLine"]}
    assert set(by_org_line) == {("上海", "OTO"), ("上海", "证保"), ("北京", "证保")}
    beijing_zhengbao = by_org_line[("北京", "证保")]
    top_band = next(row for row in beijing_zhengbao["bands"] if row["label"] == "[1000万,+)")
    assert top_band["count"] == 1
    assert top_band["headcountShare"] == 100.0
    assert top_band["qjPremium"] == 1000.0
    assert top_band["premiumShare"] == 100.0


def test_team_enhanced_uses_end_month_headcount_scope(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_end_month.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL, "折算保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A002", "1年以内", 1, 0),
                (2026, 5, "上海", "证券", "F2", "B001", "1年以内", 1, 1),
            ],
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202605", "OTO", "上海", "A001", "P1", 20000, 20000),
                (2026, "202605", "OTO", "上海", "A002", "P2", 80000, 80000),
                (2026, "202605", "证券", "上海", "B001", "P3", 30000, 30000),
            ],
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="month", period_value=5, business_lines=["OTO", "证保"])

    assert result["summary"]["sampleCount"] == 2
    assert result["summary"]["qjPremium"] == 5.0
    assert result["standardManpower"]["summary"][0]["trackedHeadcount"] == 2


def test_team_enhanced_standard_manpower_by_org_line_and_month(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_standard.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "期交保费" REAL, "折算保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A002", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A003", "1年以内", 1, 0),
                (2026, 5, "上海", "证券", "F2", "B001", "1年以内", 1, 1),
                (2026, 5, "北京", "证券", "F2", "B002", "1年以内", 1, 1),
                (2026, 4, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
            ],
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202605", "OTO", "上海", "A001", "P1", 30000, 25000),
                (2026, "202605", "OTO", "上海", "A002", "P2", 20000, 19000),
                (2026, "202605", "OTO", "上海", "A003", "P3", 50000, 50000),
                (2026, "202605", "证券", "上海", "B001", "P4", 40000, 30000),
                (2026, "202605", "证券", "北京", "B002", "P5", 10000, 35000),
                (2026, "202604", "OTO", "上海", "A001", "P6", 10000, 21000),
            ],
        )
        conn.commit()

    result = get_team_enhanced_analysis(2026, period_type="month", period_value=5)
    standard = result["standardManpower"]
    overall = standard["summary"][0]

    assert overall["trackedHeadcount"] == 4
    assert overall["standardCount"] == 3
    assert overall["standardRate"] == 75.0
    assert overall["qjPremium"] == 10.0
    assert overall["standardQjPremium"] == 8.0
    assert overall["premiumContributionRate"] == 80.0

    by_line = {row["label"]: row for row in standard["byBusinessLine"]}
    assert by_line["OTO"]["trackedHeadcount"] == 2
    assert by_line["OTO"]["standardCount"] == 1
    assert by_line["OTO"]["standardQjPremium"] == 3.0
    assert by_line["证保"]["trackedHeadcount"] == 2
    assert by_line["证保"]["standardCount"] == 2
    assert by_line["证保"]["standardQjPremium"] == 5.0

    shanghai = next(row for row in standard["byOrg"] if row["label"] == "上海")
    assert shanghai["trackedHeadcount"] == 3
    assert shanghai["standardCount"] == 2
    assert shanghai["standardQjPremium"] == 7.0
    assert {row["label"] for row in standard["byOrgBusinessLine"]} == {
        "上海 / OTO",
        "上海 / 证保",
        "北京 / 证保",
    }
    assert any(row["month"] == 5 and row["label"] == "整体" and row["standardCount"] == 3 for row in standard["trend"])


def test_team_enhanced_standard_manpower_2026_product_4281_uses_full_qj(tmp_path, monkeypatch):
    from db import connection
    import db as db_module
    from db.repositories import team_enhanced
    from db.repositories.team_enhanced import get_team_enhanced_analysis

    db_path = tmp_path / "team_enhanced_4281.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(team_enhanced, "init_db", lambda: None)

    with connection.get_db() as conn:
        conn.execute(
            """CREATE TABLE hr_data (
                "统计年" INTEGER, "统计月" INTEGER, "销售机构名称" TEXT,
                "业务模式名称" TEXT, "职等" TEXT, "人员代码" TEXT,
                "月末司龄区间" TEXT, "月初在职人力" INTEGER, "月末在职人力" INTEGER
            )"""
        )
        conn.execute(
            """CREATE TABLE performance (
                "年" INTEGER, "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT,
                "人员工号" TEXT, "投保单号" TEXT, "产品代码" TEXT,
                "期交保费" REAL, "折算保费" REAL
            )"""
        )
        conn.executemany(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, 5, "上海", "OTO", "F1", "A001", "1年以内", 1, 1),
                (2026, 5, "上海", "OTO", "F1", "A002", "1年以内", 1, 1),
                (2027, 5, "上海", "OTO", "F1", "A003", "1年以内", 1, 1),
            ],
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (2026, "202605", "OTO", "上海", "A001", "P1", "4281.0", 20000, 2000),
                (2026, "202605", "OTO", "上海", "A002", "P2", "9999", 20000, 2000),
                (2027, "202705", "OTO", "上海", "A003", "P3", "4281", 20000, 2000),
            ],
        )
        conn.commit()

    result_2026 = get_team_enhanced_analysis(2026, period_type="month", period_value=5, business_lines=["OTO"])
    standard_2026 = result_2026["standardManpower"]["summary"][0]
    assert standard_2026["trackedHeadcount"] == 2
    assert standard_2026["standardCount"] == 1
    assert standard_2026["standardQjPremium"] == 2.0
    assert standard_2026["standardPremium"] == 2.0

    result_2027 = get_team_enhanced_analysis(2027, period_type="month", period_value=5, business_lines=["OTO"])
    standard_2027 = result_2027["standardManpower"]["summary"][0]
    assert standard_2027["trackedHeadcount"] == 1
    assert standard_2027["standardCount"] == 0
