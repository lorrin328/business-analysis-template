"""Tests for /api/product-config endpoint."""
import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from main import app
from db import get_kpi_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_product_config_db(tmp_path, monkeypatch):
    db_path = tmp_path / "product_config_test.db"

    import db as db_module
    import db.connection as connection
    from db import init_db

    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    init_db()

    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS performance")
    conn.execute(
        """
        CREATE TABLE performance (
            "年月" TEXT,
            "业务模式" TEXT,
            "销售机构名称" TEXT,
            "产品类型" TEXT,
            "产品代码" TEXT,
            "产品名称" TEXT,
            "期交保费" REAL DEFAULT 0,
            "年化规保" REAL DEFAULT 0,
            "规模保费" REAL DEFAULT 0,
            "承保件数" INTEGER DEFAULT 0,
            "缴费年限" TEXT
        )
        """
    )
    conn.execute("DROP TABLE IF EXISTS jingdai")
    conn.execute(
        """
        CREATE TABLE jingdai (
            "时间" TEXT,
            "当前缴别大类" TEXT,
            "缴费年限范围" TEXT,
            "缴费年限" REAL,
            "产品名称" TEXT,
            "经代机构" TEXT,
            "承保年化规保" REAL,
            "期交保费" REAL
        )
        """
    )
    conn.commit()
    conn.close()

    yield


