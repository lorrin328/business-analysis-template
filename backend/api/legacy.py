from fastapi import APIRouter, Body, Depends, HTTPException, Response

from auth import require_permission
from db import (
    get_kpi_data,
    get_org_kpi_data,
    get_platform_data,
    get_product_structure,
    get_target_config,
    save_target_config,
)
from validators.target_validator import validate_target_payload


router = APIRouter(tags=["legacy"])


def mark_legacy_api(response: Response, replacement: str):
    response.headers["X-API-Deprecated"] = "true"
    response.headers["X-API-Replacement"] = replacement


@router.get("/api/data/{year}")
def get_data(year: int, response: Response, _user=Depends(require_permission("platform_trend"))):
    """Legacy platform data endpoint. Prefer /api/platform-data?year=YYYY."""
    mark_legacy_api(response, "/api/platform-data?year={year}")
    return get_platform_data(year)


@router.get("/api/kpi/{year}")
def get_kpi(year: int, response: Response, _user=Depends(require_permission("kpi"))):
    """Legacy KPI endpoint. Prefer /api/kpi?year=YYYY."""
    mark_legacy_api(response, "/api/kpi?year={year}")
    return get_kpi_data(year)


@router.get("/api/product/{year}")
def get_product(
    year: int,
    response: Response,
    dimension: str = "product_mix",
    transformLines: str | None = None,
    jingdaiOrgs: str | None = None,
    includeTransform: bool = True,
    includeJingdai: bool = True,
    orgs: str | None = None,
    months: str | None = None,
    metric: str = "qj",
    _user=Depends(require_permission("product_structure")),
):
    """Legacy product endpoint. Prefer /api/product-analysis?year=YYYY."""
    mark_legacy_api(response, "/api/product-analysis?year={year}")
    return get_product_structure(year, dimension, transformLines, jingdaiOrgs, includeTransform, includeJingdai, orgs, months, metric)


@router.get("/api/org-kpi/{year}")
def get_org_kpi(year: int, response: Response, _user=Depends(require_permission("org"))):
    """Legacy organization KPI endpoint. Prefer /api/org-analysis?year=YYYY."""
    mark_legacy_api(response, "/api/org-analysis?year={year}")
    return get_org_kpi_data(year)


@router.get("/api/targets/{year}")
def get_targets(year: int, response: Response):
    """Legacy target read endpoint. Prefer /api/targets?year=YYYY."""
    mark_legacy_api(response, "/api/targets?year={year}")
    saved = get_target_config(year)
    return saved or {"year": year, "categories": None}


@router.put("/api/targets/{year}")
def put_targets(year: int, response: Response, payload: dict = Body(...), _user=Depends(require_permission("targets"))):
    """Legacy target write endpoint. Prefer POST /api/targets?year=YYYY."""
    mark_legacy_api(response, "/api/targets?year={year}")
    validation = validate_target_payload(payload)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.to_dict())
    payload_year = payload.get("year")
    if payload_year is not None and int(payload_year) != int(year):
        raise HTTPException(status_code=400, detail="目标年份与请求年份不一致")
    return save_target_config(year, payload, updated_by=_user.get("username") or "system")
