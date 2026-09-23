"""Read-only API surface for external AI assistants."""
from __future__ import annotations

import base64
import binascii
import hmac
import os
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from api.auth_routes import (
    _clear_login_failures,
    _login_attempt_key,
    _login_retry_after,
    _record_login_failure,
)
from api.params import DashboardYearQuery
from auth import ROLE_ADMIN, get_current_user, verify_user_credentials
from config.business_lines import BUSINESS_LINES, DEFAULT_YEAR
from config.metrics import DASHBOARD_KPI_CARDS, DISPLAY_CONSTRAINTS, METRICS
from config.version import get_app_version, get_semver
from db import get_kpi_data, get_org_kpi_data
from db.repositories.target import get_target_config
from db.repositories.team_enhanced import get_team_enhanced_analysis
from market_analysis.repository import MarketAnalysisRepository
from services.audit_log import log_operation
from services.response import response_meta, success_response
from services.ai_raw_data import ImportChangedError, list_raw_datasets, read_raw_page
from services.ai_business_data import BUSINESS_DATASETS, analyze, catalog, page

router = APIRouter(prefix="/api/ai", tags=["ai-readonly"])


def _ai_token() -> str:
    return os.getenv("AI_READONLY_TOKEN", "").strip()


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item and item.strip()]


def _extract_token(authorization: str | None, x_ai_token: str | None) -> str:
    if x_ai_token:
        return x_ai_token.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return ""


def _unauthorized(detail: str = "AI read-only authentication failed") -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": 'Basic realm="Business Analysis AI", Bearer'},
    )


def _extract_basic_credentials(authorization: str) -> tuple[str, str]:
    encoded = authorization.removeprefix("Basic ").strip()
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        _unauthorized("Invalid Basic authentication header")
    if not username or not password:
        _unauthorized("Username and password are required")
    return username, password


def _authenticate_basic(request: Request, authorization: str) -> dict:
    username, password = _extract_basic_credentials(authorization)
    attempt_key = _login_attempt_key(request, username)
    retry_after = _login_retry_after(attempt_key)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )
    user = verify_user_credentials(username, password)
    if not user:
        retry_after = _record_login_failure(attempt_key)
        log_operation(
            "ai_basic_login",
            status="failed",
            target_username=str(username or "")[:64],
            detail={"reason": "invalid_credentials"},
        )
        if retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录失败次数过多，请稍后再试",
                headers={"Retry-After": str(retry_after)},
            )
        _unauthorized("用户名或密码错误")
    _clear_login_failures(attempt_key)
    return user


def require_ai_readonly(
    request: Request,
    authorization: str | None = Header(default=None),
    x_ai_token: str | None = Header(default=None, alias="X-AI-Token"),
) -> dict:
    if authorization and authorization.startswith("Basic "):
        return _authenticate_basic(request, authorization)

    expected = _ai_token()
    provided = _extract_token(authorization, x_ai_token)
    if expected and provided and hmac.compare_digest(provided, expected):
        return {
            "id": 0,
            "username": "ai-readonly",
            "role": "ai_reader",
            "permissions": {"ai_readonly": True},
        }
    if authorization and authorization.startswith("Bearer "):
        try:
            return get_current_user(authorization)
        except HTTPException:
            _unauthorized("Invalid AI token or account session")
    _unauthorized()


def _require_ai_permission(user: dict, module_key: str) -> None:
    if user.get("role") in {ROLE_ADMIN, "ai_reader"}:
        return
    if user.get("permissions", {}).get(module_key) is True:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _log_ai(action: str, user: dict, detail: dict[str, Any]) -> None:
    log_operation(action, user=user, detail=detail)


def _target_summary(year: int) -> dict:
    payload = get_target_config(year) or {}
    categories = payload.get("categories") or {}
    org_targets = payload.get("orgTargets") or {}
    return {
        "year": year,
        "hasTargetConfig": bool(payload),
        "categoryKeys": sorted(categories.keys()),
        "orgTargetCount": len(org_targets),
        "updatedAt": payload.get("updated_at"),
        "updatedBy": payload.get("updated_by"),
    }