class TestProductConfig:
    def test_get_product_config_empty_when_both_empty(self):
        """product_config 和 performance 均为空时返回空列表。"""
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM product_config")
        conn.execute("DELETE FROM performance")
        conn.commit()
        conn.close()
        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []

    def test_product_config_does_not_auto_extract_transform_products(self, monkeypatch):
        """转型产品分类来自业绩基表标识，不再进入参数设置。"""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("DELETE FROM product_config")
        # 确保 performance 表有 2026 年数据
        c.execute('''
            INSERT OR IGNORE INTO performance
            ("年月", "业务模式", "产品代码", "产品名称", "期交保费")
            VALUES (?, ?, ?, ?, ?)
        ''', ("2026-01-01 00:00:00", "OTO", "AUTO999", "自动提取产品", 1000))
        conn.commit()
        conn.close()

        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []

        # 清理
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM performance WHERE CAST("产品代码" AS TEXT) = ?', ("AUTO999",))
        c.execute('DELETE FROM product_config WHERE product_code = ?', ("AUTO999",))
        conn.commit()
        conn.close()

    def test_product_config_ignores_compact_yyyymm_transform_products(self, monkeypatch):
        """即使转型年月可识别，也不自动进入经代参数设置。"""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("DELETE FROM product_config")
        c.execute('''
            INSERT OR IGNORE INTO performance
            ("年月", "业务模式", "产品代码", "产品名称", "期交保费")
            VALUES (?, ?, ?, ?, ?)
        ''', ("202605", "OTO", "AUTO998", "紧凑年月产品", 1000))
        conn.commit()
        conn.close()

        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM performance WHERE CAST("产品代码" AS TEXT) = ?', ("AUTO998",))
        c.execute('DELETE FROM product_config WHERE product_code = ?', ("AUTO998",))
        conn.commit()
        conn.close()

    def test_auto_extract_includes_jingdai_products(self, monkeypatch):
        """经代产品没有产品代码时，使用产品名称作为配置键列示出来。"""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM product_config")
        c.execute('''
            INSERT INTO jingdai
            ("时间", "产品名称", "经代机构", "承保年化规保", "期交保费")
            VALUES (?, ?, ?, ?, ?)
        ''', ("202605", "经代年金产品A", "支付宝", 10000, 10000))
        conn.commit()
        conn.close()

        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        products = resp.json()["data"]
        jd_product = next((p for p in products if p["product_code"] == "经代年金产品A"), None)
        assert jd_product is not None
        assert jd_product["product_name"] == "经代年金产品A"
        assert jd_product["business_type"] == "经代"
        assert jd_product["is_annuity"] == "N"
        assert jd_product["is_protection"] == "N"

    def test_post_triggers_recalc_when_jingdai_empty(self, monkeypatch):
        """保存配置时若 jingdai 表为空，recalculated 为 0。"""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("DELETE FROM product_config")
        c.execute("DELETE FROM jingdai")
        c.execute("""
            INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
            VALUES (?, ?, ?, ?, ?)
        """, ("RECALC01", "测试产品", "经代", "N", "N"))
        conn.commit()
        conn.close()

        resp = client.post(
            "/api/product-config",
            json={"products": [{"product_code": "RECALC01", "is_annuity": "Y", "is_protection": "Y"}]},
            headers={"X-Admin-Token": "test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["updated"] == 1
        # jingdai 表为空，无法重新聚合
        assert data["data"]["recalculated"] == 0

        # 清理
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM product_config WHERE product_code = ?', ("RECALC01",))
        conn.commit()
        conn.close()

    def test_post_and_get_product_config(self, monkeypatch):
        """保存配置后能正确读取。"""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        # 先通过 DB 直接插入测试数据（模拟导入时自动提取）
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("DELETE FROM product_config")
        c.execute("""
            INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
            VALUES (?, ?, ?, ?, ?)
        """, ("TEST002", "测试产品B", "经代", "Y", "N"))
        conn.commit()
        conn.close()

        # GET 验证
        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["product_code"] == "TEST002"
        assert data[0]["business_type"] == "经代"
        assert data[0]["is_annuity"] == "Y"

        # POST 修改配置
        resp = client.post(
            "/api/product-config",
            json={"products": [
                {"product_code": "TEST002", "is_annuity": "N", "is_protection": "N"},
            ]},
            headers={"X-Admin-Token": "test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 再次 GET 验证修改已生效
        resp = client.get("/api/product-config")
        data = resp.json()["data"]
        test002 = next(p for p in data if p["product_code"] == "TEST002")
        assert test002["is_annuity"] == "N"
        assert test002["is_protection"] == "N"

    def test_same_product_code_can_have_different_business_type_config(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM product_config")
        c.execute("""
            INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
            VALUES (?, ?, ?, ?, ?)
        """, ("SAME001", "同码OTO产品", "OTO", "N", "N"))
        c.execute("""
            INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
            VALUES (?, ?, ?, ?, ?)
        """, ("SAME001", "同码经代产品", "经代", "N", "N"))
        conn.commit()
        conn.close()

        resp = client.post(
            "/api/product-config",
            json={"products": [
                {"product_code": "SAME001", "business_type": "OTO", "is_annuity": "Y", "is_protection": "N"},
                {"product_code": "SAME001", "business_type": "经代", "is_annuity": "N", "is_protection": "Y"},
            ]},
            headers={"X-Admin-Token": "test-token"},
        )
        assert resp.status_code == 200

        resp = client.get("/api/product-config")
        rows = [p for p in resp.json()["data"] if p["product_code"] == "SAME001"]
        assert len(rows) == 1
        by_type = {p["business_type"]: p for p in rows}
        assert by_type["经代"]["is_annuity"] == "N"
        assert by_type["经代"]["is_protection"] == "Y"

    def test_meta_includes_definitions(self):
        resp = client.get("/api/product-config")
        data = resp.json()
        assert "meta" in data
        assert data["meta"]["metric"] == "product-config"

    def test_kpi_returns_configured_protection_total(self):
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        try:
            c = conn.cursor()
            for table in ["agg_org_performance", "agg_performance", "agg_jingdai", "agg_hr_data", "agg_value_data", "agg_payment_period"]:
                c.execute(f"DELETE FROM {table} WHERE year = 2097")
            c.execute(
                """
                INSERT INTO agg_performance (year, month, channel, qj_premium, gm_premium, zs_premium)
                VALUES (2097, 1, 'OTO', 10, 10, 10)
                """
            )
            c.execute(
                """
                INSERT INTO agg_jingdai (year, month, qj_premium, gm_premium, zs_premium)
                VALUES (2097, 1, 0, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_hr_data (year, month, channel, start_headcount, end_headcount, active_headcount)
                VALUES (2097, 1, 'OTO', 1, 1, 1)
                """
            )
            c.execute(
                """
                INSERT INTO agg_value_data (year, month, channel, value_premium)
                VALUES (2097, 1, 'OTO', 1)
                """
            )
            c.execute(
                """
                INSERT INTO agg_org_performance
                (year, month, org, channel, qj_premium, gm_premium, zs_premium, product_10year, product_annuity, product_protection)
                VALUES (2097, 1, '上海', 'OTO', 10, 10, 10, 2, 3, 4)
                """
            )
            c.execute(
                """
                INSERT INTO agg_payment_period
                (year, month, business_type, channel, org, category, qj_premium, gm_premium, count)
                VALUES (2097, 1, '经代', '', '支付宝', '10年及以上', 5, 5, 0)
                """
            )
            conn.commit()

            data = get_kpi_data(2097)
            assert data["annuity_total"] == 3
            assert data["protection_total"] == 4
            assert data["tenyear_tf"] == 2
            assert data["tenyear_jd"] == 5
            assert data["tenyear_total"] == 7
        finally:
            conn.execute("DELETE FROM agg_org_performance WHERE year = 2097")
            conn.execute("DELETE FROM agg_performance WHERE year = 2097")
            conn.execute("DELETE FROM agg_jingdai WHERE year = 2097")
            conn.execute("DELETE FROM agg_hr_data WHERE year = 2097")
            conn.execute("DELETE FROM agg_value_data WHERE year = 2097")
            conn.execute("DELETE FROM agg_payment_period WHERE year = 2097")
            conn.commit()
            conn.close()

    def test_kpi_product_totals_follow_daily_as_of_cutoff(self):
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        try:
            c = conn.cursor()
            for table in [
                "agg_performance", "agg_daily_performance",
                "agg_org_performance", "agg_org_daily_performance",
                "agg_jingdai", "agg_jingdai_daily",
            ]:
                c.execute(f"DELETE FROM {table} WHERE year = 2098")
            c.execute(
                """
                INSERT INTO agg_performance (year, month, channel, qj_premium, gm_premium, zs_premium)
                VALUES (2098, 6, 'OTO', 300, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_daily_performance (year, month, day, channel, qj_premium, gm_premium, zs_premium)
                VALUES
                    (2098, 6, 18, 'OTO', 30, 0, 0),
                    (2098, 6, 28, 'OTO', 60, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_org_performance
                (year, month, org, channel, qj_premium, gm_premium, zs_premium, product_10year, product_annuity, product_protection)
                VALUES (2098, 6, '上海', 'OTO', 300, 0, 0, 80, 100, 200)
                """
            )
            c.execute(
                """
                INSERT INTO agg_org_daily_performance
                (year, month, day, org, channel, qj_premium, gm_premium, zs_premium, product_10year, product_annuity, product_protection)
                VALUES
                    (2098, 6, 18, '上海', 'OTO', 30, 0, 0, 8, 10, 20),
                    (2098, 6, 28, '上海', 'OTO', 60, 0, 0, 18, 30, 40)
                """
            )
            c.execute(
                """
                INSERT INTO agg_jingdai
                (year, month, qj_premium, gm_premium, zs_premium, product_annuity, product_protection)
                VALUES (2098, 6, 50, 0, 0, 5, 6)
                """
            )
            c.execute(
                """
                INSERT INTO agg_jingdai_daily
                (year, month, day, qj_premium, gm_premium, zs_premium, product_annuity, product_protection)
                VALUES
                    (2098, 6, 18, 5, 0, 0, 1, 2),
                    (2098, 6, 28, 9, 0, 0, 3, 4)
                """
            )
            conn.commit()

            data = get_kpi_data(2098, as_of="2098-06-18")

            assert data["annuity_tf"] == 10
            assert data["annuity_jd"] == 1
            assert data["annuity_total"] == 11
            assert data["protection_tf"] == 20
            assert data["protection_jd"] == 2
            assert data["protection_total"] == 22
            assert data["tenyear_tf"] == 8
        finally:
            for table in [
                "agg_performance", "agg_daily_performance",
                "agg_org_performance", "agg_org_daily_performance",
                "agg_jingdai", "agg_jingdai_daily",
            ]:
                conn.execute(f"DELETE FROM {table} WHERE year = 2098")
            conn.commit()
            conn.close()

    def test_kpi_uses_common_daily_cutoff_for_transform_and_jingdai(self):
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        try:
            c = conn.cursor()
            for table in [
                "agg_daily_performance", "agg_jingdai_daily", "agg_performance",
                "agg_jingdai", "agg_hr_data", "agg_value_data", "agg_longterm_qj",
            ]:
                c.execute(f"DELETE FROM {table} WHERE year = 2095")
            c.execute(
                """
                INSERT INTO agg_performance (year, month, channel, qj_premium, gm_premium, zs_premium)
                VALUES (2095, 5, 'OTO', 999, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_jingdai (year, month, qj_premium, gm_premium, zs_premium)
                VALUES (2095, 5, 999, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_hr_data (year, month, channel, start_headcount, end_headcount, active_headcount)
                VALUES (2095, 5, 'OTO', 1, 1, 1)
                """
            )
            c.execute(
                """
                INSERT INTO agg_value_data (year, month, channel, value_premium)
                VALUES (2095, 5, 'OTO', 1)
                """
            )
            c.execute(
                """
                INSERT INTO agg_daily_performance
                    (year, month, day, channel, qj_premium, gm_premium, zs_premium)
                VALUES
                    (2095, 5, 13, 'OTO', 10, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_jingdai_daily
                    (year, month, day, qj_premium, gm_premium, zs_premium)
                VALUES
                    (2095, 5, 13, 20, 0, 0),
                    (2095, 5, 20, 30, 0, 0)
                """
            )
            c.execute(
                """
                INSERT INTO agg_longterm_qj
                    (year, month, day, business_type, channel, org, qj_premium)
                VALUES
                    (2095, 5, 13, '转型', 'OTO', '上海', 8),
                    (2095, 5, 14, '转型', 'OTO', '上海', 999),
                    (2095, 5, 13, '经代', '', '支付宝', 18),
                    (2095, 5, 20, '经代', '', '支付宝', 28)
                """
            )
            conn.commit()

            data = get_kpi_data(2095)
            assert data["daily_cutoff"]["month"] == 5
            assert data["daily_cutoff"]["day"] == 20
            assert data["daily_cutoff"]["common"] == {"month": 5, "day": 13}
            assert data["daily_cutoff"]["transform"] == {"month": 5, "day": 13}
            assert data["daily_cutoff"]["jingdai"] == {"month": 5, "day": 20}
            assert data["qj_premium"]["oto"] == 10
            assert data["qj_premium"]["jingdai"] == 50
            assert data["qj_premium"]["total"] == 60
            assert data["longterm_qj_tf"] == 8
            assert data["longterm_qj_jd"] == 46
            assert data["longterm_qj"] == 54
            assert data["longterm_qj"] < data["qj_premium"]["total"]
        finally:
            for table in [
                "agg_daily_performance", "agg_jingdai_daily", "agg_performance",
                "agg_jingdai", "agg_hr_data", "agg_value_data", "agg_longterm_qj",
            ]:
                conn.execute(f"DELETE FROM {table} WHERE year = 2095")
            conn.commit()
            conn.close()

    def test_kpi_includes_configured_jingdai_product_categories(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        try:
            c = conn.cursor()
            c.execute("DELETE FROM product_config")
            for table in ["agg_jingdai", "agg_performance", "agg_hr_data", "agg_value_data", "jingdai"]:
                c.execute(f"DELETE FROM {table} WHERE year = 2096" if table.startswith("agg_") else f"DELETE FROM {table}")
            c.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, '经代', 'Y', 'Y')
                """,
                ("经代保障年金", "经代保障年金"),
            )
            c.execute(
                """
                INSERT INTO jingdai ("时间", "产品名称", "经代机构", "承保年化规保", "期交保费")
                VALUES (?, ?, ?, ?, ?)
                """,
                ("209601", "经代保障年金", "支付宝", 10000, 10000),
            )
            conn.commit()

            resp = client.post(
                "/api/product-config",
                json={"products": [{"product_code": "经代保障年金", "is_annuity": "Y", "is_protection": "Y"}]},
                headers={"X-Admin-Token": "test-token"},
            )
            assert resp.status_code == 200

            data = get_kpi_data(2096)
            assert data["annuity_jd"] == 1
            assert data["protection_jd"] == 1
            assert data["annuity_total"] == 1
            assert data["protection_total"] == 1
        finally:
            for table in ["agg_jingdai", "agg_performance", "agg_hr_data", "agg_value_data"]:
                conn.execute(f"DELETE FROM {table} WHERE year = 2096")
            conn.execute("DELETE FROM jingdai")
            conn.execute("DELETE FROM product_config")
            conn.commit()
            conn.close()

    def test_product_config_merges_decimal_duplicate_codes(self, monkeypatch):
        """4281 and 4281.0 should be one configurable product, with Y flags preserved."""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        try:
            c = conn.cursor()
            c.execute("DELETE FROM product_config")
            c.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("4281", "产品4281", "经代", "N", "N"),
            )
            c.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("4281.0", "产品4281小数", "经代", "Y", "Y"),
            )
            conn.commit()

            resp = client.get("/api/product-config")
            assert resp.status_code == 200
            rows = [r for r in resp.json()["data"] if r["business_type"] == "经代" and r["product_code"] == "4281"]
            assert len(rows) == 1
            assert rows[0]["is_annuity"] == "Y"
            assert rows[0]["is_protection"] == "Y"

            count = conn.execute(
                "SELECT COUNT(*) FROM product_config WHERE business_type = '经代' AND product_code IN ('4281', '4281.0')"
            ).fetchone()[0]
            assert count == 1
        finally:
            conn.execute("DELETE FROM product_config")
            conn.commit()
            conn.close()

    def test_product_config_save_normalizes_decimal_code(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM product_config")
            conn.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("4281", "产品4281", "经代", "N", "N"),
            )
            conn.commit()

            resp = client.post(
                "/api/product-config",
                json={"products": [{"product_code": "4281.0", "business_type": "经代", "is_annuity": "Y", "is_protection": "N"}]},
                headers={"X-Admin-Token": "test-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["normalized"] == 0

            row = conn.execute(
                "SELECT product_code, is_annuity, is_protection FROM product_config WHERE business_type = '经代'"
            ).fetchone()
            assert row[0] == "4281"
            assert row[1] == "Y"
            assert row[2] == "N"
        finally:
            conn.execute("DELETE FROM product_config")
            conn.commit()
            conn.close()

    def test_product_config_filters_nan_code_and_name(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        from db import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM product_config")
            conn.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("nan", "nan", "经代", "N", "N"),
            )
            conn.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("NAN001", "nan", "经代", "N", "N"),
            )
            conn.commit()

            resp = client.get("/api/product-config")
            assert resp.status_code == 200
            rows = resp.json()["data"]
            assert not any(str(r["product_code"]).lower() == "nan" for r in rows)
            nan001 = next(r for r in rows if r["product_code"] == "NAN001")
            assert nan001["product_name"] == ""
        finally:
            conn.execute("DELETE FROM product_config")
            conn.commit()
            conn.close()

    def test_aggregate_product_category_uses_transform_excel_flags(self, monkeypatch):
        """转型商保年金和保障类产品直接读取业绩基表标识，不读取 product_config。"""
        monkeypatch.setenv("ADMIN_TOKEN", "test-token")

        import pandas as pd
        from db import DB_PATH
        from etl.aggregates.org import aggregate_org_performance

        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM product_config")
            conn.execute(
                """
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("4281.0", "产品4281", "OTO", "N", "N"),
            )
            conn.commit()

            df = pd.DataFrame([{
                "年": 2097,
                "年月": "209701",
                "业务模式": "OTO",
                "销售机构名称": "上海",
                "产品代码": "4281",
                "产品名称": "产品4281",
                "期交保费": 10000,
                "缴费年限": 10,
                "是否商保年金产品": "是",
                "是否社会保障型产品": "是",
            }])
            rows = aggregate_org_performance(df)
            assert len(rows) == 1
            assert rows[0]["product_annuity"] == 1
            assert rows[0]["product_protection"] == 1
        finally:
            conn.execute("DELETE FROM product_config")
            conn.commit()
            conn.close()

    def test_aggregate_2026_4281_counts_as_10year_product(self):
        """2026 business rule: product 4281 enters both longterm and 10-year metrics."""
        import pandas as pd
        from etl.aggregates.org import aggregate_org_performance

        df = pd.DataFrame([{
            "年": 2026,
            "年月": "202605",
            "业务模式": "OTO",
            "销售机构名称": "上海",
            "产品代码": "4281.0",
            "产品名称": "太平超e保（长享版）长期医疗保险（费率可调）",
            "期交保费": 10000,
            "缴费年限": 1,
        }, {
            "年": 2027,
            "年月": "202705",
            "业务模式": "OTO",
            "销售机构名称": "上海",
            "产品代码": "4281",
            "产品名称": "太平超e保（长享版）长期医疗保险（费率可调）",
            "期交保费": 10000,
            "缴费年限": 1,
        }])

        rows = aggregate_org_performance(df)
        by_year = {r["year"]: r for r in rows}
        assert by_year[2026]["product_10year"] == 1
        assert by_year[2027]["product_10year"] == 0
