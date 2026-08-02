"""Compact aggregates used by interactive dashboard queries."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from config.business_lines import TRANSFORM_CHANNELS
from etl.columns import _pick_col
from etl.normalize import _amount_to_wan, _normalize_channel, _period_year_month, _to_number
from metrics.business_rules import TENYEAR_PRODUCT_CODES_BY_YEAR, normalize_product_code


def _clean_text(series: pd.Series, default: str = "") -> pd.Series:
    result = series.fillna("").astype(str).str.strip()
    result = result.mask(result.str.lower().isin({"nan", "none", "null"}), "")
    return result.mask(result == "", default)


def _clean_staff(series: pd.Series) -> pd.Series:
    result = _clean_text(series)
    numeric_mask = result.str.fullmatch(r"[+-]?\d+(?:\.0+)?", na=False)
    if numeric_mask.any():
        numeric = pd.to_numeric(result.where(numeric_mask), errors="coerce").astype("Int64")
        result = result.mask(numeric_mask, numeric.astype(str))
    return result


def aggregate_staff_month_performance(df: pd.DataFrame) -> List[Dict]:
    """Aggregate raw policy rows to the staff-month grain used by team analysis."""
    year_col = _pick_col(df, ["年"])
    month_col = _pick_col(df, ["年月", "月", "月份"])
    staff_col = _pick_col(df, ["人员工号", "人员代码", "工号"])
    channel_col = _pick_col(df, ["业务模式", "业务模式名称", "渠道"])
    org_col = _pick_col(df, ["销售机构名称", "机构", "机构名称"])
    qj_col = _pick_col(df, ["期交保费"])
    standard_col = _pick_col(df, ["折算保费", "标准保费", "标保"])
    product_col = _pick_col(df, ["产品代码"])
    policy_col = _pick_col(df, ["投保单号", "保单号"])
    if not all([month_col, staff_col, channel_col, qj_col]):
        return []

    work = _period_year_month(df, year_col, month_col)
    work["_staff_id"] = _clean_staff(work[staff_col])
    work["_channel"] = work[channel_col].map(_normalize_channel)
    # Keep the raw repository's historical behaviour: without a business-line
    # filter, every policy row belonging to the staff member contributes.  The
    # channel is retained in the aggregate so filtered requests still narrow to
    # OTO/证保/蚁桥 exactly as before.
    work = work[work["_staff_id"] != ""]
    if work.empty:
        return []
    work["_org"] = _clean_text(work[org_col]) if org_col else ""
    work["_qj"] = _to_number(work[qj_col])
    work["_standard"] = _to_number(work[standard_col]) if standard_col else 0.0
    if product_col:
        codes = work[product_col].map(normalize_product_code)
        for rule_year, rule_codes in TENYEAR_PRODUCT_CODES_BY_YEAR.items():
            mask = (work["_year"] == int(rule_year)) & codes.isin(rule_codes)
            work.loc[mask, "_standard"] = work.loc[mask, "_qj"]
    work["_policy"] = _clean_text(work[policy_col]) if policy_col else ""

    grouped = work.groupby(
        ["_year", "_month", "_channel", "_org", "_staff_id"],
        dropna=False,
    )
    rows: list[dict] = []
    for (year, month, channel, org, staff_id), group in grouped:
        policies = group.loc[group["_policy"] != "", "_policy"].nunique()
        rows.append({
            "year": int(year),
            "month": int(month),
            "channel": str(channel),
            "org": str(org),
            "staff_id": str(staff_id),
            "qj_premium": _amount_to_wan(group["_qj"].sum()),
            "standard_premium": _amount_to_wan(group["_standard"].sum()),
            "policy_count": int(policies),
        })
    return rows


def aggregate_transform_product_daily(df: pd.DataFrame) -> List[Dict]:
    year_col = _pick_col(df, ["年"])
    month_col = _pick_col(df, ["年月", "月", "月份"])
    date_col = _pick_col(df, ["年月日", "入账时间", "日期", "出单日期", "投保日期", "承保日期"])
    channel_col = _pick_col(df, ["业务模式", "业务模式名称", "渠道"])
    org_col = _pick_col(df, ["销售机构名称", "机构", "机构名称"])
    category_col = _pick_col(df, ["产品类型"])
    product_col = _pick_col(df, ["产品名称", "产品类型", "产品代码"])
    qj_col = _pick_col(df, ["期交保费"])
    gm_col = _pick_col(df, ["年化规保", "规模保费", "规保"], ["规模", "规保"])
    count_col = _pick_col(df, ["承保件数"])
    if not all([month_col, channel_col, qj_col]):
        return []

    work = _period_year_month(df, year_col, month_col if not date_col else None, date_col)
    work["_channel"] = work[channel_col].map(_normalize_channel)
    work = work[work["_channel"].isin(TRANSFORM_CHANNELS)]
    if work.empty:
        return []
    work["_org"] = _clean_text(work[org_col]) if org_col else ""
    work["_category"] = _clean_text(work[category_col], "未分类") if category_col else "未分类"
    work["_product"] = _clean_text(work[product_col], "未分类") if product_col else work["_category"]
    work["_qj"] = _to_number(work[qj_col])
    work["_gm"] = _to_number(work[gm_col]) if gm_col else 0.0
    work["_count"] = _to_number(work[count_col]) if count_col else 1.0
    return _aggregate_product_rows(work, "转型")


def aggregate_jingdai_product_daily(df: pd.DataFrame) -> List[Dict]:
    year_col = _pick_col(df, ["年"])
    month_col = _pick_col(df, ["年月", "月", "月份", "时间"])
    date_col = _pick_col(df, ["年月日", "入账时间", "日期", "承保日期", "出单日期", "生效日期", "时间"])
    org_col = _pick_col(df, ["经代机构", "机构", "机构名称"])
    product_col = _pick_col(df, ["产品名称", "产品代码"])
    qj_col = _pick_col(df, ["期交保费"])
    gm_col = _pick_col(df, ["承保年化规保", "年化规保", "规模保费"])
    if not all([month_col, product_col, qj_col]):
        return []

    work = _period_year_month(df, year_col, month_col if not date_col else None, date_col)
    if work.empty:
        return []
    work["_channel"] = "经代"
    work["_org"] = _clean_text(work[org_col]) if org_col else ""
    work["_category"] = _clean_text(work[product_col], "未分类")
    work["_product"] = work["_category"]
    work["_qj"] = _to_number(work[qj_col])
    work["_gm"] = _to_number(work[gm_col]) if gm_col else 0.0
    work["_count"] = 1.0
    return _aggregate_product_rows(work, "经代")


def _aggregate_product_rows(work: pd.DataFrame, business_type: str) -> List[Dict]:
    grouped = work.groupby(
        ["_year", "_month", "_day", "_channel", "_org", "_category", "_product"],
        dropna=False,
    )
    rows: list[dict] = []
    for (year, month, day, channel, org, category, product), group in grouped:
        rows.append({
            "year": int(year),
            "month": int(month),
            "day": int(day),
            "business_type": business_type,
            "channel": str(channel),
            "org": str(org),
            "product_category": str(category),
            "product_name": str(product),
            "qj_premium": _amount_to_wan(group["_qj"].sum()),
            "gm_premium": _amount_to_wan(group["_gm"].sum()),
            "count": int(group["_count"].sum()),
        })
    return rows
