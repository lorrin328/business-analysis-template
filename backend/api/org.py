from fastapi import APIRouter, Depends

from auth import require_permission
from api.params import AsOfQuery, DashboardYearQuery, DateQuery, RangeTypeQuery
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_org_kpi_data
from services.response import response_meta, success_response

router = APIRouter(prefix="/api", tags=["org"])


@router.get("/org-analysis")
def org_analysis(
    year: DashboardYearQuery = DEFAULT_YEAR,
    asOf: AsOfQuery = None,
    rangeType: RangeTypeQuery = None,
    startDate: DateQuery = None,
    endDate: DateQuery = None,
    _user=Depends(require_permission("org")),
):
    return success_response(
        get_org_kpi_data(
            year,
            as_of=asOf,
            range_type=rangeType,
            start_date=startDate,
            end_date=endDate,
        ),
        meta=response_meta(
            metric="org-analysis",
            unit="万元",
            data_source="agg_org_*, agg_longterm_qj",
            year=year,
            asOf=asOf,
            rangeType=rangeType,
            startDate=startDate,
            endDate=endDate,
            definitions={
                k: METRICS[k]
                for k in ["achievement_rate", "yoy", "avg_premium", "avg_productivity"]
                if k in METRICS
            },
        ),
    )
