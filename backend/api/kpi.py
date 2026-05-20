from fastapi import APIRouter, Query

from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_kpi_data
from services.response import success_response

router = APIRouter(prefix="/api", tags=["kpi"])


@router.get("/kpi")
def kpi(year: int = Query(DEFAULT_YEAR, ge=2000, le=2100)):
    return success_response(
        get_kpi_data(year),
        meta={
            "year": year,
            "metric": "kpi",
            "unit": "万元/%",
            "dataSource": "SQLite aggregate tables",
            "definitions": METRICS,
        },
    )
