from fastapi import APIRouter, Depends, Query

from api.params import DashboardYearQuery
from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from config.metrics import METRICS
from db import get_platform_data
from db.repositories.team_enhanced import get_team_enhanced_analysis
from services.response import response_meta, success_response

router = APIRouter(prefix="/api", tags=["team"])


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item and item.strip()]


def _split_months(value: str | None) -> list[int]:
    months = []
    for item in _split_csv(value):
        try:
            month = int(item)
        except ValueError:
            continue
        if 1 <= month <= 12 and month not in months:
            months.append(month)
    return sorted(months)


@router.get("/team-analysis")
def team_analysis(year: DashboardYearQuery = DEFAULT_YEAR, _user=Depends(require_permission("team"))):
    data = get_platform_data(year)
    return success_response(
        {"year": year, "hr": data.get("hr", [])},
        meta=response_meta(
            metric="team-analysis",
            unit="人/万元",
            data_source="agg_hr_data",
            year=year,
            definitions={
                k: METRICS[k]
                for k in ["activity_rate", "avg_premium", "avg_productivity"]
                if k in METRICS
            },
        ),
    )


@router.get("/team-enhanced-analysis")
def team_enhanced_analysis(
    year: DashboardYearQuery = DEFAULT_YEAR,
    month: int | None = Query(None, ge=1, le=12),
    months: str | None = Query(None),
    periodType: str = Query("month", pattern="^(year|quarter|month)$"),
    periodValue: int | None = Query(None, ge=1, le=12),
    businessLines: str | None = Query(None),
    orgs: str | None = Query(None),
    scope: str = Query("all", pattern="^(all|active)$"),
    _user=Depends(require_permission("team_enhanced")),
):
    data = get_team_enhanced_analysis(
        year=year,
        month=month,
        period_type=periodType,
        period_value=periodValue,
        months=_split_months(months),
        business_lines=_split_csv(businessLines),
        orgs=_split_csv(orgs),
        scope=scope,
    )
    return success_response(
        data,
        meta=response_meta(
            metric="team-enhanced-analysis",
            unit="人、万元、%",
            data_source="hr_data LEFT JOIN performance",
            year=year,
            month=data.get("month"),
            periodType=data.get("periodType"),
            periodValue=data.get("periodValue"),
            months=data.get("months"),
            definitions={
                "sample": "单月以 hr_data 当月月末在职人员为样本；多月以所选月份内任一月末在职过的人员去重为样本，机构/司龄/职等取所选月份中最后一个月末在职月份。",
                "scope_all": "默认样本为所选期间内月末在职人员；结构占比按月末在职样本计算。",
                "scope_active": "仅看所选期间期交保费大于 0 的正产能人员，用于补充观察，不作为默认结构口径。",
                "productivity": "单月产能 = 月末在职人员当月个人期交保费 / 10000；多月产能 = 所选月份内月末在职人员个人累计期交保费 / 10000，单位为万元。",
                "highProductivity": "高产能人力仅展示OTO、证保，按个人累计期交保费划分[60万,100万)、[100万,150万)、[150万,300万)、[300万,500万)、[500万,1000万)、[1000万,+)六档。人数占比和保费占比分别以同一业务模式或同一机构+业务模式的全部月末在职样本人数、累计期交保费为分母。",
                "standardManpower": "标准人力仅统计 OTO 与证保：OTO 为月末在职且当月折算保费/标准保费>=2万元；证保为月末在职且当月折算保费/标准保费>=3万元。2026年产品4281按10年及以上交期处理，标准保费按期交保费全额计入。保费贡献按标准人力对应期交保费计算。",
                "percentile": "P25/P50/P75 按人员产能升序后线性插值计算；零/负产能人员纳入默认样本；P 值人数为达到该阈值及以上的人数。",
                "businessLine": "业务模式统一映射：证券=证保，网服=蚁桥，OTO保持不变。",
                "filters": "机构和业务模式筛选与队伍趋势联动；经代无队伍人力基表，不进入本模块。",
            },
        ),
    )
