from fastapi import APIRouter, Query

from database import get_org_kpi_data
from services.response import success_response

router = APIRouter(prefix="/api", tags=["org"])


@router.get("/org-analysis")
def org_analysis(year: int = Query(2026, ge=2000, le=2100)):
    return success_response(
        get_org_kpi_data(year),
        meta={"year": year, "metric": "org-analysis", "unit": "万元", "dataSource": "agg_org_*"},
    )
