"""Independent daily new-business evidence; never net acceptance against refunds."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
import re

import numpy as np
import pandas as pd

from config.business_lines import TRANSFORM_CHANNELS
from config.orgs import ORG_SCOPE
from etl.columns import _pick_col
from etl.normalize import _normalize_channel


ACTIVITY_SOURCE_COLUMNS = (
    "年", "年月", "月", "月份", "年月日", "入账时间",
    "业务模式", "业务模式名称", "渠道",
    "销售机构名称", "机构", "分公司", "org", "期交保费", "承保件数",
)
_SEPARATED = re.compile(
    r"^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d{1,9})?)?)?$"
)
_MONTH_PREFIX = re.compile(r"^(\d{4})[-/.年](\d{1,2})(?=$|[-/.月\s])")


def _text(value) -> str:
    text = str(value).strip()
    # Excel blank cells can promote YYYYMMDD integers to float, then SQLite TEXT.
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


@lru_cache(maxsize=8192)
def _date_parts(text: str) -> tuple[int, int, int]:
    """Return day=0 for month precision or invalid day, never invent month-start."""
    year = month = day = 0
    valid_time = True
    if re.fullmatch(r"\d{8}", text):
        year, month, day = int(text[:4]), int(text[4:6]), int(text[6:])
    elif match := _SEPARATED.fullmatch(text):
        year, month, day = map(int, match.group(1, 2, 3))
        hour, minute, second = match.group(4, 5, 6)
        valid_time = (hour is None or (int(hour) < 24 and int(minute) < 60 and int(second or 0) < 60))
    elif re.fullmatch(r"\d{6}", text):
        year, month = int(text[:4]), int(text[4:])
    elif match := _MONTH_PREFIX.match(text):
        year, month = map(int, match.group(1, 2))
    if not (1900 <= year <= 2100 and 1 <= month <= 12):
        return 0, 0, 0
    try:
        if not valid_time:
            raise ValueError("invalid time")
        date(year, month, day)
    except ValueError:
        day = 0
    return year, month, day


def _resolve_periods(frame: pd.DataFrame) -> pd.DataFrame:
    # Column priority is global. A blank 年月日 cell must not use 入账时间,
    # and 承保时间/承保日期 are deliberately excluded from this business rule.
    date_col = _pick_col(frame, ["年月日", "入账时间"])
    month_col = _pick_col(frame, ["年月", "月", "月份"])
    year_col = _pick_col(frame, ["年"])
    parts = frame[date_col].map(lambda value: _date_parts(_text(value))) if date_col else [(0, 0, 0)] * len(frame)
    periods = pd.DataFrame(list(parts), columns=["year", "month", "day"], index=frame.index)
    missing = periods["month"].eq(0)
    if missing.any() and month_col:
        month_text = frame.loc[missing, month_col].map(_text)
        month_parts = pd.DataFrame(
            month_text.map(_date_parts).tolist(), columns=["year", "month", "day"], index=month_text.index,
        )
        if year_col:
            short = month_text.str.fullmatch(r"\d{1,2}")
            years = pd.to_numeric(frame.loc[month_text.index, year_col], errors="coerce")
            months = pd.to_numeric(month_text, errors="coerce")
            usable = short & years.between(1900, 2100) & years.mod(1).eq(0) & months.between(1, 12)
            month_parts.loc[usable, "year"] = years[usable].astype(int)
            month_parts.loc[usable, "month"] = months[usable].astype(int)
        periods.loc[missing, ["year", "month"]] = month_parts[["year", "month"]]
    if periods["month"].eq(0).any():
        # This is an import error, not a missing business day; do not expose rows.
        raise ValueError("连续挂零：存在无法识别业绩归属年月的记录，请核对年月日、入账时间及年月字段")
    return periods


def extract_org_activity_periods(frame: pd.DataFrame) -> set[tuple[int, int]]:
    """Covered source months, including records corrected out of supported scope."""
    if frame.empty:
        return set()
    periods = _resolve_periods(frame.reset_index(drop=True))
    return set(map(tuple, periods[["year", "month"]].drop_duplicates().itertuples(index=False, name=None)))


def aggregate_org_daily_activity(df: pd.DataFrame) -> list[dict]:
    """Boolean MAX by institution/project/day; day=0 records month uncertainty."""
    if df.empty:
        return []
    channel_col = _pick_col(df, ["业务模式", "业务模式名称", "渠道"])
    org_col = _pick_col(df, ["销售机构名称", "机构", "分公司", "org"])
    if not channel_col or not org_col:
        raise ValueError("连续挂零：缺少机构或业务模式字段")
    channels = df[channel_col].map(_normalize_channel)
    orgs = df[org_col].fillna("").astype(str).str.strip()
    selected = channels.isin(TRANSFORM_CHANNELS) & orgs.isin(ORG_SCOPE)
    work = df.loc[selected].reset_index(drop=True)
    if work.empty:
        return []
    result = _resolve_periods(work)
    result["org"] = orgs.loc[selected].to_numpy()
    result["channel"] = channels.loc[selected].to_numpy()
    premium = pd.to_numeric(work.get("期交保费", pd.Series(np.nan, index=work.index)), errors="coerce")
    count = pd.to_numeric(work.get("承保件数", pd.Series(np.nan, index=work.index)), errors="coerce")
    finite_premium = np.isfinite(premium)
    accepted = np.isfinite(count) & count.gt(0)
    valid_day = result["day"].gt(0)
    result["has_positive_qj"] = (finite_premium & premium.gt(0) & accepted & valid_day).astype(int)
    result["uncertain"] = (~valid_day | ~finite_premium | (premium.gt(0) & ~accepted)).astype(int)
    return result.groupby(["year", "month", "day", "org", "channel"], as_index=False)[
        ["has_positive_qj", "uncertain"]
    ].max().to_dict("records")
