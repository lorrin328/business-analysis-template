import math
from datetime import datetime
from typing import Any

from config.business_lines import normalize_business_line
from config.orgs import normalize_org


FIELD_MAPPINGS = {
    "performance": {
        "year": ["年", "统计年"],
        "month": ["年月", "月", "月份", "统计月"],
        "business_line": ["业务模式", "业务模式名称", "渠道"],
        "channel": ["业务模式", "业务模式名称", "渠道"],
        "qj_premium": ["期交保费"],
        "gm_premium": ["规模保费", "承保年化规保", "年化规保", "规保"],
        "zs_premium": ["折算保费", "标准保费"],
        "org": ["机构", "分公司", "二级机构", "销售机构名称"],
        "date": ["日期", "时间", "入账时间", "承保日期", "投保日期"],
    },
    "jingdai": {
        "year": ["年", "统计年"],
        "month": ["年月", "时间", "日期", "入账时间"],
        "day": ["日", "日期", "时间", "入账时间", "生效日期", "出单日期", "承保日期"],
        "qj_premium": ["期交保费"],
        "gm_premium": ["承保年化规保", "年化规保", "规模保费", "规保"],
        "zs_premium": ["折算保费", "标准保费"],
        "pay_years": ["缴费年限"],
    },
    "hr": {
        "year": ["统计年", "年"],
        "month": ["统计月", "统计日期", "年月", "月"],
        "business_line": ["业务模式名称", "业务模式", "渠道"],
        "channel": ["业务模式名称", "业务模式", "渠道"],
        "start_headcount": ["月初在职人力"],
        "end_headcount": ["月末在职人力"],
        "active_headcount": ["活动人力", "出单人力"],
    },
    "value": {
        "year": ["年", "统计年"],
        "month": ["年月", "时间", "日期"],
        "business_line": ["业务模式名称", "业务模式", "渠道"],
        "channel": ["业务模式名称", "业务模式", "渠道"],
        "value_premium": ["价值", "价值保费", "价值贡献"],
        "org": ["机构", "分公司", "二级机构", "销售机构名称"],
    },
    "target": {
        "year": ["年", "目标年份"],
        "period_type": ["周期类型", "期间类型", "period_type"],
        "period_value": ["周期值", "期间值", "period_value"],
        "business_line": ["业务线", "业务模式", "渠道"],
        "metric_code": ["指标编码", "指标", "metric_code"],
        "target_value": ["目标值", "目标", "target_value"],
        "org": ["机构", "分公司", "二级机构"],
    },
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


def map_record_fields(row: dict, dataset: str) -> dict:
    mapping = FIELD_MAPPINGS.get(dataset, {})
    out = {}
    for canonical, aliases in mapping.items():
        for alias in aliases:
            if alias in row:
                out[canonical] = row.get(alias)
                break
    return out


def standardize_record(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if isinstance(value, str) and value.strip() == "":
            value = None
        out[key] = value
    if "month" in out:
        out["month"] = normalize_month(out.get("month"))
    if "day" in out:
        out["day"] = normalize_day(out.get("day"))
    if "business_line" in out:
        out["business_line"] = normalize_business_line(out.get("business_line"))
    if "channel" in out:
        out["channel"] = normalize_business_line(out.get("channel"))
    if "org" in out:
        out["org"] = normalize_org(out.get("org"))
    return out
