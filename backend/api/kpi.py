from fastapi import APIRouter, Depends, Query

from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_kpi_data
from services.response import success_response

router = APIRouter(prefix="/api", tags=["kpi"])


@router.get("/kpi")
def kpi(
    year: int = Query(DEFAULT_YEAR, ge=2000, le=2100),
    asOf: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user=Depends(require_permission("kpi")),
):
    return success_response(
        get_kpi_data(year, as_of=asOf),
        meta={
            "year": year,
            "asOf": asOf,
            "metric": "kpi",
            "unit": "万元/%",
            "dataSource": "SQLite aggregate tables",
            "definitions": METRICS,
        },
    )


@router.get("/kpi-definitions")
def kpi_definitions(_user=Depends(require_permission("kpi"))):
    """返回 KPI 模块涉及的所有指标定义与口径。"""
    return success_response(
        METRICS,
        meta={"metric": "kpi-definitions", "unit": "-", "dataSource": "config/metrics.py"},
    )
