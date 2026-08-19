from __future__ import annotations

import calendar
import math
from collections import defaultdict
from datetime import date, datetime
from typing import Literal

from db.connection import get_db
from branch_analysis.repository import read_reference


BUSINESS_MODES = {"证券", "证保"}
GENERIC_BRANCH_NAMES = {"广发证券股份有限公司", "中信证券股份有限公司"}
PeriodType = Literal["year", "quarter", "month"]


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _number(value) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    for fmt, size in (("%Y-%m-%d", 10), ("%Y/%m/%d", 10), ("%Y%m%d", 8), ("%Y-%m", 7)):
        try:
            return datetime.strptime(text[:size], fmt).date()
        except ValueError:
            continue
    return None


def _code(value) -> str:
    text = _text(value)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.lstrip("0") if text.isdigit() else text


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _previous_cutoff(cutoff: date) -> date:
    day = min(cutoff.day, calendar.monthrange(cutoff.year - 1, cutoff.month)[1])
    return date(cutoff.year - 1, cutoff.month, day)


def _period_window(
    year: int,
    cutoff: date,
    period_type: PeriodType,
    period_value: int | None,
) -> tuple[date, date, str]:
    if period_type == "year":
        start = date(year, 1, 1)
        natural_end = date(year, 12, 31)
        label = f"{year}年度累计"
    elif period_type == "quarter":
        if period_value not in {1, 2, 3, 4}:
            raise ValueError("季度筛选必须选择1至4季度")
        start_month = (period_value - 1) * 3 + 1
        end_month = start_month + 2
        start = date(year, start_month, 1)
        natural_end = date(year, end_month, calendar.monthrange(year, end_month)[1])
        label = f"{year}年Q{period_value}"
    elif period_type == "month":
        if period_value is None or not 1 <= period_value <= 12:
            raise ValueError("月度筛选必须选择1至12月")
        start = date(year, period_value, 1)
        natural_end = date(year, period_value, calendar.monthrange(year, period_value)[1])
        label = f"{year}年{period_value}月"
    else:
        raise ValueError("统计周期仅支持年度累计、季度或月度")

    if cutoff < start:
        raise ValueError(f"{label}尚未到达统计截止日，暂无可统计数据")
    return start, min(cutoff, natural_end), label


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _performance_cutoff(conn, year: int | None = None) -> date | None:
    if year is None:
        value = conn.execute(
            'SELECT MAX("年月日") FROM performance WHERE "年月日" IS NOT NULL'
        ).fetchone()[0]
    else:
        value = conn.execute(
            '''
            SELECT MAX("年月日")
            FROM performance
            WHERE "年月日" >= ? AND "年月日" < ?
            ''',
            (f"{year:04d}-01-01", f"{year + 1:04d}-01-01"),
        ).fetchone()[0]
    return _date(value)


