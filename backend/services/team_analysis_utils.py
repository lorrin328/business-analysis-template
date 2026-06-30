"""Pure helpers for team structure and productivity analysis."""
from __future__ import annotations

from typing import Any


BUSINESS_LINE_MAP = {
    "证券": "证保",
    "证保": "证保",
    "网服": "蚁桥",
    "蚁桥": "蚁桥",
    "OTO": "OTO",
}

STANDARD_MANPOWER_THRESHOLDS = {
    "OTO": 2.0,
    "证保": 3.0,
}

PRODUCTIVITY_BANDS = [
    ("0及以下", None, 0),
    ("0-0.5万", 0, 0.5),
    ("0.5-1万", 0.5, 1),
    ("1-3万", 1, 3),
    ("3-5万", 3, 5),
    ("5-10万", 5, 10),
    ("10万以上", 10, None),
]


def to_int(value: Any, default: int | None = 0) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return default


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def clean_staff_id(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except (TypeError, ValueError):
        pass
    return text


def normalize_line(value: Any) -> str:
    text = clean_text(value)
    return BUSINESS_LINE_MAP.get(text, text)


def compact_period(value: Any) -> str:
    text = clean_text(value)
    for token in ("-", "/", ".", "年", "月", "日", " "):
        text = text.replace(token, "")
    return text


def performance_year_month(row: dict[str, Any]) -> tuple[int | None, int | None]:
    year = to_int(row.get("年"), None)
    month = None
    for key in ("年月日", "年月"):
        compact = compact_period(row.get(key))
        if len(compact) >= 6 and compact[:6].isdigit():
            if year is None:
                year = int(compact[:4])
            month = int(compact[4:6])
            break
    return year, month


def ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator * 100


def round_optional(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    weight = pos - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def threshold_count(values: list[float], threshold: float | None) -> int | None:
    if threshold is None:
        return None
    return sum(1 for value in values if value >= threshold)


def row_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    return None


def is_subtotal(value: Any) -> bool:
    return clean_text(value) == "小计"


def band_label(value: float) -> str:
    if value <= 0:
        return PRODUCTIVITY_BANDS[0][0]
    for label, low, high in PRODUCTIVITY_BANDS[1:]:
        if low is not None and value <= low:
            continue
        if high is None or value <= high:
            return label
    return PRODUCTIVITY_BANDS[-1][0]
