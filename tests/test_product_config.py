"""Tests for /api/product-config endpoint."""
import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestProductConfig:
    def test_get_product_config_empty(self):
        """product_config 表为空时返回空列表。"""
        import sqlite3
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM product_config")
        conn.commit()
        conn.close()
        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []

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
        """, ("TEST001", "测试产品A", "OTO", "N", "N"))
        c.execute("""
            INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection)
            VALUES (?, ?, ?, ?, ?)
        """, ("TEST002", "测试产品B", "证保", "Y", "N"))
        conn.commit()
        conn.close()

        # GET 验证
        resp = client.get("/api/product-config")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["product_code"] == "TEST001"
        assert data[0]["is_annuity"] == "N"
        assert data[1]["product_code"] == "TEST002"
        assert data[1]["is_annuity"] == "Y"

        # POST 修改配置
        resp = client.post(
            "/api/product-config",
            json={"products": [
                {"product_code": "TEST001", "is_annuity": "Y", "is_protection": "Y"},
                {"product_code": "TEST002", "is_annuity": "N", "is_protection": "N"},
            ]},
            headers={"X-Admin-Token": "test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # 再次 GET 验证修改已生效
        resp = client.get("/api/product-config")
        data = resp.json()["data"]
        test001 = next(p for p in data if p["product_code"] == "TEST001")
        test002 = next(p for p in data if p["product_code"] == "TEST002")
        assert test001["is_annuity"] == "Y"
        assert test001["is_protection"] == "Y"
        assert test002["is_annuity"] == "N"
        assert test002["is_protection"] == "N"

    def test_meta_includes_definitions(self):
        resp = client.get("/api/product-config")
        data = resp.json()
        assert "meta" in data
        assert data["meta"]["metric"] == "product-config"
