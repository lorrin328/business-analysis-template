"""交期结构 API — 按交期分类聚合展示保费/件数饼图。"""
from typing import Optional

from fastapi import APIRouter, Query

from config.metrics import METRICS
from db import get_payment_period_structure

router = APIRouter(tags=["payment-period"])


@router.get("/api/payment-period/{year}")
def payment_period_analysis(
    year: int,
    month: Optional[int] = Query(None),
    months: Optional[str] = Query(None),
    businessTypes: Optional[str] = Query(None),
    channels: Optional[str] = Query(None),
    orgs: Optional[str] = Query(None),
    jingdaiOrgs: Optional[str] = Query(None),
    metric: str = Query("qj"),
):
    """获取交期结构数据。

    参数：
    - year: 年份
    - month: 单月份筛选（可选，月度视图或旧调用使用）
    - months: 多月份筛选，逗号分隔，如 "4,5,6"（季度视图使用）
    - businessTypes: 逗号分隔，如 "转型,经代"
    - channels: 逗号分隔转型渠道，如 "OTO,证保"
    - orgs: 逗号分隔转型机构
    - jingdaiOrgs: 逗号分隔经代机构
    - metric: qj=期交保费, gm=规模保费
    """
    from db import _split_csv
    from services.response import success_response
    month_list = [
        int(item) for item in _split_csv(months)
        if item.isdigit() and 1 <= int(item) <= 12
    ] if months else None

    data = get_payment_period_structure(
        year=year,
        month=month,
        months=month_list,
        business_types=_split_csv(businessTypes) if businessTypes else None,
        channels=_split_csv(channels) if channels else None,
        orgs=_split_csv(orgs) if orgs else None,
        jingdai_orgs=_split_csv(jingdaiOrgs) if jingdaiOrgs else None,
        metric=metric or "qj",
    )
    return success_response(
        data,
        meta={
            "year": str(year),
            "metric": metric or "qj",
            "unit": "万元/件",
            "dataSource": "agg_payment_period",
            "definitions": {
                k: METRICS[k]
                for k in ["achievement_rate", "yoy"]
                if k in METRICS
            },
        },
    )
