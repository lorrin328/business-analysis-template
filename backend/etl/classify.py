"""Payment period classification functions."""
from typing import Dict, List

import pandas as pd

def _classify_payment_period(pay_years_val, term_type_val):
    """将缴费年限 + 长短险映射为交期分类（转型业务）。"""
    term_str = str(term_type_val).strip() if pd.notna(term_type_val) else ''
    if term_str in ('短期', '极短期'):
        return '短期险'
    try:
        y = int(float(pay_years_val))
    except (TypeError, ValueError):
        y = None
    if y is None:
        return None
    if y == 0:
        return '趸交'
    if 1 <= y <= 3:
        return '3年交'
    if 4 <= y <= 9:
        return '5年交'
    if y >= 10:
        return '10年及以上'
    return None


def _classify_jingdai_payment_period(pay_years_val, term_cat_val):
    """将缴费年限 + 当前缴别大类映射为交期分类（经代业务）。"""
    term_cat = str(term_cat_val).strip() if pd.notna(term_cat_val) else ''
    try:
        y = int(float(pay_years_val))
    except (TypeError, ValueError):
        y = None
    if term_cat == '趸交':
        return '趸交'
    if term_cat == '期交' and y is not None:
        if y == 1:
            return '短期险'
        if 2 <= y <= 3:
            return '3年交'
        if 4 <= y <= 9:
            return '5年交'
        if y >= 10:
            return '10年及以上'
    if y is not None:
        if y == 0:
            return '趸交'
        if 1 <= y <= 3:
            return '3年交'
        if 4 <= y <= 9:
            return '5年交'
        if y >= 10:
            return '10年及以上'
    return None

