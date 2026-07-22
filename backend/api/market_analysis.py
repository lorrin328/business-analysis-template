from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_permission
from market_analysis.repository import MarketAnalysisRepository
from services.response import success_response


router = APIRouter(prefix="/api/market-analysis", tags=["market-analysis"])


def _repository() -> MarketAnalysisRepository:
    return MarketAnalysisRepository()


@router.get("/latest")
def latest(_user=Depends(require_permission("market_analysis"))):
    report = _repository().latest()
    return success_response(report, message="" if report else "暂无已发布的市场研判报告")


@router.get("/history")
def history(
    limit: int = Query(24, ge=1, le=100),
    _user=Depends(require_permission("market_analysis")),
):
    return success_response(_repository().history(limit=limit))


@router.get("/reports/{report_id}")
def report_detail(report_id: str, _user=Depends(require_permission("market_analysis"))):
    report = _repository().get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到该期市场研判报告")
    return success_response(report)


@router.get("/status")
def status(_user=Depends(require_permission("market_analysis"))):
    return success_response(_repository().status())


@router.get("/topics/{topic_key}")
def topic_timeline(
    topic_key: str,
    limit: int = Query(12, ge=1, le=36),
    _user=Depends(require_permission("market_analysis")),
):
    return success_response(_repository().topic_timeline(topic_key, limit=limit))
