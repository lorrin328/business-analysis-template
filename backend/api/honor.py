from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from honor.config import DATA_SOURCE_MODE, RULE_VERSION
from honor.exporter import build_honor_export_workbook
from honor.repository import fetch_summary, fetch_table, latest_batch
from honor.service import recalculate_honor, run_field_audit
from services.audit_log import log_operation
from services.response import success_response

router = APIRouter(prefix="/api/honor", tags=["honor"])


def _batch_or_404(batch_id: int | None = None, year: int | None = None, month: int | None = None) -> dict:
    batch = {"id": batch_id} if batch_id else latest_batch(year=year, month=month)
    if batch_id:
        batch = latest_batch()
        if not batch or int(batch["id"]) != int(batch_id):
            from db.connection import get_db
            with get_db() as conn:
                row = conn.execute("SELECT * FROM honor_import_batches WHERE id = ?", (batch_id,)).fetchone()
                batch = dict(row) if row else None
    if not batch:
        raise HTTPException(status_code=404, detail="暂无星钻批次，请先执行字段审计或重算")
    return batch


@router.get("/field-audit")
def field_audit(_user=Depends(require_permission("honor_audit"))):
    audit = run_field_audit(user=_user, persist=True)
    log_operation(
        "honor_field_audit",
        user=_user,
        detail={
            "batchId": audit.get("batchId"),
            "ruleVersion": RULE_VERSION,
            "dataSourceMode": DATA_SOURCE_MODE,
            "exceptionCount": audit.get("unavailableRuleCount", 0),
            "userOrgScope": "all",
        },
    )
    return success_response(
        audit,
        meta={"batchId": audit.get("batchId"), "ruleVersion": RULE_VERSION, "dataSourceMode": DATA_SOURCE_MODE},
    )


@router.post("/recalculate")
def recalculate(payload: dict = Body(...), _user=Depends(require_permission("honor_recalculate"))):
    year = int(payload.get("year") or DEFAULT_YEAR)
    month = int(payload.get("month") or 12)
    result = recalculate_honor(year, month, user=_user)
    log_operation(
        "honor_recalculate",
        user=_user,
        detail={**result, "userOrgScope": "all"},
    )
    return success_response(result, meta=result)


@router.get("/summary")
def summary(
    year: int = Query(DEFAULT_YEAR),
    month: int | None = None,
    batch_id: int | None = Query(None, alias="batchId"),
    _user=Depends(require_permission("honor_view")),
):
    batch = _batch_or_404(batch_id, year, month)
    data = fetch_summary(int(batch["id"]))
    log_operation(
        "honor_view_batch",
        user=_user,
        detail={"year": data.get("batch", {}).get("year"), "month": data.get("batch", {}).get("month"), "batchId": batch["id"], "ruleVersion": data.get("batch", {}).get("rule_version"), "dataSourceMode": data.get("batch", {}).get("data_source_mode"), "userOrgScope": "all"},
    )
    return success_response(data, meta={"batchId": batch["id"], "ruleVersion": RULE_VERSION, "dataSourceMode": DATA_SOURCE_MODE})


@router.get("/orgs")
def orgs(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    return success_response({"rows": fetch_table("honor_org_summary", int(batch["id"]))}, meta={"batchId": batch["id"]})


@router.get("/persons")
def persons(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    return success_response({"rows": fetch_table("honor_person_summary", int(batch["id"]))}, meta={"batchId": batch["id"]})


@router.get("/exceptions")
def exceptions(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    return success_response({"rows": fetch_table("honor_exceptions", int(batch["id"]))}, meta={"batchId": batch["id"]})


@router.get("/trend")
def trend(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    rows = fetch_table("honor_person_month", int(batch["id"]), limit=5000)
    grouped = {}
    for row in rows:
        key = int(row.get("month") or 0)
        item = grouped.setdefault(key, {"month": key, "gainCount": 0, "deductCount": 0, "memberCount": 0})
        item["gainCount"] += 1 if int(row.get("diamond_delta") or 0) > 0 else 0
        item["deductCount"] += 1 if int(row.get("diamond_delta") or 0) < 0 else 0
        item["memberCount"] += 1 if row.get("membership_level") != "未入会" else 0
    return success_response({"rows": [grouped[k] for k in sorted(grouped)]}, meta={"batchId": batch["id"]})


@router.get("/export")
def export(batch_id: int = Query(..., alias="batchId"), _user=Depends(require_permission("honor_export"))):
    batch = _batch_or_404(batch_id=batch_id)
    content = build_honor_export_workbook(int(batch["id"]))
    log_operation(
        "honor_export",
        user=_user,
        detail={"year": batch.get("year"), "month": batch.get("month"), "batchId": batch["id"], "ruleVersion": batch.get("rule_version"), "dataSourceMode": batch.get("data_source_mode"), "exceptionCount": batch.get("exception_count"), "userOrgScope": "all"},
    )
    filename = quote(f"星钻联盟荣誉体系_{batch.get('year')}_{batch.get('month')}_{batch['id']}.xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/upload")
def upload_placeholder(_user=Depends(require_permission("honor_upload"))):
    raise HTTPException(status_code=501, detail="本期不新增星钻专用上传，请优先复用现有数据。")

