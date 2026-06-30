"""Team structure and productivity analysis based on raw person-month data."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from db.connection import get_db
from db.schema import init_db
from metrics.business_rules import standard_premium_for_manpower
from services.raw_table_reader import quote_identifier, raw_table_columns, read_raw_table_rows
from services.team_analysis_utils import (
    PRODUCTIVITY_BANDS,
    STANDARD_MANPOWER_THRESHOLDS,
    band_label as _band_label,
    clean_staff_id as _clean_staff_id,
    clean_text as _clean_text,
    normalize_line as _normalize_line,
    performance_year_month as _performance_year_month,
    percentile as _percentile,
    ratio as _ratio,
    round_optional as _round,
    row_value as _row_value,
    threshold_count as _threshold_count,
    to_float as _to_float,
    to_int as _to_int,
    is_subtotal as _is_subtotal,
)


def _available_columns(conn, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
    except Exception:
        return set()


def _latest_hr_month(conn, year: int) -> int | None:
    row = conn.execute(
        'SELECT MAX(CAST("统计月" AS INTEGER)) AS month FROM hr_data WHERE CAST("统计年" AS INTEGER) = ?',
        (year,),
    ).fetchone()
    if not row:
        return None
    return _to_int(row["month"], None)


def _period_months(conn, year: int, period_type: str, period_value: int | None) -> list[int]:
    available = [
        _to_int(row["month"], None)
        for row in conn.execute(
            'SELECT DISTINCT CAST("统计月" AS INTEGER) AS month FROM hr_data '
            'WHERE CAST("统计年" AS INTEGER) = ? ORDER BY month',
            (year,),
        ).fetchall()
    ]
    available = [month for month in available if month]
    if period_type == "year":
        return available
    if period_type == "quarter":
        quarter = period_value or ((_latest_hr_month(conn, year) - 1) // 3 + 1 if _latest_hr_month(conn, year) else 1)
        quarter_months = set(range((quarter - 1) * 3 + 1, quarter * 3 + 1))
        return [month for month in available if month in quarter_months]
    selected_month = period_value or _latest_hr_month(conn, year)
    return [selected_month] if selected_month in available else []


def _load_performance(conn, year: int, business_lines: set[str] | None, orgs: set[str] | None):
    columns = _available_columns(conn, "performance")
    if not columns:
        return {}
    rows = read_raw_table_rows(conn, "performance")
    grouped: dict[tuple[int, int, str], dict[str, Any]] = defaultdict(
        lambda: {"qj_premium": 0.0, "standard_premium": 0.0, "policy_numbers": set()}
    )
    for raw in rows:
        row = dict(raw)
        row_year, row_month = _performance_year_month(row)
        if row_year != year or not row_month:
            continue
        staff_id = _clean_staff_id(_row_value(row, ("人员工号", "人员代码", "工号")))
        if not staff_id:
            continue
        line = _normalize_line(_row_value(row, ("业务模式", "业务模式名称")))
        org = _clean_text(_row_value(row, ("销售机构名称", "机构", "机构名称")))
        if business_lines and line not in business_lines:
            continue
        if orgs and org not in orgs:
            continue
        key = (row_year, row_month, staff_id)
        qj_premium = _to_float(_row_value(row, ("期交保费",)))
        source_standard_premium = _to_float(_row_value(row, ("折算保费", "标准保费", "标保")))
        product_code = _row_value(row, ("产品代码",))
        grouped[key]["qj_premium"] += qj_premium / 10000.0
        grouped[key]["standard_premium"] += (
            standard_premium_for_manpower(qj_premium, source_standard_premium, product_code, row_year) / 10000.0
        )
        policy_no = _clean_text(_row_value(row, ("投保单号", "保单号")))
        if policy_no:
            grouped[key]["policy_numbers"].add(policy_no)
    return {
        key: {
            "qj_premium": value["qj_premium"],
            "standard_premium": value["standard_premium"],
            "policy_count": len(value["policy_numbers"]),
        }
        for key, value in grouped.items()
    }


def _sample_staff(
    conn,
    year: int,
    month: int,
    perf_map: dict[tuple[int, int, str], dict[str, Any]],
    business_lines: set[str] | None,
    orgs: set[str] | None,
    scope: str,
) -> list[dict[str, Any]]:
    columns = raw_table_columns(conn, "hr_data")
    if not columns:
        return []
    select_list = ", ".join(quote_identifier(col) for col in columns)
    rows = conn.execute(
        f'SELECT {select_list} FROM hr_data WHERE CAST("统计年" AS INTEGER) = ? AND CAST("统计月" AS INTEGER) = ?',
        (year, month),
    ).fetchall()
    sample = []
    for raw in rows:
        row = dict(raw)
        org = _clean_text(_row_value(row, ("销售机构名称", "机构", "机构名称")))
        line = _normalize_line(_row_value(row, ("业务模式名称", "业务模式")))
        rank = _clean_text(_row_value(row, ("职等", "职级"))) or "未列明"
        tenure = _clean_text(_row_value(row, ("月末司龄区间", "司龄区间", "司龄段"))) or "未列明"
        if any(_is_subtotal(v) for v in (org, line, rank, tenure)):
            continue
        if business_lines and line not in business_lines:
            continue
        if orgs and org not in orgs:
            continue
        staff_id = _clean_staff_id(_row_value(row, ("人员代码", "人员工号", "工号")))
        if not staff_id:
            continue
        start_headcount = _to_int(_row_value(row, ("月初在职人力",)), 0) or 0
        end_headcount = _to_int(_row_value(row, ("月末在职人力",)), 0) or 0
        if end_headcount <= 0:
            continue
        perf = perf_map.get(
            (year, month, staff_id),
            {"qj_premium": 0.0, "standard_premium": 0.0, "policy_count": 0},
        )
        qj_premium = float(perf["qj_premium"])
        standard_premium = float(perf.get("standard_premium") or 0.0)
        policy_count = int(perf["policy_count"])
        if scope == "active" and qj_premium <= 0 and policy_count <= 0:
            continue
        sample.append(
            {
                "staff_id": staff_id,
                "org": org or "未列明",
                "businessLine": line or "未列明",
                "rank": rank,
                "tenure": tenure,
                "startHeadcount": start_headcount,
                "endHeadcount": end_headcount,
                "qjPremium": qj_premium,
                "standardPremium": standard_premium,
                "policyCount": policy_count,
                "active": qj_premium > 0,
            }
        )
    return sample


def _sample_staff_period(
    conn,
    year: int,
    months: list[int],
    perf_map: dict[tuple[int, int, str], dict[str, Any]],
    business_lines: set[str] | None,
    orgs: set[str] | None,
    scope: str,
) -> list[dict[str, Any]]:
    if len(months) == 1:
        return _sample_staff(conn, year, months[0], perf_map, business_lines, orgs, scope)

    aggregated: dict[str, dict[str, Any]] = {}
    for month in months:
        for row in _sample_staff(conn, year, month, perf_map, business_lines, orgs, "all"):
            staff_id = row["staff_id"]
            current = aggregated.get(staff_id)
            if current is None:
                current = {
                    **row,
                    "qjPremium": 0.0,
                    "standardPremium": 0.0,
                    "policyCount": 0,
                    "periodMonths": 0,
                    "_latestMonth": month,
                }
                aggregated[staff_id] = current
            if month >= current["_latestMonth"]:
                for key in ("org", "businessLine", "rank", "tenure", "startHeadcount", "endHeadcount"):
                    current[key] = row[key]
                current["_latestMonth"] = month
            current["qjPremium"] += row["qjPremium"]
            current["standardPremium"] += row["standardPremium"]
            current["policyCount"] += row["policyCount"]
            current["periodMonths"] += 1

    sample = []
    for row in aggregated.values():
        row.pop("_latestMonth", None)
        row["active"] = row["qjPremium"] > 0
        if scope == "active" and row["qjPremium"] <= 0:
            continue
        sample.append(row)
    return sample


def _group_structure(sample: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "premium": 0.0, "active": 0})
    total_count = 0
    for row in sample:
        if row["endHeadcount"] <= 0:
            continue
        label = row[field] or "未列明"
        grouped[label]["count"] += 1
        grouped[label]["premium"] += row["qjPremium"]
        grouped[label]["active"] += 1 if row["active"] else 0
        total_count += 1
    result = []
    for label, value in grouped.items():
        count = value["count"]
        premium = value["premium"]
        result.append(
            {
                "label": label,
                "count": count,
                "share": _round(_ratio(count, total_count), 1),
                "activeCount": value["active"],
                "activityRate": _round(_ratio(value["active"], count), 1),
                "qjPremium": _round(premium, 2),
                "avgPremium": _round(premium / count if count else None, 2),
            }
        )
    return sorted(result, key=lambda item: (-item["count"], item["label"]))


def _productivity_bands(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = {
        label: {"count": 0, "premium": 0.0}
        for label, _, _ in PRODUCTIVITY_BANDS
    }
    total_count = len(sample)
    total_premium = sum(row["qjPremium"] for row in sample)
    for row in sample:
        label = _band_label(row["qjPremium"])
        grouped[label]["count"] += 1
        grouped[label]["premium"] += row["qjPremium"]
    return [
        {
            "label": label,
            "count": value["count"],
            "share": _round(_ratio(value["count"], total_count), 1),
            "qjPremium": _round(value["premium"], 2),
            "premiumShare": _round(_ratio(value["premium"], total_premium), 1),
        }
        for label, value in grouped.items()
    ]


def _percentile_summary(label: str, sample: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["qjPremium"] for row in sample]
    active_count = sum(1 for row in sample if row["qjPremium"] > 0)
    sample_count = len(sample)
    total_premium = sum(values)
    zero_count = sum(1 for row in sample if row["qjPremium"] <= 0)
    p25 = _percentile(values, 0.25)
    p50 = _percentile(values, 0.50)
    p75 = _percentile(values, 0.75)
    return {
        "label": label,
        "sampleCount": sample_count,
        "activeCount": active_count,
        "zeroCount": zero_count,
        "zeroRate": _round(_ratio(zero_count, sample_count), 1),
        "p25": _round(p25, 2),
        "p25Count": _threshold_count(values, p25),
        "p50": _round(p50, 2),
        "p50Count": _threshold_count(values, p50),
        "p75": _round(p75, 2),
        "p75Count": _threshold_count(values, p75),
        "avg": _round(total_premium / sample_count if sample_count else None, 2),
        "qjPremium": _round(total_premium, 2),
    }


def _percentiles_by_line(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sample:
        grouped[row["businessLine"]].append(row)
    result = [_percentile_summary("整体", sample)]
    for line in ("OTO", "证保", "蚁桥"):
        if grouped.get(line):
            result.append(_percentile_summary(line, grouped[line]))
    return result


def _percentiles_by_org(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sample:
        grouped[row["org"]].append(row)
    return sorted(
        (_percentile_summary(org, rows) for org, rows in grouped.items()),
        key=lambda item: (-item["sampleCount"], item["label"]),
    )


def _standard_manpower_record(label: str, rows: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    tracked = [
        row
        for row in rows
        if row.get("endHeadcount", 0) > 0 and row.get("businessLine") in STANDARD_MANPOWER_THRESHOLDS
    ]
    standard_rows = [
        row
        for row in tracked
        if float(row.get("standardPremium") or 0) >= STANDARD_MANPOWER_THRESHOLDS[row["businessLine"]]
    ]
    total_qj = sum(float(row.get("qjPremium") or 0) for row in tracked)
    standard_qj = sum(float(row.get("qjPremium") or 0) for row in standard_rows)
    standard_premium = sum(float(row.get("standardPremium") or 0) for row in standard_rows)
    return {
        "label": label,
        "dimension": dimension,
        "trackedHeadcount": len(tracked),
        "standardCount": len(standard_rows),
        "standardRate": _round(_ratio(len(standard_rows), len(tracked)), 1),
        "qjPremium": _round(total_qj, 2),
        "standardQjPremium": _round(standard_qj, 2),
        "standardPremium": _round(standard_premium, 2),
        "premiumContributionRate": _round(_ratio(standard_qj, total_qj), 1),
    }


def _standard_manpower_rows_by_dimension(
    rows: list[dict[str, Any]],
    field: str,
    dimension: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field) or "未列明"].append(row)
    return sorted(
        (_standard_manpower_record(label, values, dimension) for label, values in grouped.items()),
        key=lambda item: (-item["standardQjPremium"], -item["standardCount"], item["label"]),
    )


def _standard_manpower_analysis(
    conn,
    year: int,
    months: list[int],
    perf_map: dict[tuple[int, int, str], dict[str, Any]],
    business_lines: set[str] | None,
    orgs: set[str] | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    trend_rows: list[dict[str, Any]] = []

    for month in months:
        month_rows = [
            {**row, "month": month}
            for row in _sample_staff(conn, year, month, perf_map, business_lines, orgs, "all")
            if row.get("businessLine") in STANDARD_MANPOWER_THRESHOLDS
        ]
        rows.extend(month_rows)
        trend_rows.append({"month": month, **_standard_manpower_record("整体", month_rows, "month")})
        for line in ("OTO", "证保"):
            line_rows = [row for row in month_rows if row.get("businessLine") == line]
            if line_rows:
                trend_rows.append({"month": month, **_standard_manpower_record(line, line_rows, "month_line")})

    by_line = _standard_manpower_rows_by_dimension(rows, "businessLine", "business_line")
    by_org = _standard_manpower_rows_by_dimension(rows, "org", "org")

    grouped_org_line: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_org_line[f'{row.get("org") or "未列明"} / {row.get("businessLine") or "未列明"}'].append(row)
    by_org_line = sorted(
        (
            _standard_manpower_record(label, values, "org_business_line")
            for label, values in grouped_org_line.items()
        ),
        key=lambda item: (-item["standardQjPremium"], item["label"]),
    )

    return {
        "periodMonths": len(months),
        "summary": [_standard_manpower_record("整体", rows, "overall")],
        "byBusinessLine": by_line,
        "byOrg": by_org,
        "byOrgBusinessLine": by_org_line,
        "trend": trend_rows,
        "definitions": {
            "OTO": "月末在职且当月折算保费/标准保费大于等于2万元",
            "证保": "月末在职且当月折算保费/标准保费大于等于3万元",
            "specialProductRules": "2026年产品代码4281按10年及以上交期处理，标准人力计算时标准保费按期交保费全额计入",
            "premiumContribution": "保费贡献按标准人力对应的期交保费计算",
            "periodAggregation": "季度/年度为所选月份的人月口径汇总，月度为当月人数口径",
        },
    }


def _trend(
    conn,
    year: int,
    perf_map: dict[tuple[int, int, str], dict[str, Any]],
    business_lines: set[str] | None,
    orgs: set[str] | None,
    scope: str,
) -> list[dict[str, Any]]:
    months = [
        _to_int(row["month"], None)
        for row in conn.execute(
            'SELECT DISTINCT CAST("统计月" AS INTEGER) AS month FROM hr_data '
            'WHERE CAST("统计年" AS INTEGER) = ? ORDER BY month',
            (year,),
        ).fetchall()
    ]
    result = []
    for month in [m for m in months if m]:
        sample = _sample_staff(conn, year, month, perf_map, business_lines, orgs, scope)
        summary = _percentile_summary(f"{month}月", sample)
        result.append({"month": month, **summary})
    return result


def _empty_team_analysis_response(
    *,
    year: int,
    month: int | None,
    period_type: str,
    period_value: int | None,
    line_filter: set[str],
    org_filter: set[str],
    scope: str,
) -> dict[str, Any]:
    return {
        "year": year,
        "month": month,
        "periodType": period_type,
        "periodValue": period_value,
        "months": [],
        "summary": _percentile_summary("整体", []),
        "tenureStructure": [],
        "rankStructure": [],
        "productivityBands": [],
        "percentiles": [],
        "orgPercentiles": [],
        "standardManpower": {
            "periodMonths": 0,
            "summary": [],
            "byBusinessLine": [],
            "byOrg": [],
            "byOrgBusinessLine": [],
            "trend": [],
            "definitions": {},
        },
        "trend": [],
        "filters": {"businessLines": sorted(line_filter), "orgs": sorted(org_filter), "scope": scope},
    }


def get_team_enhanced_analysis(
    year: int,
    month: int | None = None,
    period_type: str = "month",
    period_value: int | None = None,
    business_lines: list[str] | None = None,
    orgs: list[str] | None = None,
    scope: str = "all",
) -> dict[str, Any]:
    """Return person-month team structure and productivity analysis.

    The sample is based on hr_data, then left-joined to performance by staff and
    month. This intentionally keeps zero-productivity in-force staff in the
    distribution so median and percentile values are not overstated.
    """
    init_db()
    line_filter = {_normalize_line(item) for item in business_lines or [] if _normalize_line(item)}
    org_filter = {_clean_text(item) for item in orgs or [] if _clean_text(item)}
    if scope not in {"all", "active"}:
        scope = "all"
    if period_type not in {"year", "quarter", "month"}:
        period_type = "month"
    if month is not None and period_value is None:
        period_value = month

    with get_db() as conn:
        if "hr_data" not in {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }:
            return _empty_team_analysis_response(
                year=year,
                month=month,
                period_type=period_type,
                period_value=period_value,
                line_filter=line_filter,
                org_filter=org_filter,
                scope=scope,
            )
        selected_months = _period_months(conn, year, period_type, period_value)
        if not selected_months:
            return _empty_team_analysis_response(
                year=year,
                month=None,
                period_type=period_type,
                period_value=period_value,
                line_filter=line_filter,
                org_filter=org_filter,
                scope=scope,
            )
        perf_map = _load_performance(conn, year, line_filter or None, org_filter or None)
        sample = _sample_staff_period(conn, year, selected_months, perf_map, line_filter or None, org_filter or None, scope)
        standard_manpower = _standard_manpower_analysis(
            conn,
            year,
            selected_months,
            perf_map,
            line_filter or None,
            org_filter or None,
        )
        return {
            "year": year,
            "month": selected_months[-1],
            "periodType": period_type,
            "periodValue": period_value or (selected_months[-1] if period_type == "month" else None),
            "months": selected_months,
            "summary": _percentile_summary("整体", sample),
            "tenureStructure": _group_structure(sample, "tenure"),
            "rankStructure": _group_structure(sample, "rank"),
            "productivityBands": _productivity_bands(sample),
            "percentiles": _percentiles_by_line(sample),
            "orgPercentiles": _percentiles_by_org(sample),
            "standardManpower": standard_manpower,
            "trend": _trend(conn, year, perf_map, line_filter or None, org_filter or None, scope),
            "filters": {
                "businessLines": sorted(line_filter),
                "orgs": sorted(org_filter),
                "scope": scope,
            },
        }