def _org_overview(org_data: dict) -> dict:
    perf = org_data.get("perf") or {}
    org_totals: dict[str, dict[str, float]] = {}
    for key, item in perf.items():
        org, channel = (str(key).split("|", 1) + [""])[:2]
        year_data = (item or {}).get("year") or {}
        total = org_totals.setdefault(org, {
            "qjPremium": 0.0,
            "tenyear": 0.0,
            "annuity": 0.0,
            "protection": 0.0,
            "businessLineCount": 0,
        })
        total["businessLineCount"] += 1 if channel else 0
        total["qjPremium"] += float(year_data.get("qj_premium") or 0)
        total["tenyear"] += float(year_data.get("product_10year") or 0)
        total["annuity"] += float(year_data.get("product_annuity") or 0)
        total["protection"] += float(year_data.get("product_protection") or 0)
    rows = [
        {
            "org": org,
            "qjPremium": round(values["qjPremium"], 2),
            "tenyear": round(values["tenyear"], 2),
            "annuity": round(values["annuity"], 2),
            "protection": round(values["protection"], 2),
            "businessLineCount": int(values["businessLineCount"]),
        }
        for org, values in org_totals.items()
    ]
    rows.sort(key=lambda r: r["qjPremium"], reverse=True)
    return {
        "year": org_data.get("year"),
        "orgCount": len(rows),
        "topByQjPremium": rows[:10],
        "totals": {
            "qjPremium": round(sum(r["qjPremium"] for r in rows), 2),
            "tenyear": round(sum(r["tenyear"] for r in rows), 2),
            "annuity": round(sum(r["annuity"] for r in rows), 2),
            "protection": round(sum(r["protection"] for r in rows), 2),
        },
    }


def _snapshot(kpi: dict, org_data: dict, *, include_org_detail: bool) -> dict:
    data = {
        "version": get_app_version(),
        "year": kpi.get("year"),
        "month": kpi.get("month"),
        "dataCutoff": kpi.get("data_cutoff"),
        "dailyCutoff": kpi.get("daily_cutoff"),
        "kpi": kpi,
        "orgOverview": _org_overview(org_data),
        "targetSummary": _target_summary(int(kpi.get("year") or DEFAULT_YEAR)),
        "metricDefinitions": {
            "metrics": METRICS,
            "dashboardCards": DASHBOARD_KPI_CARDS,
            "displayConstraints": DISPLAY_CONSTRAINTS,
        },
    }
    if include_org_detail:
        data["orgDetail"] = org_data
    return data


@router.get("/kpi")
def ai_kpi(year: DashboardYearQuery = DEFAULT_YEAR, user=Depends(require_ai_readonly)):
    _require_ai_permission(user, "kpi")
    data = get_kpi_data(year)
    _log_ai("ai_kpi_read", user, {"year": year})
    return success_response(
        data,
        meta=response_meta(
            metric="ai-kpi",
            data_source="SQLite aggregate tables",
            year=year,
            access="ai-readonly",
        ),
    )


@router.get("/org-summary")
def ai_org_summary(
    year: DashboardYearQuery = DEFAULT_YEAR,
    includeDetail: bool = Query(False),
    user=Depends(require_ai_readonly),
):
    _require_ai_permission(user, "org")
    org_data = get_org_kpi_data(year)
    data = {"overview": _org_overview(org_data)}
    if includeDetail:
        data["detail"] = org_data
    _log_ai("ai_org_summary_read", user, {"year": year, "includeDetail": includeDetail})
    return success_response(
        data,
        meta=response_meta(
            metric="ai-org-summary",
            data_source="agg_org_*",
            year=year,
            access="ai-readonly",
        ),
    )


@router.get("/team-summary")
def ai_team_summary(
    year: DashboardYearQuery = DEFAULT_YEAR,
    month: int | None = Query(None, ge=1, le=12),
    periodType: str = Query("month", pattern="^(year|quarter|month)$"),
    periodValue: int | None = Query(None, ge=1, le=12),
    businessLines: str | None = Query(None),
    orgs: str | None = Query(None),
    scope: str = Query("all", pattern="^(all|active)$"),
    user=Depends(require_ai_readonly),
):
    _require_ai_permission(user, "team_enhanced")
    data = get_team_enhanced_analysis(
        year=year,
        month=month,
        period_type=periodType,
        period_value=periodValue,
        business_lines=_split_csv(businessLines),
        orgs=_split_csv(orgs),
        scope=scope,
    )
    _log_ai(
        "ai_team_summary_read",
        user,
        {
            "year": year,
            "month": month,
            "periodType": periodType,
            "periodValue": periodValue,
            "businessLines": businessLines,
            "orgs": orgs,
            "scope": scope,
        },
    )
    return success_response(
        data,
        meta=response_meta(
            metric="ai-team-summary",
            data_source="hr_data/performance",
            year=year,
            access="ai-readonly",
        ),
    )


