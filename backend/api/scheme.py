from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from auth import require_permission
from scheme.calculator import calculate_2026_org_dev_workbook
from scheme.config import DATA_SOURCE_MODE, RULE_DEFINITIONS, RULE_VERSION, SCHEME_ID, SCHEME_NAME, SCHEME_OPTIONS
from scheme.repository import create_scheme_batch, latest_scheme_batch
from services.audit_log import log_operation
from services.response import batch_meta, success_response

router = APIRouter(prefix="/api/scheme", tags=["scheme"])

MAX_SCHEME_UPLOAD_SIZE_MB = int(os.getenv("MAX_SCHEME_UPLOAD_SIZE_MB", "20"))


def _scheme_option_or_404(scheme_id: str) -> dict:
    for option in SCHEME_OPTIONS:
        if option["id"] == scheme_id:
            return option
    raise HTTPException(status_code=404, detail="方案不存在")


@router.get("/options")
def options(_user=Depends(require_permission("scheme_calculation"))):
    latest = latest_scheme_batch(SCHEME_ID)
    return success_response(
        {
            "schemes": SCHEME_OPTIONS,
            "defaultSchemeId": SCHEME_ID,
            "latestBatch": latest.get("batch") if latest else None,
        },
        meta=batch_meta(batch_id=latest["batch"]["id"] if latest else None, rule_version=RULE_VERSION, data_source_mode=DATA_SOURCE_MODE),
    )


@router.get("/latest")
def latest(scheme_id: str = Query(SCHEME_ID, alias="schemeId"), _user=Depends(require_permission("scheme_calculation"))):
    option = _scheme_option_or_404(scheme_id)
    latest = latest_scheme_batch(scheme_id)
    if latest:
        return success_response(
            latest,
            meta=batch_meta(
                batch_id=latest["batch"]["id"],
                rule_version=latest["batch"]["ruleVersion"],
                data_source_mode=DATA_SOURCE_MODE,
            ),
        )
    empty = {
        "batch": None,
        "scheme": {"id": option["id"], "name": option["name"], "ruleVersion": option["ruleVersion"]},
        "summary": {},
        "details": {"rows": []},
        "warnings": [],
        "definitions": RULE_DEFINITIONS,
        "sourceAudit": {"calculationBasis": "正式PDF为主、Excel底稿为当前测算展示依据。"},
    }
    return success_response(empty, meta=batch_meta(batch_id=None, rule_version=RULE_VERSION, data_source_mode=DATA_SOURCE_MODE))


@router.post("/upload")
async def upload_scheme_excel(
    scheme_id: str = Form(SCHEME_ID, alias="schemeId"),
    tracking: UploadFile = File(...),
    _user=Depends(require_permission("scheme_upload")),
):
    option = _scheme_option_or_404(scheme_id)
    if not tracking.filename or not tracking.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 格式的方案测算工作簿")

    content = await tracking.read()
    max_size = MAX_SCHEME_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"文件超过 {MAX_SCHEME_UPLOAD_SIZE_MB}MB 限制")
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        result = calculate_2026_org_dev_workbook(content, tracking.filename)
    except Exception as exc:
        log_operation("scheme_upload", user=_user, status="failed", detail={"schemeId": scheme_id, "fileName": tracking.filename})
        raise HTTPException(status_code=400, detail=f"方案测算工作簿解析失败：{exc}") from exc

    file_hash = hashlib.sha256(content).hexdigest()
    batch = create_scheme_batch(
        scheme_id=option["id"],
        scheme_name=option["name"],
        rule_version=RULE_VERSION,
        file_name=tracking.filename,
        file_hash=file_hash,
        file_size=len(content),
        result=result,
        imported_by=_user.get("username") or "system",
    )
    log_operation(
        "scheme_upload",
        user=_user,
        detail={
            "schemeId": option["id"],
            "schemeName": SCHEME_NAME,
            "batchId": batch["batch"]["id"],
            "ruleVersion": RULE_VERSION,
            "dataSourceMode": DATA_SOURCE_MODE,
            "fileName": tracking.filename,
        },
    )
    return success_response(
        batch,
        meta=batch_meta(batch_id=batch["batch"]["id"], rule_version=RULE_VERSION, data_source_mode=DATA_SOURCE_MODE),
    )
