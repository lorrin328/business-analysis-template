"""Shared normalization helpers for honor alliance calculations."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def text_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def staff_code(value: Any) -> str:
    text = text_value(value)
    if not text:
        return ""
    if text.isdigit():
        return text.zfill(8)
    return text


def number_value(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def optional_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def ym_from_value(value: Any) -> tuple[int | None, int | None]:
    dt = parse_date(value)
    if dt:
        return dt.year, dt.month
    text = str(value or "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return int(digits[:4]), int(digits[4:6])
    return None, None


def normalize_business_line(value: Any) -> str:
    text = text_value(value)
    if text in {"证券", "证保"}:
        return "证保"
    if text in {"网服", "蚁桥"}:
        return "蚁桥"
    return text


def role_type(rank_name: Any) -> str:
    text = text_value(rank_name)
    if "创新经理" in text:
        return "经理"
    if "创新主管" in text or "主管" in text or "服务经理" in text:
        return "主管"
    return "个人"
