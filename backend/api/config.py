"""运行时配置 API — 业务线、指标等前后端统一配置。"""
from fastapi import APIRouter

from config.business_lines import BUSINESS_LINES
from config.metrics import DASHBOARD_KPI_CARDS, DISPLAY_CONSTRAINTS, METRICS
from services.response import success_response

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/business-lines")
def get_business_lines():
    """返回所有业务线配置。

    前端启动时调用，替换硬编码的业务线名称、颜色、能力标记等。
    返回 BUSINESS_LINES 列表（不含内部查表字段）。
    """
    safe_lines = []
    for item in BUSINESS_LINES:
        safe_lines.append({
            "code": item["code"],
            "name": item["name"],
            "displayName": item.get("displayName", item["name"]),
            "color": item.get("color", "#94a3b8"),
            "order": item.get("order", 99),
            "isIncludedInTotal": item.get("isIncludedInTotal", True),
            "supportOrgDimension": item.get("supportOrgDimension", True),
            "supportTeamDimension": item.get("supportTeamDimension", True),
            "supportDailyTrend": item.get("supportDailyTrend", True),
            "aliases": item.get("aliases", []),
        })
    return success_response(safe_lines)


@router.get("/metrics")
def get_metrics():
    """返回所有指标定义与口径。

    前端启动时调用，获取统一的指标公式、单位和不可计算规则。
    复杂指标在 meta.definitions 中返回口径说明。
    """
    return success_response(
        {
            "metrics": METRICS,
            "displayConstraints": DISPLAY_CONSTRAINTS,
            "dashboardKpiCards": DASHBOARD_KPI_CARDS,
        },
        meta={
            "metric": "config-metrics",
            "unit": "-",
            "dataSource": "config/metrics.py",
            "definitions": METRICS,
        },
    )
