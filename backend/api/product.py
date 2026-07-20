from fastapi import APIRouter, Depends, Query

from auth import require_permission
from api.params import AsOfQuery, DashboardYearQuery, DateQuery, RangeTypeQuery
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_product_structure
from services.response import response_meta, success_response

router = APIRouter(prefix="/api", tags=["product"])


@router.get("/product-analysis")
def product_analysis(
    year: DashboardYearQuery = DEFAULT_YEAR,
    dimension: str = "product_mix",
    transformLines: str | None = None,
    jingdaiOrgs: str | None = None,
    includeTransform: bool = True,
    includeJingdai: bool = True,
    orgs: str | None = None,
    months: str | None = None,
    metric: str = Query("qj", pattern="^(qj|gm)$"),
    asOf: AsOfQuery = None,
    rangeType: RangeTypeQuery = None,
    startDate: DateQuery = None,
    endDate: DateQuery = None,
    _user=Depends(require_permission("product_structure")),
):
    return success_response(
        get_product_structure(
            year,
            dimension,
            transformLines,
            jingdaiOrgs,
            includeTransform,
            includeJingdai,
            orgs,
            months,
            metric,
            as_of=asOf,
            range_type=rangeType,
            start_date=startDate,
            end_date=endDate,
        ),
        meta=response_meta(
            metric="product-analysis",
            unit="万元/件",
            data_source="performance / jingdai",
            year=year,
            asOf=asOf,
            rangeType=rangeType,
            startDate=startDate,
            endDate=endDate,
            definitions={
                k: METRICS[k]
                for k in ["achievement_rate", "yoy"]
                if k in METRICS
            },
        ),
    )
