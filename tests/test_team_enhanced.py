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
    assert result["summary"]["p50"] == 2.0
    assert result["summary"]["p75"] == 3.75
    zero_band = next(row for row in result["productivityBands"] if row["label"] == "0及以下")
    assert zero_band["count"] == 1
    assert {row["label"] for row in result["percentiles"]} == {"整体", "OTO", "证保", "蚁桥"}
    assert result["tenureStructure"][0]["count"] == 2


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
