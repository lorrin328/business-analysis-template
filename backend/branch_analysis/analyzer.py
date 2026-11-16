from __future__ import annotations

import calendar
import math
from collections import defaultdict
from datetime import date, datetime
from typing import Literal

from db.connection import get_db
from branch_analysis.repository import read_reference


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


def _performance_rows(conn) -> list[tuple[date, dict]]:
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
    payment_col = ', "缴费年限"' if "缴费年限" in columns else ', NULL AS "缴费年限"'
    rows = conn.execute(
        f"""
        SELECT rowid AS source_row, "年月日", "销售机构名称", "人员工号", "投保单号",
               "证券方营业网点名称", "证券方销售人员工号", "期交保费"{payment_col}
        FROM performance
        WHERE "业务模式" IN ('证券', '证保')
        ORDER BY rowid
        """
    )
    result = []
    for row in rows:
        business_date = _date(row["年月日"])
        if business_date:
            result.append((business_date, dict(row)))
    return result


LARGE_POLICY_THRESHOLD = 100_000_000  # 分
MATRIX_PREMIUM_WAN = 20
MATRIX_ACTIVE_MONTHS = 2
CAPACITY_TIERS = (
    (1, "≥100万元"),
    (2, "50万至不足100万元"),
    (3, "20万至不足50万元"),
    (4, "大于0且不足20万元"),
    (5, "净期交≤0"),
)


def _payment_years(value) -> int | None:
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    return int(years) if years >= 0 and years.is_integer() else None


def _empty_metrics() -> dict:
    return {
        "premium": 0,
        "regular_premium": 0,
        "large_premium": 0,
        "negative_premium": 0,
        "unknown_policy_premium": 0,
        "known_term_premium": 0,
        "long_term_10y_premium": 0,
        "policies": 0,
        "large_policies": 0,
        "unknown_policy_rows": 0,
        "orgs": set(),
        "sellers": set(),
        "agents": set(),
        "active_days": set(),
    }


def _add_policy(metrics: dict, policy: dict, identified: bool) -> None:
    premium = policy["premium"]
    metrics["premium"] += premium
    metrics["orgs"].update(policy["orgs"])
    if not identified:
        metrics["unknown_policy_rows"] += 1
    if premium < 0:
        metrics["negative_premium"] += premium
    if premium <= 0:
        return
    if not identified:
        metrics["unknown_policy_premium"] += premium
        return

    metrics["policies"] += 1
    if premium >= LARGE_POLICY_THRESHOLD:
        metrics["large_premium"] += premium
        metrics["large_policies"] += 1
    else:
        metrics["regular_premium"] += premium

    if len(policy["terms"]) == 1:
        metrics["known_term_premium"] += premium
        if next(iter(policy["terms"])) >= 10:
            metrics["long_term_10y_premium"] += premium
    if policy["seller"]:
        metrics["sellers"].add(policy["seller"])
    if policy["agent"]:
        metrics["agents"].add(policy["agent"])
    metrics["active_days"].update(day for day, net in policy["daily"].items() if net > 0)


def _aggregate(rows: list[tuple[date, dict]]) -> dict:
    policies: dict[tuple[str, str | int], dict] = {}
    # 同一期间优先用正向明细归属，日期及源行号确定同方向记录的顺序。
    for business_date, row in rows:
        policy_number = _text(row["投保单号"])
        key = ("policy", policy_number) if policy_number else ("row", row["source_row"])
        amount = round(_number(row["期交保费"]) * 100)
        policy = policies.get(key)
        if policy is None:
            policy = {
                "premium": 0, "orgs": set(), "terms": set(), "daily": defaultdict(int),
                "branch": "", "seller": "", "agent": "", "priorities": {},
            }
            policies[key] = policy
        policy["premium"] += amount
        policy["daily"][business_date] += amount
        org = _text(row["销售机构名称"])
        if org:
            policy["orgs"].add(org)
        term = _payment_years(row["缴费年限"])
        if term is not None:
            policy["terms"].add(term)
        priority = (amount <= 0, business_date, row["source_row"])
        for field, value in (
            ("branch", _text(row["证券方营业网点名称"])),
            ("seller", _code(row["证券方销售人员工号"])),
            ("agent", _code(row["人员工号"])),
        ):
            if value and (not policy[field] or priority < policy["priorities"][field]):
                policy[field] = value
                policy["priorities"][field] = priority

    total = _empty_metrics()
    branches: dict[str, dict] = {}
    for (kind, _), policy in policies.items():
        name = policy["branch"]
        if name not in branches:
            branches[name] = _empty_metrics()
        _add_policy(total, policy, kind == "policy")
        _add_policy(branches[name], policy, kind == "policy")
    return {**total, "branches": branches}


