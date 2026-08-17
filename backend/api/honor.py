from datetime import date, datetime
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from honor.config import DATA_SOURCE_MODE, RULE_VERSION
from honor.exporter import build_honor_export_workbook
from honor.periods import honor_result_meta
from honor.repository import fetch_dashboard, fetch_summary, fetch_table, latest_batch, list_available_periods
from honor.service import recalculate_honor, run_field_audit
from services.audit_log import log_operation
from services.response import batch_meta, success_response

router = APIRouter(prefix="/api/honor", tags=["honor"])


def _normalize_source_cutoff(value: str | None, *, year: int | None = None, month: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="过程截至日格式应为 YYYY-MM-DD") from exc
    if year and month and parsed < date(int(year), int(month), 1):
        raise HTTPException(status_code=400, detail="过程截至日不能早于所选月份首日")
    return parsed.isoformat()


def _batch_or_404(
    batch_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    source_cutoff: str | None = None,
) -> dict:
    batch = {"id": batch_id} if batch_id else latest_batch(year=year, month=month, source_cutoff=source_cutoff)
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


@router.get("/periods")
def periods(
    year: int | None = Query(None),
    _user=Depends(require_permission("honor_view")),
):
    batches = list_available_periods(year)
    grouped: dict[tuple[int, int], dict] = {}
    seen_versions: dict[tuple[int, int], set[str]] = {}
    for batch in batches:
        batch_year = int(batch.get("year") or 0)
        batch_month = int(batch.get("month") or 0)
        if not batch_year or not batch_month:
            continue
        key = (batch_year, batch_month)
        item = grouped.setdefault(
            key,
            {
                "year": batch_year,
                "month": batch_month,
                "recommendedBatchId": None,
                "sourceCutoff": None,
                "monthEndSnapshotBatchId": None,
                "finalBatchId": None,
                "versions": [],
            },
        )
        cutoff = str(batch.get("source_cutoff") or "")
        version_key = cutoff or "final"
        if version_key in seen_versions.setdefault(key, set()):
            continue
        seen_versions[key].add(version_key)
        result_meta = honor_result_meta(
            batch_year,
            batch_month,
            cutoff or None,
            created_at=batch.get("created_at"),
        )
        version = {
            "batchId": int(batch["id"]),
            "sourceCutoff": cutoff or None,
            "createdAt": batch.get("created_at"),
            "ruleVersion": batch.get("rule_version"),
            **result_meta,
        }
        item["versions"].append(version)
        if result_meta["resultType"] == "month_end":
            item["monthEndSnapshotBatchId"] = version["batchId"]
        elif result_meta["resultType"] == "final" and result_meta["finalConfirmed"]:
            item["finalBatchId"] = version["batchId"]

    items = [grouped[key] for key in sorted(grouped, reverse=True)]
    for item in items:
        recommended = next(
            (version for version in item["versions"] if version["finalConfirmed"]),
            next(
                (version for version in item["versions"] if version["resultType"] != "final"),
                item["versions"][0],
            ),
        )
        item["recommendedBatchId"] = recommended["batchId"]
        item["sourceCutoff"] = recommended["sourceCutoff"]
        period_meta = honor_result_meta(item["year"], item["month"], item.get("sourceCutoff"))
        item.update(
            {
                "monthEnd": period_meta["monthEnd"],
                "finalReadyOn": period_meta["finalReadyOn"],
                "canCreateMonthEndSnapshot": period_meta["canCreateMonthEndSnapshot"],
                "canCreateFinal": period_meta["canCreateFinal"],
                "monthEndSnapshotAvailable": item["monthEndSnapshotBatchId"] is not None,
                "finalAvailable": item["finalBatchId"] is not None,
            }
        )
    return success_response(
        {
            "years": sorted({item["year"] for item in items}, reverse=True),
            "periods": items,
        }
    )


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
        meta=batch_meta(
            batch_id=audit.get("batchId"),
            rule_version=RULE_VERSION,
            data_source_mode=DATA_SOURCE_MODE,
        ),
    )


