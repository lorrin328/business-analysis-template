"""产品分类配置 API — 商保年金 / 保障类产品可配置化。"""
import logging

from fastapi import APIRouter, Body, Depends, HTTPException

from auth import require_admin
from config.business_lines import CHANNEL_MAP
from db import get_db
from services.response import success_response

router = APIRouter(prefix="/api", tags=["product-config"])

logger = logging.getLogger("business-analysis")


def _auto_extract_from_performance(conn) -> int:
    """当 product_config 为空时，从 performance 原始表自动提取年份≥2026的产品列表。"""
    c = conn.cursor()

    # 检查 performance 表是否存在
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='performance'")
    if not c.fetchone():
        return 0

    # 检查是否有 2026 年及以后的数据
    c.execute("SELECT COUNT(*) FROM performance WHERE strftime('%Y', \"年月\") >= '2026' LIMIT 1")
    if c.fetchone()[0] == 0:
        return 0

    c.execute('''
        SELECT DISTINCT
            CAST("产品代码" AS TEXT) as product_code,
            COALESCE(NULLIF(TRIM("产品名称"), ''), '') as product_name,
            COALESCE(NULLIF(TRIM("业务模式"), ''), '') as business_type
        FROM performance
        WHERE strftime('%Y', "年月") >= '2026'
          AND "产品代码" IS NOT NULL
          AND CAST("产品代码" AS TEXT) != ''
        ORDER BY "年月" DESC
    ''')

    inserted = 0
    for row in c.fetchall():
        code = row["product_code"].strip()
        name = row["product_name"].strip()
        channel = CHANNEL_MAP.get(row["business_type"], row["business_type"])
        c.execute('''
            INSERT OR IGNORE INTO product_config (product_code, product_name, business_type)
            VALUES (?, ?, ?)
        ''', (code, name, channel))
        if c.rowcount > 0:
            inserted += 1

    conn.commit()
    return inserted


@router.get("/product-config")
def get_product_config():
    """返回所有产品配置列表（按产品代码排序）。

    若 product_config 表为空，自动从 performance 原始表提取年份≥2026的产品列表。
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM product_config")
        count = c.fetchone()[0]

        if count == 0:
            inserted = _auto_extract_from_performance(conn)
            if inserted > 0:
                logger.info("auto-extracted %s products from performance to product_config", inserted)

        c.execute('''
            SELECT product_code, product_name, business_type, is_annuity, is_protection
            FROM product_config
            ORDER BY product_code
        ''')
        rows = [
            {
                "product_code": r["product_code"],
                "product_name": r["product_name"],
                "business_type": r["business_type"],
                "is_annuity": r["is_annuity"],
                "is_protection": r["is_protection"],
            }
            for r in c.fetchall()
        ]
    return success_response(
        rows,
        meta={"metric": "product-config", "unit": "-", "dataSource": "product_config"},
    )


@router.post("/product-config")
def save_product_config(
    payload: dict = Body(...),
    _admin=Depends(require_admin),
):
    """批量保存产品分类配置。

    Payload: {"products": [{"product_code": "...", "is_annuity": "Y/N", "is_protection": "Y/N"}]}
    """
    products = payload.get("products", [])
    if not isinstance(products, list):
        raise HTTPException(status_code=400, detail="products must be a list")

    valid_values = {"Y", "N"}
    with get_db() as conn:
        c = conn.cursor()
        for item in products:
            code = item.get("product_code")
            if not code:
                continue
            annuity = str(item.get("is_annuity", "N")).upper()
            protection = str(item.get("is_protection", "N")).upper()
            if annuity not in valid_values:
                annuity = "N"
            if protection not in valid_values:
                protection = "N"
            c.execute('''
                UPDATE product_config
                SET is_annuity = ?, is_protection = ?, updated_at = CURRENT_TIMESTAMP
                WHERE product_code = ?
            ''', (annuity, protection, code))
        conn.commit()

    return success_response(
        {"updated": len(products)},
        message="产品配置已保存",
        meta={"metric": "product-config", "unit": "-"},
    )
