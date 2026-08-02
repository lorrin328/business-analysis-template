from __future__ import annotations

from io import BytesIO
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from auth import require_permission
from customer_analysis import get_customer_analysis, get_new_customer_cohort_analysis
from customer_analysis.importer import (
    CustomerImportError,
    build_customer_import_template,
    list_customer_import_batches,
)
from customer_analysis.jobs import (
    append_upload_chunk,
    commit_prepared_customer_import,
    create_upload_session,
    get_import_job,
    prepare_customer_import,
    request_commit,
    start_processing,
)
from services.audit_log import log_operation
from services.response import response_meta, success_response


router = APIRouter(prefix="/api/customer-analysis", tags=["customer-analysis"])


@router.get("/overview")
def overview(
    year: int | None = Query(None, ge=2007, le=2100),
    period_type: Literal["year", "quarter", "month"] = Query("year", alias="periodType"),
    period_value: int | None = Query(None, alias="periodValue", ge=1, le=12),
    business_line: Literal["OTO", "证保", "蚁桥"] | None = Query(None, alias="businessLine"),
    org: str | None = Query(None),
    policy_scope: Literal["all", "longterm"] = Query("all", alias="policyScope"),
    _user=Depends(require_permission("customer_analysis")),
):
    try:
        data = get_customer_analysis(
            year=year,
            period_type=period_type,
            period_value=period_value,
            business_line=business_line,
            org=(org or "").strip() or None,
            policy_scope=policy_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(
        data,
        meta=response_meta(
            metric="customer_policy_analysis",
            unit="万元",
            data_source="performance + customer_policy_snapshot",
            definitions=data["quality"]["definitions"],
        ),
    )


@router.get("/new-customer-cohort")
def new_customer_cohort(
    year: int | None = Query(None, ge=2007, le=2100),
    period_type: Literal["year", "quarter", "month"] = Query("year", alias="periodType"),
    period_value: int | None = Query(None, alias="periodValue", ge=1, le=12),
    observation_window: Literal["first_month", "twelve_months", "calendar_year"] = Query(
        "twelve_months", alias="observationWindow"
    ),
    business_line: Literal["OTO", "证保", "蚁桥"] | None = Query(None, alias="businessLine"),
    org: str | None = Query(None),
    policy_scope: Literal["all", "longterm"] = Query("all", alias="policyScope"),
    product: str | None = Query(None),
    _user=Depends(require_permission("customer_analysis")),
):
    try:
        data = get_new_customer_cohort_analysis(
            year=year,
            period_type=period_type,
            period_value=period_value,
            observation_window=observation_window,
            business_line=business_line,
            org=(org or "").strip() or None,
            policy_scope=policy_scope,
            product=(product or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(
        data,
        meta=response_meta(
            metric="new_customer_cohort_analysis",
            unit="万元",
            data_source="customer_master + customer_policy_month_fact + performance",
            definitions=data["quality"]["definitions"],
        ),
    )


@router.get("/import/template")
def customer_import_template(
    format: Literal["csv", "xlsx"] = Query("xlsx"),
    _viewer=Depends(require_permission("customer_analysis")),
):
    content, media_type, filename = build_customer_import_template(format)
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/import/batches")
def customer_import_batches(
    limit: int = Query(10, ge=1, le=50),
    _viewer=Depends(require_permission("customer_analysis")),
):
    return success_response({"batches": list_customer_import_batches(limit)})


@router.post("/import/uploads")
def customer_import_create_upload(
    payload: dict = Body(...),
    _viewer=Depends(require_permission("customer_analysis")),
    _user=Depends(require_permission("upload")),
):
    try:
        data = create_upload_session(payload.get("files") or [], _user.get("username") or "system")
    except CustomerImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_operation(
        "customer_import_upload_created", user=_user,
        detail={"batchId": data["batchId"], "fileCount": len(data["files"]), "totalBytes": data["totalBytes"]},
    )
    return success_response(data)


@router.post("/import/uploads/{upload_id}/files/{file_index}/chunks")
async def customer_import_upload_chunk(
    upload_id: str,
    file_index: int,
    request: Request,
    offset: int = Query(..., ge=0),
    _viewer=Depends(require_permission("customer_analysis")),
    _user=Depends(require_permission("upload")),
):
    try:
        data = append_upload_chunk(
            upload_id, file_index, offset, await request.body(), _user.get("username") or "system"
        )
    except CustomerImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(data)


@router.post("/import/uploads/{upload_id}/process", status_code=202)
def customer_import_start_processing(
    upload_id: str,
    background_tasks: BackgroundTasks,
    _viewer=Depends(require_permission("customer_analysis")),
    _user=Depends(require_permission("upload")),
):
    try:
        data = start_processing(upload_id, _user.get("username") or "system")
    except CustomerImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(prepare_customer_import, upload_id)
    log_operation("customer_import_processing_started", user=_user, detail={"uploadId": upload_id})
    return success_response(data, message="文件已转交后台预检")


@router.get("/import/uploads/{upload_id}")
def customer_import_job_status(
    upload_id: str,
    _viewer=Depends(require_permission("customer_analysis")),
    _user=Depends(require_permission("upload")),
):
    try:
        data = get_import_job(
            upload_id, _user.get("username") or "system", allow_admin=_user.get("role") == "admin"
        )
    except CustomerImportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success_response(data)


@router.post("/import/uploads/{upload_id}/commit", status_code=202)
def customer_import_commit(
    upload_id: str,
    background_tasks: BackgroundTasks,
    _viewer=Depends(require_permission("customer_analysis")),
    _user=Depends(require_permission("upload")),
):
    try:
        data = request_commit(upload_id, _user.get("username") or "system")
    except CustomerImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(commit_prepared_customer_import, upload_id)
    log_operation(
        "customer_import_commit_started", user=_user,
        detail={"batchId": data["batchId"], "uploadId": upload_id},
    )
    return success_response(data, message="导入任务已转交后台处理")
