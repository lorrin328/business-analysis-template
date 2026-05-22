"""产品分类配置 API — 商保年金 / 保障类产品可配置化。"""
from fastapi import APIRouter, Body, Depends, HTTPException

from auth import require_admin
from db import get_db
from services.response import success_response

router = APIRouter(prefix="/api", tags=["product-config"])


@router.get("/product-config")
def get_product_config():
    """返回所有产品配置列表（按产品代码排序）。"""
    with get_db() as conn:
        c = conn.cursor()
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
