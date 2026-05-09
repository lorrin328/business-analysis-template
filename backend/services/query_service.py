from collections import defaultdict

from config.business_lines import BUSINESS_LINES
from database import get_platform_data
from services.data_transform import normalize_month


def _metric_col(metric: str) -> str:
    return {
        "qj": "qj_premium",
        "gm": "gm_premium",
        "zs": "zs_premium",
    }.get(metric, "qj_premium")


def _daily_contains_jingdai(rows: list[dict], month: int | None = None) -> bool:
    for row in rows:
        row_month = normalize_month(row.get("month"))
        if row.get("channel") == "经代" and (month is None or row_month == month):
            return True
    return False


def build_month_daily_cumulative(platform_data: dict, year: int, month: int, channels: list[str], metric: str = "qj") -> dict:
    col = _metric_col(metric)
    month = int(month)
    daily = defaultdict(float)
    raw_daily = platform_data.get("daily_performance") or []
    jd_daily = platform_data.get("jingdai_daily") or []
    daily_has_jingdai = _daily_contains_jingdai(raw_daily, month)

    for row in raw_daily:
        if normalize_month(row.get("month")) == month and row.get("channel") in channels:
            daily[int(row.get("day") or 1)] += float(row.get(col) or 0)

    if "经代" in channels and not daily_has_jingdai:
        for row in jd_daily:
            if normalize_month(row.get("month")) == month:
                daily[int(row.get("day") or 1)] += float(row.get(col) or 0)

    labels, values = [], []
    running = 0.0
    for day in sorted(daily):
        running += daily[day]
        if running > 0:
            labels.append(f"{month}月{day}日")
            values.append(round(running, 2))

    return {
        "labels": labels,
        "values": values,
        "hasRealDailyData": bool(values),
        "jingdaiDeduped": "经代" in channels and daily_has_jingdai,
        "message": "" if values else "暂无日累计数据",
    }


def get_platform_trend(year: int, month: int | None = None, channels: list[str] | None = None, metric: str = "qj") -> dict:
    data = get_platform_data(year)
    channels = channels or [item["name"] for item in BUSINESS_LINES if item["name"] in ["经代", "OTO", "证保", "蚁桥"]]
    result = {"year": year, "businessLines": channels, "raw": data}
    if month:
        result["daily"] = build_month_daily_cumulative(data, year, month, channels, metric)
    return result
