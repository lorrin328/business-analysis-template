"""产品分类配置 API — 经代商保年金 / 保障类产品可配置化。"""
import logging

from fastapi import APIRouter, Body, Depends, HTTPException

from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from db import get_db
from db.repository import replace_rows_incremental
from metrics.business_rules import normalize_product_code
from services.product_config_service import (
    normalize_product_config_table,
    normalize_product_name,
    purge_non_jingdai_product_config,
)
from services.audit_log import log_operation
from services.operation_lock import OperationLockError, operation_lock
from services.raw_table_reader import read_raw_table_dataframe
from services.response import success_response

router = APIRouter(prefix="/api", tags=["product-config"])

logger = logging.getLogger("business-analysis")


def _compact_period_expr(column: str) -> str:
    quoted = '"' + column.replace('"', '""') + '"'
    expr = f'CAST({quoted} AS TEXT)'
    for token in ['-', '/', '.', '\u5e74', '\u6708', '\u65e5', ' ', ':']:
        expr = f"replace({expr}, '{token}', '')"
    return expr


def _auto_extract_from_jingdai(conn) -> int:
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jingdai'")
    if not c.fetchone():
        return 0

    period_expr = _compact_period_expr('时间')
    c.execute(f"SELECT COUNT(*) FROM jingdai WHERE CAST(substr({period_expr}, 1, 4) AS INTEGER) >= ? LIMIT 1", (DEFAULT_YEAR,))
    if c.fetchone()[0] == 0:
        return 0

    c.execute(f'''
        SELECT DISTINCT COALESCE(NULLIF(TRIM("产品名称"), ''), '') AS product_name
        FROM jingdai
        WHERE CAST(substr({period_expr}, 1, 4) AS INTEGER) >= ?
          AND "产品名称" IS NOT NULL
          AND TRIM("产品名称") != ''
        ORDER BY product_name
    ''', (DEFAULT_YEAR,))

    inserted = 0
    for row in c.fetchall():
        name = normalize_product_name(row["product_name"])
        if not name:
            continue
        c.execute('''
            INSERT OR IGNORE INTO product_config (product_code, product_name, business_type)
            VALUES (?, ?, '经代')
        ''', (name, name))
        if c.rowcount > 0:
            inserted += 1

    conn.commit()
    return inserted


def _recalc_jingdai_from_raw() -> int:
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jingdai'")
        if not c.fetchone():
            return 0
        c.execute("SELECT COUNT(*) FROM jingdai LIMIT 1")
        if c.fetchone()[0] == 0:
            return 0
        df = read_raw_table_dataframe(conn, 'jingdai')

    if df.empty:
        return 0

    from etl.aggregates.jingdai import aggregate_jingdai
    rows = aggregate_jingdai(df)
    with get_db() as conn:
        replace_rows_incremental(conn, 'agg_jingdai', rows)
        conn.commit()
    return len(rows)


@router.get("/product-config")
def get_product_config(_user=Depends(require_permission("product_config"))):
    """返回经代产品配置列表。

    转型业务产品分类直接读取业绩基表标识列，不在参数设置中维护。
    """
    with get_db() as conn:
        c = conn.cursor()
        inserted = _auto_extract_from_jingdai(conn)
        normalized = normalize_product_config_table(conn)
        purged = purge_non_jingdai_product_config(conn)
        if normalized or purged:
            conn.commit()
            logger.info("normalized %s duplicate and purged %s non-jingdai product_config rows", normalized, purged)
        if inserted > 0:
            logger.info("auto-extracted %s jingdai products from raw tables to product_config", inserted)

        c.execute('''
            SELECT product_code, product_name, business_type, is_annuity, is_protection
            FROM product_config
            WHERE business_type = '经代'
            ORDER BY COALESCE(business_type, ''), product_code
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
        meta={"metric": "product-config", "unit": "-", "dataSource": "product_config", "scope": "经代"},
    )


@router.post("/product-config")
def save_product_config(
    payload: dict = Body(...),
    _user=Depends(require_permission("product_config")),
):
    """批量保存产品分类配置。

    保存后自动从 jingdai 原始表重新计算 agg_jingdai，使经代配置立即生效。
    Payload: {"products": [{"product_code": "...", "is_annuity": "Y/N", "is_protection": "Y/N"}]}
    """
    try:
        with operation_lock("product-config", timeout=1.0):
            return _save_product_config_locked(payload, _user)
    except OperationLockError as exc:
        log_operation(
            "product_config",
            user=_user,
            status="failed",
            detail={"reason": "operation_locked"},
        )
        raise HTTPException(status_code=409, detail="已有导入、重建或参数重算任务正在执行，请稍后再试。") from exc


def _save_product_config_locked(payload: dict, _user: dict):
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
            code = normalize_product_code(code)
            if not code:
                continue
            item_business_type = item.get("business_type")
            if item_business_type is not None and str(item_business_type).strip() != "经代":
                continue
            annuity = str(item.get("is_annuity", "N")).upper()
            protection = str(item.get("is_protection", "N")).upper()
            if annuity not in valid_values:
                annuity = "N"
            if protection not in valid_values:
                protection = "N"
            if item_business_type is None:
                c.execute(
                    '''
                    UPDATE product_config
                    SET is_annuity = ?, is_protection = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE product_code = ? AND business_type = '经代'
                    ''',
                    (annuity, protection, code),
                )
                if c.rowcount == 0:
                    c.execute('''
                        INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection, updated_at)
                        VALUES (?, COALESCE(?, ''), '经代', ?, ?, CURRENT_TIMESTAMP)
                    ''', (code, normalize_product_name(item.get("product_name")), annuity, protection))
            else:
                c.execute('''
                    INSERT INTO product_config (product_code, product_name, business_type, is_annuity, is_protection, updated_at)
                    VALUES (?, COALESCE(?, ''), ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(business_type, product_code) DO UPDATE SET
                        product_name = COALESCE(NULLIF(excluded.product_name, ''), product_config.product_name),
                        is_annuity = excluded.is_annuity,
                        is_protection = excluded.is_protection,
                        updated_at = CURRENT_TIMESTAMP
                ''', (
                    code,
                    normalize_product_name(item.get("product_name")),
                    "经代",
                    annuity,
                    protection,
                ))
            updated += 1
        normalized = normalize_product_config_table(conn)
        purged = purge_non_jingdai_product_config(conn)
        conn.commit()

    recalc_count = _recalc_jingdai_from_raw()
    if recalc_count > 0:
        logger.info("recalculated %s agg_jingdai rows after product-config update", recalc_count)

    log_operation(
        "product_config",
        user=_user,
        detail={"updated": updated, "normalized": normalized, "purged": purged, "recalculated": recalc_count},
    )
    return success_response(
        {"updated": updated, "normalized": normalized, "purged": purged, "recalculated": recalc_count},
        message="经代产品配置已保存" + (f"，已重新计算 {recalc_count} 条经代业绩数据" if recalc_count else ""),
        meta={"metric": "product-config", "unit": "-"},
    )