@router.post("/recalculate")
def recalculate(payload: dict = Body(...), _user=Depends(require_permission("honor_recalculate"))):
    year = int(payload.get("year") or DEFAULT_YEAR)
    month = int(payload.get("month") or 12)
    source_cutoff = _normalize_source_cutoff(payload.get("asOf") or payload.get("sourceCutoff"), year=year, month=month)
    result_meta = honor_result_meta(year, month, source_cutoff)
    if source_cutoff and date.fromisoformat(source_cutoff) > date.today():
        raise HTTPException(status_code=400, detail="测算截止日不能晚于今天")
    if source_cutoff is None and not result_meta["canCreateFinal"]:
        current_guidance = (
            f"当前可生成{result_meta['monthEnd']}月末快照。"
            if result_meta["canCreateMonthEndSnapshot"]
            else "当前月份尚未结束，只能生成不晚于今天的过程数据。"
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"{year}年{month}月最终结果最早可在{result_meta['finalReadyOn']}生成，"
                f"且需先更新回销数据；{current_guidance}"
            ),
        )
    result = recalculate_honor(year, month, source_cutoff=source_cutoff, user=_user)
    result.update(result_meta)
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
    as_of: str | None = Query(None, alias="asOf"),
    _user=Depends(require_permission("honor_view")),
):
    source_cutoff = _normalize_source_cutoff(as_of, year=year, month=month) if as_of else None
    batch = _batch_or_404(batch_id, year, month, source_cutoff)
    data = fetch_summary(int(batch["id"]))
    log_operation(
        "honor_view_batch",
        user=_user,
        detail={"year": data.get("batch", {}).get("year"), "month": data.get("batch", {}).get("month"), "batchId": batch["id"], "ruleVersion": data.get("batch", {}).get("rule_version"), "dataSourceMode": data.get("batch", {}).get("data_source_mode"), "sourceCutoff": data.get("batch", {}).get("source_cutoff"), "userOrgScope": "all"},
    )
    return success_response(
        data,
        meta=batch_meta(
            batch_id=batch["id"],
            rule_version=RULE_VERSION,
            data_source_mode=DATA_SOURCE_MODE,
            sourceCutoff=data.get("batch", {}).get("source_cutoff"),
        ),
    )


@router.get("/dashboard")
def dashboard(
    year: int = Query(DEFAULT_YEAR),
    month: int | None = None,
    batch_id: int | None = Query(None, alias="batchId"),
    as_of: str | None = Query(None, alias="asOf"),
    _user=Depends(require_permission("honor_view")),
):
    source_cutoff = _normalize_source_cutoff(as_of, year=year, month=month) if as_of else None
    batch = _batch_or_404(batch_id, year, month, source_cutoff)
    data = fetch_dashboard(int(batch["id"]))
    log_operation(
        "honor_dashboard_view",
        user=_user,
        detail={
            "year": data.get("batch", {}).get("year"),
            "month": data.get("batch", {}).get("month"),
            "batchId": batch["id"],
            "ruleVersion": data.get("batch", {}).get("rule_version"),
            "dataSourceMode": data.get("batch", {}).get("data_source_mode"),
            "sourceCutoff": data.get("batch", {}).get("source_cutoff"),
            "userOrgScope": "all",
        },
    )
    return success_response(
        data,
        meta=batch_meta(
            batch_id=batch["id"],
            rule_version=RULE_VERSION,
            data_source_mode=DATA_SOURCE_MODE,
            sourceCutoff=data.get("batch", {}).get("source_cutoff"),
        ),
    )


@router.get("/orgs")
def orgs(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    return success_response({"rows": fetch_table("honor_org_summary", int(batch["id"]))}, meta=batch_meta(batch_id=batch["id"]))


@router.get("/persons")
def persons(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    return success_response({"rows": fetch_table("honor_person_summary", int(batch["id"]))}, meta=batch_meta(batch_id=batch["id"]))


@router.get("/exceptions")
def exceptions(batch_id: int | None = Query(None, alias="batchId"), year: int = Query(DEFAULT_YEAR), month: int | None = None, _user=Depends(require_permission("honor_view"))):
    batch = _batch_or_404(batch_id, year, month)
    rows = fetch_table("honor_exceptions", int(batch["id"]))
    persons = fetch_table("honor_person_summary", int(batch["id"]), limit=5000)
    name_index = {str(row.get("staff_code") or ""): row.get("staff_name") for row in persons if row.get("staff_code")}
    for row in rows:
        row["staff_name"] = name_index.get(str(row.get("staff_code") or ""), "")
    return success_response({"rows": rows}, meta=batch_meta(batch_id=batch["id"]))


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
    return success_response({"rows": [grouped[k] for k in sorted(grouped)]}, meta=batch_meta(batch_id=batch["id"]))


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
