from fastapi import APIRouter, Query

from db import get_platform_data
from services.response import success_response

router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team-analysis")
def team_analysis(year: int = Query(2026, ge=2000, le=2100)):
    data = get_platform_data(year)
    return success_response(
        {"year": year, "hr": data.get("hr", [])},
        meta={"year": year, "metric": "team-analysis", "unit": "人/万元", "dataSource": "agg_hr_data"},
    )
