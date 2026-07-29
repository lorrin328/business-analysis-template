from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_admin, require_permission
from market_analysis.repository import MarketAnalysisRepository
from services.audit_log import log_operation
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


@router.post("/run", status_code=202)
def run_now(admin=Depends(require_admin)):
    trigger_file = Path(
        os.getenv(
            "MARKET_ANALYSIS_TRIGGER_FILE",
            "/run/business-analysis-market-trigger/request",
        )
    )
    if not trigger_file.parent.is_dir():
        log_operation(
            "market_analysis_manual_run",
            user=admin,
            status="failed",
            detail={"reason": "trigger_unavailable"},
        )
        raise HTTPException(status_code=503, detail="手动运行触发器尚未安装")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(trigger_file, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "requestedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                },
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
    except FileExistsError as exc:
        log_operation(
            "market_analysis_manual_run",
            user=admin,
            status="rejected",
            detail={"reason": "request_pending"},
        )
        raise HTTPException(status_code=409, detail="已有手动运行请求正在排队") from exc
    except OSError as exc:
        log_operation(
            "market_analysis_manual_run",
            user=admin,
            status="failed",
            detail={"reason": "trigger_write_failed", "errno": exc.errno},
        )
        raise HTTPException(status_code=503, detail="手动运行请求提交失败") from exc

    log_operation(
        "market_analysis_manual_run",
        user=admin,
        detail={"state": "queued"},
    )
    return success_response(
        {
            "state": "queued",
            "message": "手动研究任务已提交，后台将开始执行",
        }
    )


@router.get("/topics/{topic_key}")
def topic_timeline(
    topic_key: str,
    limit: int = Query(12, ge=1, le=36),
    _user=Depends(require_permission("market_analysis")),
):
    return success_response(_repository().topic_timeline(topic_key, limit=limit))
