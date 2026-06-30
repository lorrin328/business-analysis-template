"""Summary builders for honor alliance calculation results."""
from __future__ import annotations

from typing import Any

from .config import SENIOR_PLUS_LEVELS
from .rules import reward_for_level


def build_org_summary(
    batch_id: int,
    year: int,
    month: int,
    summaries: list[dict[str, Any]],
    months: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_month = [row for row in months if row["year"] == year and row["month"] == month]
    current_index = {(row["staff_code"], row["business_line"]): row for row in current_month}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in summaries:
        key = (row.get("org") or "未归属", row.get("business_line") or "")
        item = grouped.setdefault(
            key,
            {
                "batch_id": batch_id,
                "year": year,
                "month": month,
                "org": key[0],
                "business_line": key[1],
                "tracked_headcount": 0,
                "member_count": 0,
                "senior_plus_count": 0,
                "monthly_gain_count": 0,
                "monthly_deduct_count": 0,
                "total_diamond": 0,
                "member_rate": 0,
                "avg_diamond": 0,
                "estimated_reward": 0,
            },
        )
        current = current_index.get((row["staff_code"], row["business_line"]))
        current_employed = bool(current and int(current.get("is_employed_end_month") or 0) > 0)
        item["tracked_headcount"] += 1 if current_employed else 0
        item["member_count"] += 1 if current_employed and row["membership_level"] != "未入会" else 0
        item["senior_plus_count"] += 1 if current_employed and row["membership_level"] in SENIOR_PLUS_LEVELS else 0
        item["total_diamond"] += int(row["diamond_balance"] or 0)
        if current:
            item["monthly_gain_count"] += 1 if int(current["diamond_delta"] or 0) > 0 else 0
            item["monthly_deduct_count"] += 1 if int(current["diamond_delta"] or 0) < 0 else 0
        reward, _ = reward_for_level(row["membership_level"])
        item["estimated_reward"] += reward if current_employed else 0
    for item in grouped.values():
        tracked = int(item["tracked_headcount"] or 0)
        item["member_rate"] = item["member_count"] / tracked if tracked else 0
        item["avg_diamond"] = item["total_diamond"] / tracked if tracked else 0
    return list(grouped.values())


def build_quarter_rewards(
    batch_id: int,
    year: int,
    month: int,
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    quarter = ((month - 1) // 3) + 1
    rows = []
    for row in summaries:
        amount, label = reward_for_level(row["membership_level"])
        rows.append(
            {
                "batch_id": batch_id,
                "year": year,
                "quarter": quarter,
                "org": row.get("org") or "未归属",
                "staff_code": row["staff_code"],
                "staff_name": row.get("staff_name"),
                "membership_level": row["membership_level"],
                "reward_amount": amount,
                "reward_label": label,
                "is_estimated": 1,
            }
        )
    return rows
