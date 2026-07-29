from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from auth import require_permission
from services.audit_log import log_operation
from services.response import batch_meta, success_response
from variable_expense.analyzer import DATA_SOURCE_MODE, RULE_VERSION, analyze_variable_expense_workbook
from variable_expense.repository import create_batch, find_by_hash, latest_batch, list_batches


router = APIRouter(prefix="/api/variable-expense", tags=["variable-expense"])
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_VARIABLE_EXPENSE_UPLOAD_SIZE_MB", "30"))


@router.get("/latest")
def latest(
    period: str | None = Query(None, pattern=r"^20\d{2}-(0[1-9]|1[0-2])$"),
    _user=Depends(require_permission("variable_expense_view")),
):
    data = latest_batch(period)
    return success_response(
        data or {
            "batch": None,
            "period": period,
            "summary": {},
            "details": {"modes": [], "institutions": [], "composition": {}, "projects": [], "products": []},
            "quality": {"status": "empty", "checks": [], "warnings": []},
            "reportComparison": None,
            "definitions": {},
        },
        meta=batch_meta(
            batch_id=data["batch"]["id"] if data else None,
            rule_version=RULE_VERSION,
            data_source_mode=DATA_SOURCE_MODE,
        ),
    )


@router.get("/batches")
def batches(
    limit: int = Query(12, ge=1, le=36),
    _user=Depends(require_permission("variable_expense_view")),
):
    return success_response(list_batches(limit))


@router.post("/upload")
async def upload(
    workbook: UploadFile = File(...),
    period: str | None = Form(None),
    _user=Depends(require_permission("variable_expense_upload")),
):
    if not workbook.filename or not workbook.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 格式的财务月报")
    content = await workbook.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件超过 {MAX_UPLOAD_SIZE_MB}MB 限制")

    file_hash = hashlib.sha256(content).hexdigest()
    try:
        result = analyze_variable_expense_workbook(content, workbook.filename, period)
    except Exception as exc:
        log_operation(
            "variable_expense_upload",
            user=_user,
            status="failed",
            detail={"fileName": workbook.filename, "reason": str(exc)[:300]},
        )
        raise HTTPException(status_code=400, detail=f"财务月报解析失败：{exc}") from exc

    duplicate = find_by_hash(file_hash)
    if duplicate:
        return success_response(
            {**duplicate, "duplicate": True},
            message="相同文件已导入，未重复生成批次。",
            meta=batch_meta(
                batch_id=duplicate["batch"]["id"],
                rule_version=duplicate["batch"]["ruleVersion"],
                data_source_mode=DATA_SOURCE_MODE,
            ),
        )

    blocking = [item for item in result["quality"]["warnings"] if item.get("level") == "high"]
    if blocking:
        log_operation(
            "variable_expense_upload",
            user=_user,
            status="failed",
            detail={"fileName": workbook.filename, "reason": "blocking_validation"},
        )
        raise HTTPException(
            status_code=422,
            detail={"message": "财务月报未通过强校验，未生成成功批次", "warnings": blocking},
        )

    data = create_batch(
        file_name=workbook.filename,
        file_hash=file_hash,
        file_size=len(content),
        result=result,
        imported_by=_user.get("username") or "system",
    )
    log_operation(
        "variable_expense_upload",
        user=_user,
        detail={
            "batchId": data["batch"]["id"],
            "period": data["period"],
            "fileName": workbook.filename,
            "dataSourceMode": DATA_SOURCE_MODE,
        },
    )
    return success_response(
        data,
        meta=batch_meta(
            batch_id=data["batch"]["id"],
            rule_version=RULE_VERSION,
            data_source_mode=DATA_SOURCE_MODE,
        ),
    )
