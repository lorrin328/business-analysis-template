from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_permission
from branch_analysis.analyzer import analyze_branch_network
from services.response import response_meta, success_response


router = APIRouter(prefix="/api/branch-analysis", tags=["branch-analysis"])


@router.get("/overview")
def overview(
    year: int | None = Query(None, ge=2020, le=2100),
    as_of: date | None = Query(None, alias="asOf"),
    _user=Depends(require_permission("branch_analysis")),
):
    try:
        data = analyze_branch_network(year=year, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(
        data,
        meta=response_meta(
            metric="branch_network_analysis",
            unit="万元",
            data_source="production.performance + branch_reference",
            definitions=data["quality"]["definitions"],
        ),
    )
