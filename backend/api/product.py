from fastapi import APIRouter, Query

from config.business_lines import DEFAULT_YEAR
from db import get_product_structure
from services.response import success_response

router = APIRouter(prefix="/api", tags=["product"])


@router.get("/product-analysis")
def product_analysis(
    year: int = Query(DEFAULT_YEAR, ge=2000, le=2100),
    dimension: str = "product_mix",
    transformLines: str | None = None,
    jingdaiOrgs: str | None = None,
    includeTransform: bool = True,
    includeJingdai: bool = True,
    orgs: str | None = None,
    months: str | None = None,
    metric: str = Query("qj", pattern="^(qj|gm)$"),
):
    return success_response(
        get_product_structure(year, dimension, transformLines, jingdaiOrgs, includeTransform, includeJingdai, orgs, months, metric),
        meta={"year": year, "metric": "product-analysis", "unit": "万元/件", "dataSource": "performance / jingdai"},
    )