@router.get("/metric-definitions")
def ai_metric_definitions(user=Depends(require_ai_readonly)):
    _require_ai_permission(user, "kpi")
    _log_ai("ai_metric_definitions_read", user, {})
    return success_response(
        {
            "metrics": METRICS,
            "dashboardCards": DASHBOARD_KPI_CARDS,
            "displayConstraints": DISPLAY_CONSTRAINTS,
        },
        meta=response_meta(
            metric="ai-metric-definitions",
            data_source="config.metrics",
            access="ai-readonly",
        ),
    )


@router.get("/dashboard-snapshot")
def ai_dashboard_snapshot(
    year: DashboardYearQuery = DEFAULT_YEAR,
    includeOrgDetail: bool = Query(False),
    user=Depends(require_ai_readonly),
):
    _require_ai_permission(user, "kpi")
    _require_ai_permission(user, "org")
    kpi = get_kpi_data(year)
    org_data = get_org_kpi_data(year)
    data = _snapshot(kpi, org_data, include_org_detail=includeOrgDetail)
    _log_ai("ai_dashboard_snapshot_read", user, {"year": year, "includeOrgDetail": includeOrgDetail})
    return success_response(
        data,
        meta=response_meta(
            metric="ai-dashboard-snapshot",
            data_source="KPI/org aggregate tables and target_config",
            year=year,
            access="ai-readonly",
        ),
    )


def _require_raw_permission(user: dict) -> None:
    # Existing aggregate-only service tokens must not acquire policy-level access.
    if user.get("role") != ROLE_ADMIN and user.get("permissions", {}).get("ai_raw_data") is not True:
        raise HTTPException(status_code=403, detail="AI原始明细读取权限未开通")


def _require_business_permission(user: dict, dataset: str) -> None:
    if dataset not in BUSINESS_DATASETS:
        raise HTTPException(status_code=404, detail="Unknown business dataset")
    _require_raw_permission(user)
    _require_ai_permission(user, BUSINESS_DATASETS[dataset][1])


def _business_meta(dataset: str):
    return response_meta(
        metric="ai-business-data", data_source=f"SQLite {dataset}", access="ai-readonly",
        definitions={
            "scope": "当前SQLite业务表的已存储字段；不是源Excel、导入历史或冻结快照",
            "values": "保持原表单位和NULL；聚合表与原始表不可直接相加",
            "analysis": "通用分组统计只计算存储值；正式经营指标须以看板接口和指标口径为准",
            "latestImportId": "仅监测日常导入记录变化，不能检测离线重建或其他模块写入",
        },
    )


@router.get("/business-datasets")
def ai_business_datasets(user=Depends(require_ai_readonly)):
    _require_raw_permission(user)
    try:
        data = catalog(lambda _name, permission: user.get("role") == ROLE_ADMIN or
                       user.get("permissions", {}).get(permission) is True)
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail="Business data query unavailable or timed out") from exc
    _log_ai("ai_business_datasets_read", user, {"datasetCount": len(data["datasets"])})
    return success_response(data, meta=_business_meta("catalog"))


@router.get("/business-data/{dataset}")
def ai_business_data(
    dataset: str,
    limit: int = Query(200, ge=1, le=1000),
    afterRowId: int = Query(0, ge=0, le=9223372036854775807),
    columns: list[str] | None = Query(None),
    filters: str | None = Header(None, alias="X-AI-Filters", max_length=8000),
    expectedImportId: int | None = Query(None, ge=0, le=9223372036854775807),
    user=Depends(require_ai_readonly),
):
    _require_business_permission(user, dataset)
    try:
        data = page(dataset, limit=limit, after_row_id=afterRowId, columns=columns,
                    filters=filters, expected_import_id=expectedImportId)
    except ImportChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail="Business data query unavailable or timed out") from exc
    _log_ai("ai_business_data_read", user, {"dataset": dataset, "returnedRows": data["returnedRows"],
                                              "filtered": filters is not None})
    return success_response(data, meta=_business_meta(dataset))


