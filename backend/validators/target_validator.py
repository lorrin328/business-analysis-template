from validators.data_validator import ValidationResult


def validate_target_payload(payload: dict) -> ValidationResult:
    result = ValidationResult()
    if not isinstance(payload, dict):
        result.add_error("目标数据必须为 JSON 对象")
        return result
    if "categories" not in payload:
        result.add_error("目标数据缺少 categories")
    year = payload.get("year")
    if year is not None:
        try:
            int(year)
        except (TypeError, ValueError):
            result.add_error("目标年份必须为整数")
    return result
