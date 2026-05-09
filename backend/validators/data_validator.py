from dataclasses import dataclass, field
from typing import Iterable

from config.business_lines import BUSINESS_LINE_BY_NAME
from config.orgs import ORG_LIST
from services.data_transform import normalize_month


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict:
        return {"valid": self.valid, "errors": self.errors, "warnings": self.warnings}


def validate_rows(rows: Iterable[dict], *, required: list[str] | None = None, unique_keys: list[str] | None = None) -> ValidationResult:
    result = ValidationResult()
    required = required or []
    unique_keys = unique_keys or []
    seen = set()

    for idx, row in enumerate(rows, start=1):
        for field_name in required:
            if row.get(field_name) in (None, ""):
                result.add_error(f"第{idx}行缺少必填字段：{field_name}")

        month = row.get("month")
        if month is not None and normalize_month(month) is None:
            result.add_error(f"第{idx}行月份异常：{month}")

        if row.get("channel") and row.get("channel") not in BUSINESS_LINE_BY_NAME:
            result.add_warning(f"第{idx}行业务线未在配置中登记：{row.get('channel')}")

        if row.get("org") and row.get("org") not in ORG_LIST:
            result.add_warning(f"第{idx}行机构未在配置中登记：{row.get('org')}")

        for key, value in row.items():
            if key.endswith("_premium") and value is not None and float(value or 0) < 0:
                result.add_error(f"第{idx}行金额为负：{key}={value}")

        if unique_keys:
            key_tuple = tuple(row.get(k) for k in unique_keys)
            if key_tuple in seen:
                result.add_warning(f"第{idx}行存在重复键：{key_tuple}")
            seen.add(key_tuple)

    return result
