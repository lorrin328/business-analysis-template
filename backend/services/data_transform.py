import math
from datetime import datetime
from typing import Any

from config.business_lines import normalize_business_line
from config.orgs import normalize_org


FIELD_MAPPINGS = {
    "performance": {
        "year": ["年", "统计年"],
        "month": ["年月", "月", "月份"],
        "business_line": ["业务模式", "业务模式名称", "渠道"],
        "qj_premium": ["期交保费"],
        "gm_premium": ["规模保费", "承保年化规保", "年化规保"],
        "zs_premium": ["折算保费", "标准保费"],
        "org": ["机构", "分公司", "二级机构"],
        "date": ["日期", "时间", "入账时间"],
    }
}


def normalize_month(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.month
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).month
        except ValueError:
            pass
    try:
        number = int(float(text))
    except ValueError:
        return None
    if 100000 <= number <= 99999999:
        month = int(str(number)[4:6])
    elif 1000 <= number <= 999999:
        month = number % 100
    else:
        month = number
    return month if 1 <= month <= 12 else None


def normalize_day(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.day
    try:
        number = int(float(str(value).strip()))
    except ValueError:
        return None
    return number if 1 <= number <= 31 else None


def normalize_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def standardize_record(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if isinstance(value, str) and value.strip() == "":
            value = None
        out[key] = value
    if "month" in out:
        out["month"] = normalize_month(out.get("month"))
    if "business_line" in out:
        out["business_line"] = normalize_business_line(out.get("business_line"))
    if "org" in out:
        out["org"] = normalize_org(out.get("org"))
    return out
