"""Team structure and productivity analysis based on raw person-month data."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from db.connection import get_db
from db.schema import init_db


BUSINESS_LINE_MAP = {
    "证券": "证保",
    "证保": "证保",
    "网服": "蚁桥",
    "蚁桥": "蚁桥",
    "OTO": "OTO",
}

PRODUCTIVITY_BANDS = [
    ("0及以下", None, 0),
    ("0-0.5万", 0, 0.5),
    ("0.5-1万", 0.5, 1),
    ("1-3万", 1, 3),
    ("3-5万", 3, 5),
    ("5-10万", 5, 10),
    ("10万以上", 10, None),
]


def _to_int(value: Any, default: int | None = 0) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return default


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _clean_staff_id(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except (TypeError, ValueError):
        pass
    return text


def _normalize_line(value: Any) -> str:
    text = _clean_text(value)
    return BUSINESS_LINE_MAP.get(text, text)


def _compact_period(value: Any) -> str:
    text = _clean_text(value)
    for token in ("-", "/", ".", "年", "月", "日", " "):
        text = text.replace(token, "")
    return text


def _performance_year_month(row: dict[str, Any]) -> tuple[int | None, int | None]:
    year = _to_int(row.get("年"), None)
    month = None
    for key in ("年月日", "年月"):
        compact = _compact_period(row.get(key))
        if len(compact) >= 6 and compact[:6].isdigit():
            if year is None:
                year = int(compact[:4])
            month = int(compact[4:6])
            break
    return year, month


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator * 100


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    weight = pos - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _row_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _is_subtotal(value: Any) -> bool:
    return _clean_text(value) == "小计"


def _band_label(value: float) -> str:
    if value <= 0:
        return PRODUCTIVITY_BANDS[0][0]
    for label, low, high in PRODUCTIVITY_BANDS[1:]:
        if low is not None and value <= low:
            continue
        if high is None or value <= high:
            return label
    return PRODUCTIVITY_BANDS[-1][0]


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


def _load_performance(conn, year: int, business_lines: set[str] | None, orgs: set[str] | None):
    columns = _available_columns(conn, "performance")
    if not columns:
        return {}
    rows = conn.execute('SELECT * FROM performance').fetchall()
    grouped: dict[tuple[int, int, str], dict[str, Any]] = defaultdict(
        lambda: {"qj_premium": 0.0, "policy_numbers": set()}
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
        grouped[key]["qj_premium"] += _to_float(_row_value(row, ("期交保费",))) / 10000.0
        policy_no = _clean_text(_row_value(row, ("投保单号", "保单号")))
        if policy_no:
            grouped[key]["policy_numbers"].add(policy_no)
    return {
        key: {
            "qj_premium": value["qj_premium"],
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
    rows = conn.execute(
        'SELECT * FROM hr_data WHERE CAST("统计年" AS INTEGER) = ? AND CAST("统计月" AS INTEGER) = ?',
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
        if start_headcount <= 0 and end_headcount <= 0:
            continue
        perf = perf_map.get((year, month, staff_id), {"qj_premium": 0.0, "policy_count": 0})
        qj_premium = float(perf["qj_premium"])
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
                "policyCount": policy_count,
                "active": qj_premium > 0,
            }
        )
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
    return {
        "label": label,
        "sampleCount": sample_count,
        "activeCount": active_count,
        "zeroCount": zero_count,
        "zeroRate": _round(_ratio(zero_count, sample_count), 1),
        "p25": _round(_percentile(values, 0.25), 2),
        "p50": _round(_percentile(values, 0.50), 2),
        "p75": _round(_percentile(values, 0.75), 2),
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


def get_team_enhanced_analysis(
    year: int,
    month: int | None = None,
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

    with get_db() as conn:
        if "hr_data" not in {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }:
            return {
                "year": year,
                "month": month,
                "summary": _percentile_summary("整体", []),
                "tenureStructure": [],
                "rankStructure": [],
                "productivityBands": [],
                "percentiles": [],
                "trend": [],
                "filters": {"businessLines": sorted(line_filter), "orgs": sorted(org_filter), "scope": scope},
            }
        selected_month = month or _latest_hr_month(conn, year)
        if not selected_month:
            return {
                "year": year,
                "month": None,
                "summary": _percentile_summary("整体", []),
                "tenureStructure": [],
                "rankStructure": [],
                "productivityBands": [],
                "percentiles": [],
                "trend": [],
                "filters": {"businessLines": sorted(line_filter), "orgs": sorted(org_filter), "scope": scope},
            }
        perf_map = _load_performance(conn, year, line_filter or None, org_filter or None)
        sample = _sample_staff(conn, year, selected_month, perf_map, line_filter or None, org_filter or None, scope)
        return {
            "year": year,
            "month": selected_month,
            "summary": _percentile_summary("整体", sample),
            "tenureStructure": _group_structure(sample, "tenure"),
            "rankStructure": _group_structure(sample, "rank"),
            "productivityBands": _productivity_bands(sample),
            "percentiles": _percentiles_by_line(sample),
            "trend": _trend(conn, year, perf_map, line_filter or None, org_filter or None, scope),
            "filters": {
                "businessLines": sorted(line_filter),
                "orgs": sorted(org_filter),
                "scope": scope,
            },
        }
