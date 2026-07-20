from fastapi import APIRouter, Depends

from auth import require_permission
from api.params import AsOfQuery, DashboardYearQuery, DateQuery, RangeTypeQuery
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_kpi_data
from services.response import response_meta, success_response

router = APIRouter(prefix="/api", tags=["kpi"])


@router.get("/kpi")
def kpi(
    year: DashboardYearQuery = DEFAULT_YEAR,
    asOf: AsOfQuery = None,
    rangeType: RangeTypeQuery = None,
    startDate: DateQuery = None,
    endDate: DateQuery = None,
    _user=Depends(require_permission("kpi")),
):
    return success_response(
        get_kpi_data(
            year,
            as_of=asOf,
            range_type=rangeType,
            start_date=startDate,
            end_date=endDate,
        ),
        meta=response_meta(
            metric="kpi",
            unit="万元/%",
            data_source="SQLite aggregate tables",
            definitions=METRICS,
            year=year,
            asOf=asOf,
            rangeType=rangeType,
            startDate=startDate,
            endDate=endDate,
        ),
    )


@router.get("/kpi-definitions")
def kpi_definitions(_user=Depends(require_permission("kpi"))):
    """返回 KPI 模块涉及的所有指标定义与口径。"""
    return success_response(
        METRICS,
        meta=response_meta(metric="kpi-definitions", unit="-", data_source="config/metrics.py"),
    )
