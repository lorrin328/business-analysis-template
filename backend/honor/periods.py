"""Honor result-period labels and readiness boundaries."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any


CALLBACK_OBSERVATION_DAYS = 45


def honor_month_end(year: int, month: int) -> date:
    """Return the natural month end for an honor calculation period."""
    last_day = calendar.monthrange(int(year), int(month))[1]
    return date(int(year), int(month), last_day)


def honor_final_ready_on(year: int, month: int) -> date:
    """Return the first date when the whole month has completed callback observation."""
    return honor_month_end(year, month) + timedelta(days=CALLBACK_OBSERVATION_DAYS)


def honor_result_meta(
    year: int,
    month: int,
    source_cutoff: str | None,
    *,
    today: date | None = None,
    created_at: str | date | datetime | None = None,
) -> dict[str, Any]:
    """Classify a stored batch without changing the existing batch schema."""
    year = int(year)
    month = int(month)
    month_end = honor_month_end(year, month)
    final_ready_on = honor_final_ready_on(year, month)
    current_date = today or date.today()
    cutoff = _parse_cutoff(source_cutoff)
    created_date = _parse_date(created_at)
    final_confirmed = False

    if cutoff is None:
        result_type = "final"
        result_label = f"{month}月最终结果"
        final_confirmed = current_date >= final_ready_on and (created_date is None or created_date >= final_ready_on)
        if final_confirmed:
            result_note = f"已按完整月份计算，并完成{CALLBACK_OBSERVATION_DAYS}天回销观察。"
        else:
            result_note = (
                f"该历史批次标记为最终结果；按现行口径应在{final_ready_on.month}月"
                f"{final_ready_on.day}日后生成，请核对回销数据是否完整。"
            )
    elif cutoff < month_end:
        result_type = "process"
        result_label = f"截至{cutoff.month}月{cutoff.day}日（过程）"
        result_note = "月内过程数据，会随新单、入账和回销状态变化。"
    elif cutoff == month_end:
        result_type = "month_end"
        result_label = f"{month}月{cutoff.day}日（月末快照）"
        result_note = (
            f"已覆盖整月业绩，仍需观察回销；最终结果最早可在"
            f"{final_ready_on.month}月{final_ready_on.day}日生成。"
        )
    else:
        result_type = "observation"
        result_label = f"回销观察更新至{cutoff.month}月{cutoff.day}日"
        result_note = (
            f"整月业绩的回销状态已更新至{cutoff.isoformat()}；最终结果最早可在"
            f"{final_ready_on.month}月{final_ready_on.day}日生成。"
        )

    return {
        "resultType": result_type,
        "resultLabel": result_label,
        "resultNote": result_note,
        "monthEnd": month_end.isoformat(),
        "finalReadyOn": final_ready_on.isoformat(),
        "canCreateMonthEndSnapshot": current_date >= month_end,
        "canCreateFinal": current_date >= final_ready_on,
        "finalConfirmed": final_confirmed,
    }


def _parse_cutoff(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_date(value: str | date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None