def _performance_rows(conn) -> list[dict]:
    required = {
        "年月日",
        "销售机构名称",
        "业务模式",
        "人员工号",
        "投保单号",
        "证券方营业网点名称",
        "证券方销售人员工号",
        "期交保费",
    }
    columns = _columns(conn, "performance")
    missing = required - columns
    if missing:
        raise ValueError(f"当前业绩库缺少网点分析字段：{'、'.join(sorted(missing))}")
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT rowid AS source_row, "年月日", "销售机构名称", "业务模式",
                   "人员工号", "投保单号", "证券方营业网点名称",
                   "证券方销售人员工号", "期交保费"
            FROM performance
            WHERE "业务模式" IN ('证券', '证保')
            """
        ).fetchall()
    ]


def _aggregate(rows: list[dict], start: date, end: date) -> dict:
    policies: dict[str, dict] = {}
    for row in rows:
        business_date = _date(row["年月日"])
        if not business_date or not start <= business_date <= end:
            continue
        key = _text(row["投保单号"]) or f"row-{row['source_row']}"
        item = policies.setdefault(
            key,
            {
                "premium": 0.0,
                "branch": "",
                "org": "",
                "seller": "",
                "agent": "",
                "dates": set(),
            },
        )
        item["premium"] += _number(row["期交保费"])
        item["branch"] = item["branch"] or _text(row["证券方营业网点名称"])
        item["org"] = item["org"] or _text(row["销售机构名称"])
        item["seller"] = item["seller"] or _code(row["证券方销售人员工号"])
        item["agent"] = item["agent"] or _code(row["人员工号"])
        item["dates"].add(business_date)

    net_by_branch: dict[str, float] = defaultdict(float)
    for policy in policies.values():
        net_by_branch[policy["branch"]] += policy["premium"]

    positive = {key: value for key, value in policies.items() if value["premium"] > 0}
    branches: dict[str, dict] = {}
    for policy in positive.values():
        name = policy["branch"]
        branch = branches.setdefault(
            name,
            {"premium": 0.0, "policies": 0, "orgs": set(), "sellers": set(), "agents": set(), "months": set()},
        )
        branch["policies"] += 1
        if policy["org"]:
            branch["orgs"].add(policy["org"])
        if policy["seller"]:
            branch["sellers"].add(policy["seller"])
        if policy["agent"]:
            branch["agents"].add(policy["agent"])
        branch["months"].update(item.month for item in policy["dates"])
    for name, branch in branches.items():
        branch["premium"] = net_by_branch.get(name, 0.0)
    return {
        "premium": sum(policy["premium"] for policy in policies.values()),
        "policies": len(positive),
        "sellers": {policy["seller"] for policy in positive.values() if policy["seller"]},
        "agents": {policy["agent"] for policy in positive.values() if policy["agent"]},
        "branches": branches,
    }


def _branch_status(current: bool, previous: bool) -> str:
    if current and previous:
        return "持续经营"
    if current:
        return "新增/恢复"
    if previous:
        return "待唤醒"
    return "未活动"


def _wan(value: float) -> float:
    return round(value / 10000, 4)


def analyze_branch_network(
    year: int | None = None,
    as_of: date | None = None,
    period_type: PeriodType = "year",
    period_value: int | None = None,
) -> dict:
    with get_db() as conn:
        reference, batch = read_reference(conn)
        if not reference:
            raise ValueError("尚未导入证保网点参考表")
        source_cutoff = _performance_cutoff(conn, year)
        if source_cutoff is None:
            if year is None:
                raise ValueError("当前业绩库没有可用业务日期")
            raise ValueError(f"当前业绩库没有{year}年业务数据")
        if year is None:
            year = source_cutoff.year
        performance = _performance_rows(conn)

    if as_of and as_of.year != year:
        raise ValueError("统计截止日必须属于所选年份")
    cutoff = min(as_of, source_cutoff) if as_of else source_cutoff

    period_start, period_end, period_label = _period_window(
        year,
        cutoff,
        period_type,
        period_value,
    )
    previous_period_start = date(year - 1, period_start.month, period_start.day)
    previous_cutoff = _previous_cutoff(period_end)
    current = _aggregate(performance, period_start, period_end)
    previous = _aggregate(performance, previous_period_start, previous_cutoff)
    period_branch_dates = [
        item
        for row in performance
        if (item := _date(row["年月日"])) and period_start <= item <= period_end
    ]
    last_branch_business_date = max(period_branch_dates, default=None)

    regular = [row for row in reference if row["include_in_regular_count"] == 1]
    referral = [row for row in reference if row["branch_type"] == "转介绍网点"]
    regular_names = {row["branch_name"] for row in regular}
    referral_names = {row["branch_name"] for row in referral}
    referral_parents = {row["parent_name"] for row in referral if row["parent_name"]}

    branch_rows = []
    for ref in regular:
        current_item = current["branches"].get(ref["branch_name"])
        previous_item = previous["branches"].get(ref["branch_name"])
        current_premium = current_item["premium"] if current_item else 0.0
        previous_premium = previous_item["premium"] if previous_item else 0.0
        branch_rows.append(
            {
                "referenceId": ref["reference_id"],
                "branch": ref["branch_name"],
                "parent": ref["parent_name"],
                "province": ref["province"],
                "city": ref["city"],
                "grade": ref["grade"],
                "project": ref["project"],
                "subproject": ref["subproject"],
                "locality": ref["locality"],
                "status": _branch_status(bool(current_item), bool(previous_item)),
                "org": "、".join(sorted(current_item["orgs"])) if current_item else "",
                "premiumWan": _wan(current_premium),
                "previousPremiumWan": _wan(previous_premium),
                "premiumChange": _ratio(current_premium, previous_premium),
                "policies": current_item["policies"] if current_item else 0,
                "averageCaseWan": _wan(current_premium / current_item["policies"]) if current_item and current_item["policies"] else None,
                "externalSellers": len(current_item["sellers"]) if current_item else 0,
                "internalAgents": len(current_item["agents"]) if current_item else 0,
                "activeMonths": len(current_item["months"]) if current_item else 0,
            }
        )
    branch_rows.sort(key=lambda item: (item["premiumWan"], item["policies"]), reverse=True)

    referral_rows = [
        {
            "referenceId": row["reference_id"],
            "branch": row["branch_name"],
            "parent": row["parent_name"],
            "province": row["province"],
            "city": row["city"],
            "project": row["project"],
            "subproject": row["subproject"],
            "locality": row["locality"],
        }
        for row in referral
    ]

    active_regular = sum(item["status"] in {"持续经营", "新增/恢复"} for item in branch_rows)
    matched_regular_premium = sum(
        item["premium"] for name, item in current["branches"].items() if name in regular_names
    )
    referral_premium = sum(
        item["premium"]
        for name, item in current["branches"].items()
        if name in referral_names or name in referral_parents
    )
    referral_outside_regular_premium = sum(
        item["premium"]
        for name, item in current["branches"].items()
        if (name in referral_names or name in referral_parents) and name not in regular_names
    )
    referral_policies = sum(
        item["policies"]
        for name, item in current["branches"].items()
        if name in referral_names or name in referral_parents
    )
    referral_sellers = set()
    for name, item in current["branches"].items():
        if name in referral_names or name in referral_parents:
            referral_sellers.update(item["sellers"])

    unmatched = []
    for name, item in current["branches"].items():
        if name not in regular_names and name not in referral_names and name not in referral_parents:
            unmatched.append(
                {
                    "branch": name or "（网点缺失）",
                    "premiumWan": _wan(item["premium"]),
                    "policies": item["policies"],
                }
            )
    unmatched.sort(key=lambda item: item["premiumWan"], reverse=True)

    def grouped(field: str) -> list[dict]:
        groups: dict[str, dict] = {}
        by_name = {item["branch"]: item for item in branch_rows}
        for ref in regular:
            label = ref[field] or "未标注"
            group = groups.setdefault(label, {"label": label, "stock": 0, "active": 0, "premiumWan": 0.0})
            group["stock"] += 1
            item = by_name[ref["branch_name"]]
            if item["status"] in {"持续经营", "新增/恢复"}:
                group["active"] += 1
            group["premiumWan"] += item["premiumWan"]
        for group in groups.values():
            group["activityRate"] = _ratio(group["active"], group["stock"])
            group["premiumWan"] = round(group["premiumWan"], 4)
        return sorted(groups.values(), key=lambda item: item["premiumWan"], reverse=True)

    matched_sorted = sorted(
        (item["premium"] for name, item in current["branches"].items() if name in regular_names),
        reverse=True,
    )
    top5 = sum(matched_sorted[:5])
    total_premium = current["premium"]
    # “广发证券股份有限公司”本身属于147个常规主网点，86个转介绍子网点
    # 归属于该主网点。主网点保费已经包含在常规匹配额中，不得再次相加。
    matched_total = matched_regular_premium + referral_outside_regular_premium

    return {
        "meta": {
            "year": year,
            "periodType": period_type,
            "periodValue": period_value if period_type != "year" else None,
            "periodLabel": period_label,
            "periodStart": period_start.isoformat(),
            "asOf": period_end.isoformat(),
            "previousPeriodStart": previous_period_start.isoformat(),
            "previousAsOf": previous_cutoff.isoformat(),
            "performanceCutoff": source_cutoff.isoformat(),
            "lastBranchBusinessDate": last_branch_business_date.isoformat() if last_branch_business_date else None,
            "referenceBatch": batch,
            "unit": "万元",
        },
        "summary": {
            "premiumWan": _wan(total_premium),
            "previousPremiumWan": _wan(previous["premium"]),
            "premiumChange": _ratio(total_premium, previous["premium"]),
            "policies": current["policies"],
            "averageCaseWan": _wan(total_premium / current["policies"]) if current["policies"] else None,
            "externalSellers": len(current["sellers"]),
            "regularStock": len(regular),
            "activeRegular": active_regular,
            "inactiveRegular": len(regular) - active_regular,
            "regularActivityRate": _ratio(active_regular, len(regular)),
            "matchedRegularPremiumWan": _wan(matched_regular_premium),
            "referralStockExcluded": len(referral),
            "referralPremiumWan": _wan(referral_premium),
            "referralPremiumShare": _ratio(referral_premium, total_premium),
            "referralPolicies": referral_policies,
            "referralSellers": len(referral_sellers),
            "matchedPremiumRate": _ratio(matched_total, total_premium),
            "unmatchedPremiumWan": _wan(total_premium - matched_total),
            "top5RegularShare": _ratio(top5, matched_regular_premium),
        },
        "levels": grouped("grade"),
        "projects": grouped("project"),
        "regularBranches": branch_rows,
        "referralBranches": referral_rows,
        "quality": {
            "referenceRows": len(reference),
            "regularRows": len(regular),
            "referralRows": len(referral),
            "unmatchedBranches": unmatched,
            "definitions": {
                "regularCount": "常规网点来自参数表AA2-AA148，共147个；作为网点数和活动率分母。",
                "referralCount": "参数表AA151-AA237的有效转介绍网点归属于广发证券股份有限公司，共86个；常规统计不纳入网点数。",
                "activity": "统计期内至少有1件净期交保费大于0的保单，认定为活动网点。",
                "referralPerformance": "业绩底表以广发证券股份有限公司汇总时，只展示转介绍总体贡献，不平均分摊到86个子网点。",
                "dataCutoff": "数据截止日取生产业绩基表全业务的最新覆盖日；证保最后出单日单列，不再替代数据截止日。",
            },
        },
    }
