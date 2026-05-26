from fastapi import APIRouter, Body, Depends, HTTPException, Query

from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_target_config, get_target_values, save_target_config
from services.response import success_response
from validators.target_validator import validate_target_payload

router = APIRouter(prefix="/api", tags=["targets"])


@router.get("/targets")
def targets(year: int = Query(DEFAULT_YEAR, ge=2000, le=2100), mode: str = "config"):
    if mode == "rows":
        data = {"year": year, "targets": get_target_values(year)}
    else:
        data = get_target_config(year) or {"year": year, "categories": None}
    return success_response(
        data,
        meta={
            "year": year,
            "metric": "targets",
            "unit": "万元",
            "dataSource": "target_config/target_values",
            "definitions": {
                k: METRICS[k]
                for k in ["achievement_rate", "time_progress", "progress_gap"]
                if k in METRICS
            },
        },
    )


@router.post("/targets")
def save_targets(
    year: int = Query(DEFAULT_YEAR, ge=2000, le=2100),
    payload: dict = Body(...),
    updatedBy: str = "admin",
    _user=Depends(require_permission("targets")),
):
    validation = validate_target_payload(payload)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.to_dict())
    data = save_target_config(year, payload, updated_by=updatedBy)
    return success_response(
        data,
        message="目标已保存",
        meta={
            "year": year,
            "metric": "targets",
            "unit": "万元",
            "definitions": {
                k: METRICS[k]
                for k in ["achievement_rate", "time_progress", "progress_gap"]
                if k in METRICS
            },
        },
    )
