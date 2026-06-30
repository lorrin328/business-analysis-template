from fastapi import APIRouter, Depends, Query

from auth import require_permission
from api.params import AsOfQuery, DashboardYearQuery
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_platform_data
from services.query_service import get_platform_trend
from services.response import response_meta, success_response

router = APIRouter(prefix="/api", tags=["trend"])


@router.get("/platform-data")
def platform_data(
    year: DashboardYearQuery = DEFAULT_YEAR,
    asOf: AsOfQuery = None,
    _user=Depends(require_permission("platform_trend")),
):
    return success_response(
        get_platform_data(year, as_of=asOf),
        meta=response_meta(
            metric="platform-data",
            unit="万元/人",
            data_source="SQLite aggregate tables",
            year=year,
            asOf=asOf,
            definitions={
                k: METRICS[k]
                for k in ["achievement_rate", "yoy", "time_progress", "progress_gap"]
                if k in METRICS
            },
        ),
    )


@router.get("/platform-trend")
def platform_trend(
    year: DashboardYearQuery = DEFAULT_YEAR,
    month: int | None = Query(None, ge=1, le=12),
    quarter: int | None = Query(None, ge=1, le=4),
    periodType: str = Query("year", pattern="^(year|quarter|month)$"),
    periodValue: int | None = Query(None, ge=0, le=12),
    businessLines: str | None = None,
    metric: str = Query("qj", pattern="^(qj|gm|zs)$"),
    asOf: AsOfQuery = None,
    _user=Depends(require_permission("platform_trend")),
):
    channels = [x.strip() for x in businessLines.split(",") if x.strip()] if businessLines else None
    if month:
        periodType = "month"
        periodValue = month
    elif quarter:
        periodType = "quarter"
        periodValue = quarter

    data = get_platform_trend(
        year,
        month=month,
        channels=channels,
        metric=metric,
        period_type=periodType,
        period_value=periodValue,
        as_of=asOf,
    )
    return success_response(
        data,
        meta=response_meta(
            metric=metric,
            unit="万元",
            data_source="agg_performance / agg_jingdai / agg_daily_performance / agg_jingdai_daily",
            year=year,
            periodType=data.get("periodType", periodType),
            periodValue=data.get("periodValue", periodValue or 0),
            businessLines=data.get("businessLines", []),
            asOf=asOf,
            definitions={
                k: METRICS[k]
                for k in ["yoy", "achievement_rate", "time_progress"]
                if k in METRICS
            },
        ),
    )
