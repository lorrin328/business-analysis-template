"""产品分类配置 API — 商保年金 / 保障类产品可配置化。"""
import logging

import pandas as pd
from fastapi import APIRouter, Body, Depends, HTTPException

from auth import require_admin
from config.business_lines import CHANNEL_MAP
from db import get_db
from db.repository import replace_rows_incremental
from etl.aggregates.org import aggregate_org_performance
from services.response import success_response

router = APIRouter(prefix="/api", tags=["product-config"])

logger = logging.getLogger("business-analysis")


def _compact_period_expr(column: str) -> str:
    quoted = '"' + column.replace('"', '""') + '"'
    expr = f'CAST({quoted} AS TEXT)'
    for token in ['-', '/', '.', '\u5e74', '\u6708', '\u65e5', ' ', ':']:
        expr = f"replace({expr}, '{token}', '')"
    return expr


def _auto_extract_from_performance(conn) -> int:
    """当 product_config 为空时，从 performance 原始表自动提取年份≥2026的产品列表。"""
    c = conn.cursor()

    # 检查 performance 表是否存在
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='performance'")
    if not c.fetchone():
        return 0

    period_expr = _compact_period_expr('年月')

    # 检查是否有 2026 年及以后的数据，兼容 202605、2026-05、2026/05/01 等格式。
    c.execute(f"SELECT COUNT(*) FROM performance WHERE CAST(substr({period_expr}, 1, 4) AS INTEGER) >= 2026 LIMIT 1")
    if c.fetchone()[0] == 0:
        return 0

    c.execute(f'''
        SELECT DISTINCT
            CAST("产品代码" AS TEXT) as product_code,
            COALESCE(NULLIF(TRIM("产品名称"), ''), '') as product_name,
            COALESCE(NULLIF(TRIM("业务模式"), ''), '') as business_type
        FROM performance
        WHERE CAST(substr({period_expr}, 1, 4) AS INTEGER) >= 2026
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


def _auto_extract_from_jingdai(conn) -> int:
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jingdai'")
    if not c.fetchone():
        return 0

    period_expr = _compact_period_expr('时间')
    c.execute(f"SELECT COUNT(*) FROM jingdai WHERE CAST(substr({period_expr}, 1, 4) AS INTEGER) >= 2026 LIMIT 1")
    if c.fetchone()[0] == 0:
        return 0

    c.execute(f'''
        SELECT DISTINCT COALESCE(NULLIF(TRIM("产品名称"), ''), '') AS product_name
        FROM jingdai
        WHERE CAST(substr({period_expr}, 1, 4) AS INTEGER) >= 2026
          AND "产品名称" IS NOT NULL
          AND TRIM("产品名称") != ''
        ORDER BY product_name
    ''')

    inserted = 0
    for row in c.fetchall():
        name = row["product_name"].strip()
        c.execute('''
            INSERT OR IGNORE INTO product_config (product_code, product_name, business_type)
            VALUES (?, ?, '经代')
        ''', (name, name))
        if c.rowcount > 0:
            inserted += 1

    conn.commit()
    return inserted


def _recalc_org_performance_from_raw() -> int:
    """从 performance 原始表重新计算 agg_org_performance。

    保存 product_config 后调用，使商保年金 / 保障类产品指标立即生效。
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='performance'")
        if not c.fetchone():
            return 0
        c.execute("SELECT COUNT(*) FROM performance LIMIT 1")
        if c.fetchone()[0] == 0:
            return 0

        df = pd.read_sql_query('SELECT * FROM performance', conn)

    if df.empty:
        return 0

    rows = aggregate_org_performance(df)

    with get_db() as conn:
        replace_rows_incremental(conn, 'agg_org_performance', rows)
        conn.commit()

    return len(rows)


def _recalc_jingdai_from_raw() -> int:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jingdai'")
        if not c.fetchone():
            return 0
        c.execute("SELECT COUNT(*) FROM jingdai LIMIT 1")
        if c.fetchone()[0] == 0:
            return 0
        df = pd.read_sql_query('SELECT * FROM jingdai', conn)

    if df.empty:
        return 0

    from etl.aggregates.jingdai import aggregate_jingdai
    rows = aggregate_jingdai(df)
    with get_db() as conn:
        replace_rows_incremental(conn, 'agg_jingdai', rows)
        conn.commit()
    return len(rows)


@router.get("/product-config")
def get_product_config():
    """返回所有产品配置列表（按产品代码排序）。

    若 product_config 表为空，自动从 performance 原始表提取年份≥2026的产品列表。
    """
    with get_db() as conn:
        c = conn.cursor()
        inserted = _auto_extract_from_performance(conn) + _auto_extract_from_jingdai(conn)
        if inserted > 0:
            logger.info("auto-extracted %s products from raw tables to product_config", inserted)

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

    保存后自动从 performance 原始表重新计算 agg_org_performance，使配置立即生效。
    Payload: {"products": [{"product_code": "...", "is_annuity": "Y/N", "is_protection": "Y/N"}]}
    """
    products = payload.get("products", [])
    if not isinstance(products, list):
        raise HTTPException(status_code=400, detail="products must be a list")

    valid_values = {"Y", "N"}
    updated = 0
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
                INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection, updated_at)
                VALUES (?, COALESCE(?, ''), COALESCE(?, ''), ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(product_code) DO UPDATE SET
                    is_annuity = excluded.is_annuity,
                    is_protection = excluded.is_protection,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                str(code).strip(),
                item.get("product_name"),
                item.get("business_type"),
                annuity,
                protection,
            ))
            updated += 1
        conn.commit()

    # 重新计算机构业绩聚合表
    recalc_count = _recalc_org_performance_from_raw() + _recalc_jingdai_from_raw()
    if recalc_count > 0:
        logger.info("recalculated %s agg_org_performance rows after product-config update", recalc_count)

    return success_response(
        {"updated": updated, "recalculated": recalc_count},
        message="产品配置已保存" + (f"，已重新计算 {recalc_count} 条机构业绩数据" if recalc_count else ""),
        meta={"metric": "product-config", "unit": "-"},
    )
