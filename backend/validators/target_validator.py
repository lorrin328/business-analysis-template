import json
import math

from validators.data_validator import ValidationResult


REQUIRED_TARGET_CATEGORIES = {
    "qjPremium",
    "value",
    "shangbao",
    "baozhang",
    "tenYear",
}
REQUIRED_TARGET_BUSINESS_LINES = {
    "整体",
    "经代",
    "转型业务",
    "OTO",
    "证保",
    "蚁桥",
}


def _valid_nonnegative_number(value) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
        return math.isfinite(number) and number >= 0
    except (TypeError, ValueError, OverflowError):
        return False


def _validate_metric(result: ValidationResult, label: str, metric: object) -> None:
    if not isinstance(metric, dict):
        result.add_error(f"{label} 目标必须为对象")
        return
    if not _valid_nonnegative_number(metric.get("year")):
        result.add_error(f"{label} 年度目标必须为非负数")
    for period, expected_length, period_label in (("quarter", 4, "季度"), ("month", 12, "月度")):
        values = metric.get(period)
        if not isinstance(values, list) or len(values) != expected_length:
            result.add_error(f"{label} {period_label}目标必须包含 {expected_length} 个值")
            continue
        if any(not _valid_nonnegative_number(value) for value in values):
            result.add_error(f"{label} {period_label}目标必须全部为非负数")


def validate_target_payload(payload: dict, *, require_complete: bool = True) -> ValidationResult:
    result = ValidationResult()
    if not isinstance(payload, dict):
        result.add_error("目标数据必须为 JSON 对象")
        return result
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        result.add_error("目标数据不能包含非有限数值或非法 JSON 值")
    categories = payload.get("categories")
    if not isinstance(categories, dict) or not categories:
        result.add_error("目标数据 categories 必须为非空对象")
    else:
        missing_categories = sorted(REQUIRED_TARGET_CATEGORIES - set(categories))
        if require_complete and missing_categories:
            result.add_error(f"目标数据缺少指标分类：{', '.join(missing_categories)}")
        for category_key in categories:
            category = categories.get(category_key)
            metrics = category.get("metrics") if isinstance(category, dict) else None
            if not isinstance(metrics, dict):
                result.add_error(f"{category_key} 缺少 metrics")
                continue
            missing_lines = sorted(REQUIRED_TARGET_BUSINESS_LINES - set(metrics))
            if require_complete and category_key in REQUIRED_TARGET_CATEGORIES and missing_lines:
                result.add_error(f"{category_key} 缺少业务目标：{', '.join(missing_lines)}")
            for business_line in metrics:
                _validate_metric(result, f"{category_key}/{business_line}", metrics[business_line])

    org_targets = payload.get("orgTargets")
    if org_targets is not None and not isinstance(org_targets, dict):
        result.add_error("orgTargets 必须为对象")
    elif isinstance(org_targets, dict):
        for org_line, metrics in org_targets.items():
            if not isinstance(metrics, dict):
                result.add_error(f"orgTargets/{org_line} 必须为指标对象")
                continue
            for metric_code, metric in metrics.items():
                _validate_metric(result, f"orgTargets/{org_line}/{metric_code}", metric)
    year = payload.get("year")
    if year is not None:
        try:
            parsed_year = int(year)
            if isinstance(year, bool) or float(year) != parsed_year:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            result.add_error("目标年份必须为整数")
    return result
