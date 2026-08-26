"""职拓业务分析 API。"""
from fastapi import APIRouter, Depends, Query

from auth import require_permission
from db.repositories.zhituo import get_zhituo_analysis
from services.response import response_meta, success_response


router = APIRouter(prefix="/api/zhituo-analysis", tags=["zhituo-analysis"])


@router.get("/overview")
def zhituo_overview(
    years: str | None = Query(None, max_length=200),
    months: str | None = Query(None, max_length=100),
    orgs: str | None = Query(None, max_length=2000),
    _user=Depends(require_permission("kpi")),
):
    return success_response(
        get_zhituo_analysis(years=years, months=months, orgs=orgs),
        meta=response_meta(
            metric="zhituo-analysis",
            unit="万元/件/人",
            data_source="SQLite agg_zhituo_performance",
            definitions={
                "scope": "业绩基表是否职拓=是",
                "premium": "期交保费和年化规保均按源数据净额汇总",
                "policyCount": "承保件数净额；不使用数据行数替代",
            },
        ),
    )
