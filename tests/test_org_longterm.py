import os
import sqlite3
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def test_org_analysis_returns_annual_longterm_qj_with_daily_cutoff(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db.schema import init_db
    from db.repositories.org import get_org_kpi_data

    db_path = tmp_path / "org_longterm.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agg_org_daily_performance
                (year, month, day, org, channel, qj_premium, gm_premium, zs_premium)
            VALUES
                (2098, 5, 10, '上海', 'OTO', 10, 0, 0)
            """
        )
        conn.execute(
            """
            INSERT INTO agg_longterm_qj
                (year, month, day, business_type, channel, org, qj_premium)
            VALUES
                (2098, 5, 10, '转型', 'OTO', '上海', 3),
                (2098, 5, 11, '转型', 'OTO', '上海', 99),
                (2098, 5, 10, '经代', '经代', '经代', 88)
            """
        )
        conn.commit()

    data = get_org_kpi_data(2098)

    assert data["longterm"]["上海|OTO"]["year"] == 3
    assert "经代|经代" not in data["longterm"]
    assert "上海" in data["orgs"]


def test_org_analysis_product_metrics_follow_daily_cutoff(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db.schema import init_db
    from db.repositories.org import get_org_kpi_data

    db_path = tmp_path / "org_product_daily.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agg_org_performance
                (year, month, org, channel, qj_premium, gm_premium, zs_premium, product_10year, product_annuity, product_protection)
            VALUES
                (2098, 6, '上海', 'OTO', 300, 0, 0, 80, 100, 200)
            """
        )
        conn.execute(
            """
            INSERT INTO agg_org_daily_performance
                (year, month, day, org, channel, qj_premium, gm_premium, zs_premium, product_10year, product_annuity, product_protection)
            VALUES
                (2098, 6, 18, '上海', 'OTO', 30, 0, 0, 8, 10, 20),
                (2098, 6, 28, '上海', 'OTO', 60, 0, 0, 18, 30, 40)
            """
        )
        conn.commit()

    data = get_org_kpi_data(2098, as_of="2098-06-18")
    year_perf = data["perf"]["上海|OTO"]["year"]

    assert year_perf["qj_premium"] == 30
    assert year_perf["product_10year"] == 8
    assert year_perf["product_annuity"] == 10
    assert year_perf["product_protection"] == 20
