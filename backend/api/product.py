from fastapi import APIRouter, Query

from database import get_product_structure
from services.response import success_response

router = APIRouter(prefix="/api", tags=["product"])


@router.get("/product-analysis")
def product_analysis(year: int = Query(2026, ge=2000, le=2100), dimension: str = "design_cat"):
    return success_response(
        get_product_structure(year, dimension),
        meta={"year": year, "metric": "product-analysis", "unit": "万元/件", "dataSource": "agg_product_structure"},
    )