def _branch_status(current: bool, previous: bool) -> str:
    if current and previous:
        return "持续经营"
    if current:
        return "新增/恢复"
    if previous:
        return "待唤醒"
    return "未活动"


def _wan(value: int | float) -> float:
    return round(value / 1_000_000, 6)


def _tier_id(premium: int) -> int:
    for tier, threshold in ((1, 100), (2, 50), (3, 20)):
        if premium >= threshold * 1_000_000:
            return tier
    return 4 if premium > 0 else 5


def _structure(metrics: dict) -> dict:
    regular = metrics["regular_premium"]
    large = metrics["large_premium"]
    missing_policy = metrics["unknown_policy_premium"]
    known_term = metrics["known_term_premium"]
    return {
        "regularPremiumWan": _wan(regular),
        "largePremiumWan": _wan(large),
        "netNegativePremiumWan": _wan(metrics["negative_premium"]),
        "unclassifiedPositivePremiumWan": _wan(missing_policy),
        "largePolicies": metrics["large_policies"],
        "largeShare": _ratio(large, regular + large),
        "longTerm10yPremiumWan": _wan(metrics["long_term_10y_premium"]) if known_term else None,
        "longTerm10yShare": _ratio(metrics["long_term_10y_premium"], known_term),
        "knownTermPremiumWan": _wan(known_term),
        "unknownTermPositivePremiumWan": _wan(regular + large - known_term),
        "termCoverage": _ratio(known_term, regular + large),
    }


def _month_start(value: date, offset: int = 0) -> date:
    year, month = divmod(value.year * 12 + value.month - 1 + offset, 12)
    return date(year, month + 1, 1)


def _monthly_metrics(rows: list[tuple[date, dict]], start: date, end: date) -> list[tuple[date, dict]]:
    by_month = defaultdict(list)
    for entry in rows:
        business_date, _ = entry
        by_month[(business_date.year, business_date.month)].append(entry)
    months = []
    month = _month_start(start)
    while month <= end:
        months.append((month, _aggregate(by_month[(month.year, month.month)])))
        month = _month_start(month, 1)
    return months


