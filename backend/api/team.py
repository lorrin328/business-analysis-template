from fastapi import APIRouter, Query

from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_platform_data
from services.response import success_response

router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team-analysis")
def team_analysis(year: int = Query(DEFAULT_YEAR, ge=2000, le=2100)):
    data = get_platform_data(year)
    return success_response(
        {"year": year, "hr": data.get("hr", [])},
        meta={
            "year": year,
            "metric": "team-analysis",
            "unit": "人/万元",
            "dataSource": "agg_hr_data",
            "definitions": {
                k: METRICS[k]
                for k in ["activity_rate", "avg_premium", "avg_productivity"]
                if k in METRICS
            },
        },
    )
