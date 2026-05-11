"""交期结构 API — 按交期分类聚合展示保费/件数饼图。"""
from typing import Optional

from fastapi import APIRouter, Query

from db import get_payment_period_structure

router = APIRouter(tags=["payment-period"])


@router.get("/api/payment-period/{year}")
def payment_period_analysis(
    year: int,
    month: Optional[int] = Query(None),
    businessTypes: Optional[str] = Query(None),
    channels: Optional[str] = Query(None),
    orgs: Optional[str] = Query(None),
    jingdaiOrgs: Optional[str] = Query(None),
    metric: str = Query("qj"),
):
    """获取交期结构数据。

    参数：
    - year: 年份
    - month: 月份筛选（可选，季度/月度视图时传入）
    - businessTypes: 逗号分隔，如 "转型,经代"
    - channels: 逗号分隔转型渠道，如 "OTO,证保"
    - orgs: 逗号分隔转型机构
    - jingdaiOrgs: 逗号分隔经代机构
    - metric: qj=期交保费, gm=规模保费
    """
    from db import _split_csv

    return get_payment_period_structure(
        year=year,
        month=month,
        business_types=_split_csv(businessTypes) if businessTypes else None,
        channels=_split_csv(channels) if channels else None,
        orgs=_split_csv(orgs) if orgs else None,
        jingdai_orgs=_split_csv(jingdaiOrgs) if jingdaiOrgs else None,
        metric=metric or "qj",
    )