@router.get("/analyze/{dataset}")
def ai_analyze(
    dataset: str,
    groupBy: list[str] | None = Query(None),
    measure: str | None = Query(None),
    aggregation: str = Query("count", pattern="^(count|sum|avg|min|max)$"),
    filters: str | None = Header(None, alias="X-AI-Filters", max_length=8000),
    limit: int = Query(100, ge=1, le=500),
    user=Depends(require_ai_readonly),
):
    _require_business_permission(user, dataset)
    try:
        data = analyze(dataset, group_by=groupBy, measure=measure,
                       aggregation=aggregation, filters=filters, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail="Business data query unavailable or timed out") from exc
    _log_ai("ai_business_analysis_read", user, {"dataset": dataset, "aggregation": aggregation,
                                                  "groupBy": groupBy or [], "filtered": filters is not None,
                                                  "returnedRows": len(data["rows"])})
    return success_response(data, meta=_business_meta(dataset))


@router.get("/project-context")
def ai_project_context(user=Depends(require_ai_readonly)):
    _require_ai_permission(user, "kpi")
    data = {
        "project": "太平人寿网电多元条线经营分析看板",
        "version": get_app_version(),
        "businessLines": BUSINESS_LINES,
        "metrics": METRICS,
        "dashboardCards": DASHBOARD_KPI_CARDS,
        "displayConstraints": DISPLAY_CONSTRAINTS,
        "sourceLayers": {
            "dashboard": "既有看板API按业务规则计算，优先用于正式经营结论",
            "aggregates": "agg_*为数据库汇总结果；筛选、截止日和精度须按具体指标复核",
            "source": "performance/jingdai/hr_data/value_data为当前已存储的日常导入明细，不是Excel原样归档",
            "otherBusiness": "目标、荣誉、客户、网点等模块分表存储；目录仅列出当前账号可读的数据集",
        },
        "rules": [
            "每次分析标明来源、业务期间、数据截止日、单位、筛选范围和目标版本。",
            "缺失值不是零；达成率分母为正式目标，未配置目标时不可计算。",
            "转型业务与经代可能采用不同源表；保单、客户、人员的去重口径不能直接互换。",
            "通用分组统计只用于探索；正式指标以看板接口、metric-definitions及项目口径为准。",
        ],
    }
    _log_ai("ai_project_context_read", user, {})
    return success_response(data, meta=response_meta(metric="ai-project-context", data_source="project config"))


@router.get("/market-reports")
def ai_market_reports(limit: int = Query(24, ge=1, le=100), user=Depends(require_ai_readonly)):
    _require_raw_permission(user)
    _require_ai_permission(user, "market_analysis")
    reports = MarketAnalysisRepository().history(limit=limit)
    _log_ai("ai_market_reports_read", user, {"limit": limit})
    return success_response(reports, meta=response_meta(metric="ai-market-reports", data_source="published market reports"))


@router.get("/market-reports/{report_id}")
def ai_market_report(report_id: str, user=Depends(require_ai_readonly)):
    _require_raw_permission(user)
    _require_ai_permission(user, "market_analysis")
    report = MarketAnalysisRepository().get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到该期市场研判报告")
    _log_ai("ai_market_report_read", user, {"reportId": report_id})
    return success_response(report, meta=response_meta(metric="ai-market-report", data_source="published market reports"))


def _raw_meta():
    return response_meta(
        metric="ai-raw-data", data_source="Daily-import SQLite source tables",
        access="ai-readonly", unit="source",
        definitions={
            "scope": "四类日常导入表当前已存储的明细与字段，不是Excel文件或历次导入归档",
            "values": "保留SQLite字段名、数值、文本和null，不换算万元，不补零",
            "pagination": "按行游标分页；批量读取期间避免导入、重建或切换数据库，数据变化后从首页重读",
            "latestImportId": "最近已落库日常导入记录ID（success/partial），不是业务截止日或完整数据库快照版本",
        },
    )


@router.get("/raw-datasets")
def ai_raw_datasets(user=Depends(require_ai_readonly)):
    _require_raw_permission(user)
    data = list_raw_datasets()
    _log_ai("ai_raw_datasets_read", user, {})
    return success_response(data, meta=_raw_meta())


@router.get("/raw-data/{dataset}")
def ai_raw_data(
    dataset: str,
    limit: int = Query(200, ge=1, le=1000),
    afterRowId: int = Query(0, ge=0, le=9223372036854775807),
    columns: list[str] | None = Query(None),
    filters: str | None = Header(None, alias="X-AI-Filters", max_length=8000),
    expectedImportId: int | None = Query(None, ge=0, le=9223372036854775807),
    user=Depends(require_ai_readonly),
):
    _require_raw_permission(user)
    try:
        data = read_raw_page(
            dataset, limit=limit, after_row_id=afterRowId, columns=columns,
            filters=filters, expected_import_id=expectedImportId,
        )
    except ImportChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _log_ai("ai_raw_data_read", user, {
        "dataset": dataset, "limit": limit, "returnedRows": data["returnedRows"],
        "fieldCount": len(data["columns"]), "filtered": filters is not None,
    })
    return success_response(data, meta=_raw_meta())


