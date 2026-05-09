from fastapi import APIRouter, Query

from services.query_service import get_platform_trend
from services.response import success_response

router = APIRouter(prefix="/api", tags=["trend"])


@router.get("/platform-trend")
def platform_trend(
    year: int = Query(2026, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    businessLines: str | None = None,
    metric: str = Query("qj", pattern="^(qj|gm|zs)$"),
):
    channels = [x.strip() for x in businessLines.split(",") if x.strip()] if businessLines else None
    data = get_platform_trend(year, month=month, channels=channels, metric=metric)
    return success_response(
        data,
        meta={
            "year": year,
            "periodType": "month" if month else "year",
            "periodValue": month or 0,
            "businessLines": data.get("businessLines", []),
            "metric": metric,
            "unit": "万元",
            "dataSource": "agg_daily_performance / agg_jingdai_daily",
        },
    )
