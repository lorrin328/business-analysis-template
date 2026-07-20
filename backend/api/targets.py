from fastapi import APIRouter, Body, Depends, HTTPException

from api.params import DashboardYearQuery
from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_target_config, get_target_values, save_target_config
from services.audit_log import log_operation
from services.response import response_meta, success_response
from validators.target_validator import validate_target_payload

router = APIRouter(prefix="/api", tags=["targets"])


@router.get("/targets")
def targets(year: DashboardYearQuery = DEFAULT_YEAR, mode: str = "config"):
    if mode == "rows":
        data = {"year": year, "targets": get_target_values(year)}
    else:
        data = get_target_config(year) or {"year": year, "categories": None}
    return success_response(
        data,
        meta=response_meta(
            metric="targets",
            unit="万元",
            data_source="target_config/target_values",
            year=year,
            definitions={
                k: METRICS[k]
                for k in ["achievement_rate", "time_progress", "progress_gap"]
                if k in METRICS
            },
        ),
    )


@router.post("/targets")
def save_targets(
    year: DashboardYearQuery = DEFAULT_YEAR,
    payload: dict = Body(...),
    _user=Depends(require_permission("targets")),
):
    validation = validate_target_payload(payload)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.to_dict())
    payload_year = payload.get("year")
    if payload_year is not None and int(payload_year) != int(year):
        raise HTTPException(status_code=400, detail="目标年份与请求年份不一致")
    data = save_target_config(year, payload, updated_by=_user.get("username") or "system")
    log_operation("target_save", user=_user, detail={"year": year})
    return success_response(
        data,
        message="目标已保存",
        meta=response_meta(
            metric="targets",
            unit="万元",
            year=year,
            definitions={
                k: METRICS[k]
                for k in ["achievement_rate", "time_progress", "progress_gap"]
                if k in METRICS
            },
        ),
    )