def _active_month_counts(monthly: list[tuple[date, dict]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for _, metrics in monthly:
        for name, branch in metrics["branches"].items():
            if branch["policies"]:
                counts[name] += 1
    return counts


def _matrix(
    period_type: PeriodType,
    period_end: date,
    coverage_start: date | None,
    performance: list[tuple[date, dict]],
    branch_rows: list[dict],
) -> tuple[dict | None, list[dict]]:
    if period_type == "month":
        return None, []
    month_end = calendar.monthrange(period_end.year, period_end.month)[1]
    last_month = _month_start(period_end, 0 if period_end.day == month_end else -1)
    start = _month_start(last_month, -2)
    end = last_month.replace(day=calendar.monthrange(last_month.year, last_month.month)[1])
    window = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "available": bool(coverage_start and coverage_start <= start),
        "premiumThresholdWan": MATRIX_PREMIUM_WAN,
        "activeMonthsThreshold": MATRIX_ACTIVE_MONTHS,
    }
    if not window["available"]:
        return window, []
    rows = [entry for entry in performance if start <= entry[0] <= end]
    window_metrics = _aggregate(rows)["branches"]
    active_months = _active_month_counts(_monthly_metrics(rows, start, end))
    empty = _empty_metrics()
    points = []
    for branch in branch_rows:
        metrics = window_metrics.get(branch["branch"], empty)
        months = active_months.get(branch["branch"], 0)
        high_premium = metrics["premium"] >= MATRIX_PREMIUM_WAN * 1_000_000
        high_activity = months >= MATRIX_ACTIVE_MONTHS
        code = {(True, True): "I", (True, False): "II", (False, True): "III", (False, False): "IV"}[
            high_premium, high_activity
        ]
        points.append({
            "branch": branch["branch"],
            "parent": branch["parent"],
            "grade": branch["grade"],
            "locality": branch["locality"],
            "premiumWan": _wan(metrics["premium"]),
            "regularPremiumWan": _wan(metrics["regular_premium"]),
            "largePremiumWan": _wan(metrics["large_premium"]),
            "policies": metrics["policies"],
            "activeMonths": months,
            "externalSellers": len(metrics["sellers"]),
            "quadrant": code,
            "quadrantLabel": f'产能{"达到" if high_premium else "低于"}分界 · 出单{"达到" if high_activity else "低于"}分界',
        })
    return window, points


def _branch_row(ref: dict, current: dict, previous: dict, active_months: int) -> dict:
    current_premium, previous_premium = current["premium"], previous["premium"]
    tier = _tier_id(current_premium)
    return {
        "referenceId": ref["reference_id"],
        "branch": ref["branch_name"],
        "parent": ref["parent_name"],
        "province": ref["province"],
        "city": ref["city"],
        "grade": ref["grade"],
        "project": ref["project"],
        "subproject": ref["subproject"],
        "locality": ref["locality"],
        "status": _branch_status(bool(current["policies"]), bool(previous["policies"])),
        "org": "、".join(sorted(current["orgs"])),
        "previousOrg": "、".join(sorted(previous["orgs"])),
        "previousOrgs": sorted(previous["orgs"]),
        "currentOrgs": sorted(current["orgs"]),
        "orgs": sorted(current["orgs"] | previous["orgs"]),
        "premiumWan": _wan(current_premium),
        "previousPremiumWan": _wan(previous_premium),
        "premiumChange": _ratio(current_premium, previous_premium) if previous_premium > 0 else None,
        "policies": current["policies"],
        "previousPolicies": previous["policies"],
        "averageCaseWan": _wan(current_premium / current["policies"]) if current["policies"] else None,
        "externalSellers": len(current["sellers"]),
        "internalAgents": len(current["agents"]),
        "activeMonths": active_months,
        "activeDays": len(current["active_days"]),
        "tier": tier,
        "tierName": dict(CAPACITY_TIERS)[tier],
        "frequencyCategory": f"{active_months}个出单月",
        **_structure(current),
    }


def _group_metrics(branch_rows: list[dict], current: dict, field: str) -> list[dict]:
    groups = defaultdict(list)
    for branch in branch_rows:
        groups[branch[field] or "未标注"].append(branch)
    results = []
    empty = _empty_metrics()
    for label, rows in groups.items():
        metrics = [current["branches"].get(row["branch"], empty) for row in rows]
        summed = _empty_metrics()
        for item in metrics:
            for key in ("premium", "regular_premium", "large_premium", "negative_premium", "unknown_policy_premium",
                        "known_term_premium", "long_term_10y_premium", "policies", "large_policies"):
                summed[key] += item[key]
            summed["sellers"].update(item["sellers"])
        active = sum(bool(row["policies"]) for row in rows)
        stock = len(rows)
        premium = summed["premium"]
        sellers = len(summed["sellers"])
        policies = summed["policies"]
        results.append({
            "label": label,
            "stock": stock,
            "active": active,
            "activityRate": _ratio(active, stock),
            "premiumWan": _wan(premium),
            "policies": policies,
            "sellers": sellers,
            "averageCaseWan": _wan(premium / policies) if policies else None,
            "averageStaffProductivityWan": _wan(premium / sellers) if sellers else None,
            "averageBranchPremiumWan": _wan(premium / stock),
            **_structure(summed),
        })
    return sorted(results, key=lambda item: item["premiumWan"], reverse=True)


def _concentration(branch_rows: list[dict], current: dict) -> dict:
    ranked = sorted(
        [(current["branches"][row["branch"]]["premium"], row) for row in branch_rows
         if row["branch"] in current["branches"] and current["branches"][row["branch"]]["premium"] > 0],
        key=lambda item: item[0],
        reverse=True,
    )
    positive_total = sum(premium for premium, _ in ranked)
    cumulative = 0
    series = []
    for rank, (premium, row) in enumerate(ranked[:30], 1):
        cumulative += premium
        series.append({
            "rank": rank,
            "branch": row["branch"],
            "shortName": row["branch"].removeprefix(row["parent"]) or row["branch"],
            "premiumWan": _wan(premium),
            "regularPremiumWan": row["regularPremiumWan"],
            "largePremiumWan": row["largePremiumWan"],
            "cumPremiumWan": _wan(cumulative),
            "cumShare": _ratio(cumulative, positive_total),
        })
    front_count = math.ceil(len(branch_rows) / 5)
    return {
        "top5Share": _ratio(sum(premium for premium, _ in ranked[:5]), positive_total),
        "top10Share": _ratio(sum(premium for premium, _ in ranked[:10]), positive_total),
        "top20Share": _ratio(sum(premium for premium, _ in ranked[:20]), positive_total),
        "pareto20PercentCount": front_count,
        "pareto20PercentShare": _ratio(sum(premium for premium, _ in ranked[:front_count]), positive_total),
        "series": series,
    }


def analyze_branch_network(
    year: int | None = None,
    as_of: date | None = None,
    period_type: PeriodType = "year",
    period_value: int | None = None,
) -> dict:
    with get_db() as conn:
        # 网点清册、截止日及业绩数据在同一只读快照中取数。
        conn.execute("BEGIN")
        reference, batch = read_reference(conn)
        if not reference:
            raise ValueError("尚未导入证保网点参考表")
        source_cutoff = _performance_cutoff(conn, year)
        if source_cutoff is None:
            if year is None:
                raise ValueError("当前业绩库没有可用业务日期")
            raise ValueError(f"当前业绩库没有{year}年业务数据")
        coverage_start = _date(conn.execute('SELECT MIN("年月日") FROM performance').fetchone()[0])
        performance = _performance_rows(conn)

    year = year or source_cutoff.year
    if as_of and as_of.year != year:
        raise ValueError("统计截止日必须属于所选年份")
    cutoff = min(as_of, source_cutoff) if as_of else source_cutoff
    period_start, period_end, period_label = _period_window(year, cutoff, period_type, period_value)
    previous_period_start = date(year - 1, period_start.month, period_start.day)
    previous_cutoff = _previous_cutoff(period_end)

    current_rows = [entry for entry in performance if period_start <= entry[0] <= period_end]
    current = _aggregate(current_rows)
    previous = _aggregate([entry for entry in performance if previous_period_start <= entry[0] <= previous_cutoff])
    monthly = _monthly_metrics(current_rows, period_start, period_end)
    active_month_counts = _active_month_counts(monthly)
    last_branch_business_date = max((day for day, _ in current_rows), default=None)

    regular = [row for row in reference if row["include_in_regular_count"] == 1]
    referral = [row for row in reference if row["branch_type"] == "转介绍网点"]
    regular_names = {row["branch_name"] for row in regular}
    referral_names = {row["branch_name"] for row in referral} | {row["parent_name"] for row in referral if row["parent_name"]}
    empty = _empty_metrics()
    branch_rows = [
        _branch_row(
            row,
            current["branches"].get(row["branch_name"], empty),
            previous["branches"].get(row["branch_name"], empty),
            active_month_counts.get(row["branch_name"], 0),
        )
        for row in regular
    ]
    branch_rows.sort(key=lambda row: (row["premiumWan"], row["policies"]), reverse=True)
    referral_rows = [
        {
            "referenceId": row["reference_id"], "branch": row["branch_name"], "parent": row["parent_name"],
            "province": row["province"], "city": row["city"], "project": row["project"],
            "subproject": row["subproject"], "locality": row["locality"],
        }
        for row in referral
    ]

    current_branches = current["branches"]
    matched_names = regular_names | referral_names
    matched_regular = sum(metrics["premium"] for name, metrics in current_branches.items() if name in regular_names)
    matched = sum(metrics["premium"] for name, metrics in current_branches.items() if name in matched_names)
    referral_metrics = [metrics for name, metrics in current_branches.items() if name in referral_names]
    referral_premium = sum(metrics["premium"] for metrics in referral_metrics)
    referral_overlap = sum(metrics["premium"] for name, metrics in current_branches.items() if name in regular_names & referral_names)
    unmatched = [
        {
            "branch": name or "（网点缺失）", "premiumWan": _wan(metrics["premium"]),
            "policies": metrics["policies"], "orgs": sorted(metrics["orgs"]),
        }
        for name, metrics in current_branches.items()
        if name not in matched_names and (metrics["premium"] or metrics["policies"] or metrics["unknown_policy_rows"])
    ]
    unmatched.sort(key=lambda row: abs(row["premiumWan"]), reverse=True)

    tiers = []
    for tier, label in CAPACITY_TIERS:
        names = [row["branch"] for row in branch_rows if row["tier"] == tier]
        premium = sum(current_branches.get(name, empty)["premium"] for name in names)
        tiers.append({
            "tierId": tier, "label": label, "shortLabel": label, "count": len(names),
            "countRate": _ratio(len(names), len(regular)), "premiumWan": _wan(premium),
            "premiumShare": _ratio(premium, matched_regular) if matched_regular > 0 else None,
        })
    pareto = _concentration(branch_rows, current)
    brokers = [{"broker": row["label"], **row} for row in _group_metrics(branch_rows, current, "parent")]
    matrix_window, quadrant_points = _matrix(period_type, period_end, coverage_start, performance, branch_rows)
    monthly_trend = [
        {
            "month": month.strftime("%Y-%m"), "totalWan": _wan(metrics["premium"]),
            "regularWan": _wan(metrics["regular_premium"]), "largeWan": _wan(metrics["large_premium"]),
            "netNegativeWan": _wan(metrics["negative_premium"]),
            "unclassifiedPositiveWan": _wan(metrics["unknown_policy_premium"]),
            "largePolicies": metrics["large_policies"], "policies": metrics["policies"],
            "activeBranches": sum(bool(item["policies"]) for name, item in metrics["branches"].items() if name in regular_names),
            "sellers": len(metrics["sellers"]),
        }
        for month, metrics in monthly
    ]

    dormant_alerts = [row for row in branch_rows if row["status"] == "待唤醒"]
    dormant_alerts.sort(key=lambda row: row["previousPremiumWan"], reverse=True)
    large_reliance_alerts = [
        row for row in branch_rows
        if current_branches.get(row["branch"], empty)["premium"] >= 50_000_000 and (row["largeShare"] or 0) >= 0.7
    ]
    localities = {row["label"]: row for row in _group_metrics(branch_rows, current, "locality")}
    locality_comparison = {
        key: {
            "stock": locality.get("stock", 0), "active": locality.get("active", 0),
            "activityRate": locality.get("activityRate"), "premiumWan": locality.get("premiumWan", 0),
            "avgBranchPremiumWan": locality.get("averageBranchPremiumWan"),
        }
        for key, name in (("local", "本地"), ("remote", "异地"))
        for locality in (localities.get(name, {}),)
    }

    total_premium = current["premium"]
    active_regular = sum(bool(row["policies"]) for row in branch_rows)
    positive_premium = total_premium - current["negative_premium"]
    matched_positive = sum(
        metrics["premium"] - metrics["negative_premium"]
        for name, metrics in current_branches.items() if name in matched_names
    )
    regular_sellers = set().union(*(metrics["sellers"] for name, metrics in current_branches.items() if name in regular_names))
    structure = _structure(current)
    large_share = structure["largeShare"]
    return {
        "meta": {
            "year": year, "periodType": period_type, "periodValue": period_value if period_type != "year" else None,
            "periodLabel": period_label, "periodStart": period_start.isoformat(), "asOf": period_end.isoformat(),
            "previousPeriodStart": previous_period_start.isoformat(), "previousAsOf": previous_cutoff.isoformat(),
            "performanceCutoff": source_cutoff.isoformat(),
            "lastBranchBusinessDate": last_branch_business_date.isoformat() if last_branch_business_date else None,
            "referenceBatch": batch, "unit": "万元", "matrixWindow": matrix_window,
        },
        "summary": {
            **structure,
            "premiumWan": _wan(total_premium), "previousPremiumWan": _wan(previous["premium"]),
            "premiumChange": _ratio(total_premium, previous["premium"]) if previous["premium"] > 0 else None,
            "policies": current["policies"],
            "averageCaseWan": _wan(total_premium / current["policies"]) if current["policies"] else None,
            "externalSellers": len(current["sellers"]),
            "regularStock": len(regular), "activeRegular": active_regular,
            "inactiveRegular": len(regular) - active_regular,
            "regularActivityRate": _ratio(active_regular, len(regular)),
            "continuedRegular": sum(row["status"] == "持续经营" for row in branch_rows),
            "matchedRegularPremiumWan": _wan(matched_regular),
            "referralStockExcluded": len(referral), "referralPremiumWan": _wan(referral_premium),
            "referralOverlapPremiumWan": _wan(referral_overlap),
            "referralPremiumShare": _ratio(referral_premium, total_premium) if total_premium > 0 else None,
            "referralPolicies": sum(metrics["policies"] for metrics in referral_metrics),
            "referralSellers": len(set().union(*(metrics["sellers"] for metrics in referral_metrics))),
            "matchedPremiumRate": _ratio(matched_positive, positive_premium),
            "unmatchedPremiumWan": _wan(total_premium - matched),
            "regularPlatformWan": structure["regularPremiumWan"],
            "top5RegularShare": pareto["top5Share"], "top10RegularShare": pareto["top10Share"],
            "top20RegularShare": pareto["top20Share"], "pareto20PercentShare": pareto["pareto20PercentShare"],
            "averageStaffProductivityWan": _wan(total_premium / len(current["sellers"])) if current["sellers"] else None,
            "averageBranchSellers": round(len(regular_sellers) / active_regular, 2) if active_regular else None,
        },
        "tiers": tiers, "pareto": pareto, "brokers": brokers, "quadrant": quadrant_points, "monthlyTrend": monthly_trend,
        "insights": {
            "platformDiagnosis": {"level": "warning" if large_share is not None and large_share >= 0.5 else "normal"},
            "dormantAlerts": dormant_alerts,
            "largeRelianceAlerts": large_reliance_alerts,
            "localityComparison": locality_comparison,
        },
        "levels": _group_metrics(branch_rows, current, "grade"),
        "projects": _group_metrics(branch_rows, current, "project"),
        "regularBranches": branch_rows,
        "referralBranches": referral_rows,
        "quality": {
            "referenceRows": len(reference), "regularRows": len(regular), "referralRows": len(referral),
            "unmatchedBranches": unmatched, "missingPolicyRows": current["unknown_policy_rows"],
            "definitions": {
                "regularCount": "按当前导入的常规网点名录计算网点数和活动率，历史期间使用同一批次名录。",
                "referralCount": "转介绍子网点单列，常规网点活动率按常规名录计算。",
                "activity": "统计期内至少有1张净期交大于0且有投保单号的保单。出单月逐月判定，出单天数取统计期内净正保单的日净额为正的日期。同一网点在本期和上年同期均出单计入持续出单网点。",
                "policyCount": "在各自统计窗口内按投保单号合并后计件，月度件数不跨月相加。无单号明细保留保费，缺号正额单列，件数及以件数识别的指标按可识别保单计算。",
                "referralPerformance": "广发等转介绍归属主体汇总额可同时包含于常规网点匹配额，匹配合计只计一次。转介绍子网点业绩按底表可识别归属列示。",
                "dataCutoff": "数据截止日取业绩基表全业务覆盖日。证保最后一笔业务明细日期单列。",
                "regularPlatform": "有单号且净期交大于0、低于100万元的保单净额。常规期交、超大单、无单号正额和净负冲正合计为总净期交。",
                "largePolicy": "单张保单净期交达到100万元计入超大单。占比的分母为有单号的正净保费。",
                "paymentTerm": "10年及以上交期占比的分母为有单号、净期交大于0且缴费年限已知的保单保费。缺失或冲突的年限计入未知，已知交期覆盖率按有单号的正净保费计算。",
                "paretoConcentration": "将净期交为正的常规网点保费降序排列，分母为这些网点净期交合计。前20%网点数按常规网点名录向上取整。",
                "capacityTiers": "按所选期间净期交的金额区间分档。矩阵按截至所选时点最近三个完整自然月展示，分界用于观察。",
                "matching": "网点名称按清册精确匹配，匹配率以正净期交计算。太平机构按保单明细归属展示，未出单预警可按上年同期归属筛选。",
            },
        },
    }
