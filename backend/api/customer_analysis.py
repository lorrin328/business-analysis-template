from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_permission
from customer_analysis import get_customer_analysis, get_new_customer_cohort_analysis
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