@router.get("/openapi.json")
def ai_openapi(request: Request):
    public_base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base:
        base_url = public_base
    else:
        forwarded_proto = request.headers.get("x-forwarded-proto")
        host = request.headers.get("host") or request.url.netloc
        scheme = forwarded_proto or ("https" if host and not host.startswith(("127.0.0.1", "localhost")) else request.url.scheme)
        base_url = f"{scheme}://{host}".rstrip("/")
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Business Analysis AI Readonly API",
            "version": get_semver(),
            "description": "Read-only dashboard, business datasets and bounded analysis. Business rows require an account with ai_raw_data and the matching module permission; aggregate service tokens cannot read them.",
        },
        "servers": [{"url": base_url}],
        "components": {
            "securitySchemes": {
                "AIAccountBasic": {
                    "type": "http",
                    "scheme": "basic",
                    "description": "Recommended: use an active dashboard username and password over HTTPS.",
                },
                "AIReadonlyToken": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Compatibility: use a dashboard session token or AI_READONLY_TOKEN.",
                }
            }
        },
        "security": [{"AIAccountBasic": []}, {"AIReadonlyToken": []}],
        "paths": {
            "/api/ai/project-context": {"get": {
                "operationId": "readProjectContext",
                "summary": "Read project scope, business lines and calculation guidance",
                "responses": {"200": {"description": "Project and metric context"}},
            }},
            "/api/ai/market-reports": {"get": {
                "operationId": "listPublishedMarketReports",
                "summary": "List published market research reports",
                "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer", "default": 24, "minimum": 1, "maximum": 100}}],
                "responses": {"200": {"description": "Published report summaries"}},
            }},
            "/api/ai/market-reports/{report_id}": {"get": {
                "operationId": "readPublishedMarketReport",
                "summary": "Read one published market research report",
                "parameters": [{"name": "report_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Published report"}, "404": {"description": "Report not found"}},
            }},
            "/api/ai/business-datasets": {"get": {
                "operationId": "listBusinessDatasets",
                "summary": "List all business datasets this account can read and their live schema",
                "responses": {"200": {"description": "Business dataset catalog"},
                              "403": {"description": "ai_raw_data permission required"}},
            }},
            "/api/ai/business-data/{dataset}": {"get": {
                "operationId": "readBusinessRows",
                "summary": "Page through stored rows in an allowlisted business dataset",
                "description": "Use business-datasets to discover names and columns. X-AI-Filters is an ASCII JSON object. Operators: eq, gte, lte, in (up to 50 values), isNull. No arbitrary SQL. Pass nextAfterRowId until hasMore=false. expectedImportId only detects daily imports, not every database change.",
                "parameters": [
                    {"name": "dataset", "in": "path", "required": True, "schema": {"type": "string", "enum": list(BUSINESS_DATASETS)}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 200, "minimum": 1, "maximum": 1000}},
                    {"name": "afterRowId", "in": "query", "schema": {"type": "integer", "default": 0, "minimum": 0}},
                    {"name": "columns", "in": "query", "style": "form", "explode": True,
                     "schema": {"type": "array", "items": {"type": "string"}}},
                    {"name": "X-AI-Filters", "in": "header", "schema": {"type": "string", "maxLength": 8000}},
                    {"name": "expectedImportId", "in": "query", "schema": {"type": "integer", "minimum": 0}},
                ],
                "responses": {"200": {"description": "Bounded page of stored rows"},
                              "403": {"description": "AI detail or module permission required"}},
            }},
            "/api/ai/analyze/{dataset}": {"get": {
                "operationId": "analyzeBusinessDataset",
                "summary": "Group and aggregate stored business values with bounded output",
                "description": "Direct SQL aggregation of stored values, not an official KPI. Validate source, period, cutoff and unit against project-context and metric-definitions. Result may be truncated; narrow filters or grouping when truncated=true.",
                "parameters": [
                    {"name": "dataset", "in": "path", "required": True, "schema": {"type": "string", "enum": list(BUSINESS_DATASETS)}},
                    {"name": "groupBy", "in": "query", "style": "form", "explode": True,
                     "schema": {"type": "array", "maxItems": 3, "items": {"type": "string"}}},
                    {"name": "measure", "in": "query", "schema": {"type": "string"}},
                    {"name": "aggregation", "in": "query", "schema": {"type": "string", "enum": ["count", "sum", "avg", "min", "max"], "default": "count"}},
                    {"name": "X-AI-Filters", "in": "header", "schema": {"type": "string", "maxLength": 8000}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 100, "minimum": 1, "maximum": 500}},
                ],
                "responses": {"200": {"description": "Grouped statistical result"},
                              "403": {"description": "AI detail or module permission required"}},
            }},
            "/api/ai/raw-datasets": {"get": {
                "operationId": "listDailyImportDatasets",
                "summary": "List the four daily-import datasets and all stored source columns",
                "responses": {"200": {"description": "Dataset availability, column names and SQLite types"},
                              "401": {"description": "Authentication required"},
                              "403": {"description": "ai_raw_data permission required"}},
            }},
            "/api/ai/raw-data/{dataset}": {"get": {
                "operationId": "readDailyImportRows",
                "summary": "Read every stored source field using bounded cursor pages",
                "description": "Defaults to all columns and all periods. Preserve source units and nulls. Repeat with nextAfterRowId until hasMore=false. Keep columns/filters fixed across pages and pass latestImportId as expectedImportId; restart on 409. Avoid concurrent imports/rebuilds during bulk reads. Requires an account with ai_raw_data permission.",
                "parameters": [
                    {"name": "dataset", "in": "path", "required": True,
                     "schema": {"type": "string", "enum": ["performance", "jingdai", "hr_data", "value_data"]}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 200, "minimum": 1, "maximum": 1000}},
                    {"name": "afterRowId", "in": "query", "schema": {"type": "integer", "default": 0, "minimum": 0, "maximum": 9223372036854775807}},
                    {"name": "columns", "in": "query", "style": "form", "explode": True,
                     "description": "Optional repeated query parameter; omit to return every stored column.",
                     "schema": {"type": "array", "items": {"type": "string"}}},
                    {"name": "X-AI-Filters", "in": "header", "schema": {"type": "string", "maxLength": 8000},
                     "description": "ASCII-escaped JSON object of exact source-column matches combined with AND (maximum 20). Encode Chinese keys/values with JSON Unicode escapes, e.g. json.dumps(filters, ensure_ascii=True). Values: string, finite number, or null for IS NULL. Keep filter values out of URLs and access logs."},
                    {"name": "expectedImportId", "in": "query", "schema": {"type": "integer", "minimum": 0, "maximum": 9223372036854775807},
                     "description": "latestImportId from the first page. Detects newly applied daily imports (success/partial); not an immutable database snapshot."},
                ],
                "responses": {
                    "200": {"description": "data contains dataset, columns, rows, returnedRows, limit, afterRowId, hasMore, nextAfterRowId and latestImportId; meta explains units and scope"},
                    "400": {"description": "Invalid source column or filter"},
                    "401": {"description": "Authentication required"},
                    "403": {"description": "ai_raw_data permission required"},
                    "404": {"description": "Unknown or not imported dataset"},
                    "409": {"description": "Imported data changed; restart pagination"},
                    "422": {"description": "Invalid query parameter"},
                },
            }},
            "/api/ai/dashboard-snapshot": {
                "get": {
                    "summary": "Read dashboard KPI and organization snapshot",
                    "parameters": [
                        {"name": "year", "in": "query", "schema": {"type": "integer", "default": DEFAULT_YEAR}},
                        {"name": "includeOrgDetail", "in": "query", "schema": {"type": "boolean", "default": False}},
                    ],
                    "responses": {"200": {"description": "Dashboard snapshot"}},
                }
            },
            "/api/ai/kpi": {"get": {"summary": "Read KPI data", "responses": {"200": {"description": "KPI data"}}}},
            "/api/ai/org-summary": {"get": {"summary": "Read organization summary", "responses": {"200": {"description": "Organization summary"}}}},
            "/api/ai/team-summary": {"get": {"summary": "Read team summary", "responses": {"200": {"description": "Team summary"}}}},
            "/api/ai/metric-definitions": {"get": {"summary": "Read metric definitions", "responses": {"200": {"description": "Metric definitions"}}}},
        },
    }
