"""职拓业务专用聚合。"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from etl.classify import _classify_payment_period
from etl.columns import _pick_col
from etl.normalize import _amount_to_wan, _normalize_channel, _period_year_month, _to_number


def _clean_text(series: pd.Series, default: str = "") -> pd.Series:
    result = series.fillna("").astype(str).str.strip()
    result = result.mask(result.str.lower().isin({"nan", "none", "null"}), "")
    return result.mask(result == "", default)


def _clean_staff(series: pd.Series) -> pd.Series:
    result = _clean_text(series, "人员待确认")
    numeric_mask = result.str.fullmatch(r"[+-]?\d+(?:\.0+)?", na=False)
    if numeric_mask.any():
        numeric = pd.to_numeric(result.where(numeric_mask), errors="coerce").astype("Int64")
        result = result.mask(numeric_mask, numeric.astype(str))
    return result


def _is_zhituo(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    return normalized.isin({"是", "y", "yes", "true", "1", "职拓"})


def aggregate_zhituo_performance(df: pd.DataFrame) -> List[Dict]:
    """聚合“是否职拓=是”的转型业绩，保留页面所需的日、机构、人员、产品和交期维度。"""
    flag_col = _pick_col(df, ["是否职拓", "职拓标识", "是否职域"])
    month_col = _pick_col(df, ["年月", "月", "月份"])
    date_col = _pick_col(df, ["年月日", "入账时间", "日期", "出单日期", "投保日期", "承保日期"])
    year_col = _pick_col(df, ["年"])
    channel_col = _pick_col(df, ["业务模式", "业务模式名称", "渠道"])
    org_col = _pick_col(df, ["销售机构名称", "机构", "机构名称"])
    staff_col = _pick_col(df, ["人员工号", "人员代码", "工号"])
    product_col = _pick_col(df, ["产品名称", "产品代码"])
    product_type_col = _pick_col(df, ["产品类型", "产品设计分类"])
    pay_col = _pick_col(df, ["缴费年限"])
    term_col = _pick_col(df, ["长短险"])
    qj_col = _pick_col(df, ["期交保费"])
    gm_col = _pick_col(df, ["年化规保", "规模保费", "规保"], ["规模", "规保"])
    count_col = _pick_col(df, ["承保件数"])
    if not all([flag_col, month_col, channel_col, qj_col]):
        return []

    work = _period_year_month(df, year_col, month_col if not date_col else None, date_col)
    work = work[_is_zhituo(work[flag_col])]
    if work.empty:
        return []

    work["_channel"] = work[channel_col].map(_normalize_channel)
    work["_org"] = _clean_text(work[org_col], "机构待确认") if org_col else "机构待确认"
    work["_staff_id"] = _clean_staff(work[staff_col]) if staff_col else "人员待确认"
    work["_product"] = _clean_text(work[product_col], "产品待确认") if product_col else "产品待确认"
    work["_product_type"] = (
        _clean_text(work[product_type_col], "产品类型待确认")
        if product_type_col else "产品类型待确认"
    )
    work["_payment_period"] = work.apply(
        lambda row: _classify_payment_period(
            row[pay_col] if pay_col else None,
            row[term_col] if term_col else "",
        ) or "交期待确认",
        axis=1,
    )
    work["_qj"] = _to_number(work[qj_col])
    work["_gm"] = _to_number(work[gm_col]) if gm_col else 0.0
    work["_count"] = _to_number(work[count_col]) if count_col else 1.0

    grouped = work.groupby(
        [
            "_year", "_month", "_day", "_channel", "_org", "_staff_id",
            "_product", "_product_type", "_payment_period",
        ],
        dropna=False,
    )
    rows: list[dict] = []
    for keys, group in grouped:
        year, month, day, channel, org, staff_id, product, product_type, payment_period = keys
        rows.append({
            "year": int(year),
            "month": int(month),
            "day": int(day),
            "channel": str(channel),
            "org": str(org),
            "staff_id": str(staff_id),
            "product_name": str(product),
            "product_type": str(product_type),
            "payment_period": str(payment_period),
            "qj_premium": _amount_to_wan(group["_qj"].sum()),
            "gm_premium": _amount_to_wan(group["_gm"].sum()),
            "policy_count": int(group["_count"].sum()),
        })
    return rows
