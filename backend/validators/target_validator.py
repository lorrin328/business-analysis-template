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
        return float(value) >= 0
    except (TypeError, ValueError):
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


def validate_target_payload(payload: dict) -> ValidationResult:
    result = ValidationResult()
    if not isinstance(payload, dict):
        result.add_error("目标数据必须为 JSON 对象")
        return result
    categories = payload.get("categories")
    if not isinstance(categories, dict) or not categories:
        result.add_error("目标数据 categories 必须为非空对象")
    else:
        missing_categories = sorted(REQUIRED_TARGET_CATEGORIES - set(categories))
        if missing_categories:
            result.add_error(f"目标数据缺少指标分类：{', '.join(missing_categories)}")
        for category_key in sorted(REQUIRED_TARGET_CATEGORIES & set(categories)):
            category = categories.get(category_key)
            metrics = category.get("metrics") if isinstance(category, dict) else None
            if not isinstance(metrics, dict):
                result.add_error(f"{category_key} 缺少 metrics")
                continue
            missing_lines = sorted(REQUIRED_TARGET_BUSINESS_LINES - set(metrics))
            if missing_lines:
                result.add_error(f"{category_key} 缺少业务目标：{', '.join(missing_lines)}")
            for business_line in sorted(REQUIRED_TARGET_BUSINESS_LINES & set(metrics)):
                _validate_metric(result, f"{category_key}/{business_line}", metrics[business_line])

    org_targets = payload.get("orgTargets")
    if org_targets is not None and not isinstance(org_targets, dict):
        result.add_error("orgTargets 必须为对象")
    year = payload.get("year")
    if year is not None:
        try:
            parsed_year = int(year)
            if isinstance(year, bool) or float(year) != parsed_year:
                raise ValueError
        except (TypeError, ValueError):
            result.add_error("目标年份必须为整数")
    return result
