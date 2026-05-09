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


def validate_rows(
    rows: Iterable[dict],
    *,
    required: list[str] | None = None,
    unique_keys: list[str] | None = None,
    mode: str = "aggregate",
) -> ValidationResult:
    result = ValidationResult()
    required = required or []
    unique_keys = unique_keys or []
    enforce_unique = mode == "aggregate"
    seen = set()

    for idx, row in enumerate(rows, start=1):
        for field_name in required:
            if row.get(field_name) in (None, ""):
                result.add_error(f"row {idx} missing required field: {field_name}")

        month = row.get("month")
        if month is not None and normalize_month(month) is None:
            result.add_error(f"row {idx} invalid month: {month}")

        if row.get("channel") and row.get("channel") not in BUSINESS_LINE_BY_NAME:
            result.add_warning(f"row {idx} business line is not configured: {row.get('channel')}")

        if row.get("org") and row.get("org") not in ORG_LIST:
            result.add_warning(f"row {idx} org is not configured: {row.get('org')}")

        for key, value in row.items():
            if not key.endswith("_premium") or value is None:
                continue
            try:
                amount = float(value or 0)
            except (TypeError, ValueError):
                result.add_error(f"row {idx} invalid amount: {key}={value}")
                continue
            if amount < 0:
                result.add_error(f"row {idx} negative amount: {key}={value}")

        if unique_keys and enforce_unique:
            key_tuple = tuple(row.get(k) for k in unique_keys)
            if key_tuple in seen:
                result.add_warning(f"row {idx} duplicate key: {key_tuple}")
            seen.add(key_tuple)

    return result
