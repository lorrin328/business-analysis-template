import sqlite3


def test_honor_staff_category_schema_and_historical_backfill(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db import init_db

    db_path = tmp_path / "honor_staff_category.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''
            INSERT INTO honor_source_staff_month
                (batch_id, year, month, org, business_line, staff_code, staff_name, role_type)
            VALUES (1, 2026, 7, '上海', 'OTO', '2001', '李主管', '主管')
            '''
        )
        conn.execute(
            '''
            INSERT INTO honor_person_month
                (batch_id, year, month, org, business_line, staff_code, staff_name, role_type)
            VALUES (1, 2026, 7, '上海', 'OTO', '2001', '李主管', '个人')
            '''
        )
        conn.execute(
            '''
            INSERT INTO honor_person_summary
                (batch_id, year, latest_month, org, business_line, staff_code, staff_name, role_type)
            VALUES (1, 2026, 7, '上海', 'OTO', '2001', '李主管', '个人')
            '''
        )
        conn.commit()

    init_db()

    with sqlite3.connect(db_path) as conn:
        source_category = conn.execute(
            "SELECT staff_category FROM honor_source_staff_month WHERE staff_code = '2001'"
        ).fetchone()[0]
        month_category = conn.execute(
            "SELECT staff_category FROM honor_person_month WHERE staff_code = '2001'"
        ).fetchone()[0]
        summary_category = conn.execute(
            "SELECT staff_category FROM honor_person_summary WHERE staff_code = '2001'"
        ).fetchone()[0]

    assert source_category == "外勤管理职"
    assert month_category == "外勤管理职"
    assert summary_category == "外勤管理职"
