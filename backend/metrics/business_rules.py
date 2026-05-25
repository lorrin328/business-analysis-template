"""Shared business classification rules used by ETL and KPI aggregates."""
from __future__ import annotations

import pandas as pd


LONGTERM_TERMS = {
    "长期",
    "长险",
    "长期险",
    "长",
    "一年期以上",
    "一年以上",
    "1年期以上",
}

SHORTTERM_TERMS = {
    "短期",
    "极短期",
    "一年期",
    "一年期以下",
    "一年以下",
    "1年期",
    "1年期以下",
}

LONGTERM_PRODUCT_CODES = {"4281"}


def normalize_product_code(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text[:-2] if text.endswith(".0") else text


def is_shortterm_term(value) -> bool:
    text = str(value).strip() if pd.notna(value) else ""
    return text in SHORTTERM_TERMS


def is_longterm_term(value) -> bool:
    text = str(value).strip() if pd.notna(value) else ""
    return text in LONGTERM_TERMS


def is_longterm_policy(term_value=None, product_code=None, pay_years_value=None) -> bool:
    if is_shortterm_term(term_value):
        return False
    if is_longterm_term(term_value):
        return True
    if normalize_product_code(product_code) in LONGTERM_PRODUCT_CODES:
        return True
    term_text = str(term_value).strip() if pd.notna(term_value) else ""
    if term_text:
        return False
    try:
        return float(pay_years_value) >= 2
    except (TypeError, ValueError):
        return False
