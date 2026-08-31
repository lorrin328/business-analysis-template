"""Consecutive calendar days without positive new regular-premium issuance.

This query uses independent daily activity flags, never net premiums. Historical
lookback is intentionally independent of the dashboard range start. Missing
source months and ambiguous source rows must not become invented zero days.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

from config.business_lines import TRANSFORM_CHANNELS
from config.orgs import ORG_LIST


def _today() -> date:
    return datetime.now(timezone(timedelta(hours=8))).date()


def _exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _unknown(reason, status="unknown"):
    return dict(days=None, status=status, lastPositiveDate=None, startDate=None, reason=reason)


def _month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def _coverage_start(rows, cutoff):
    """Only bridge consecutive represented source months, not absent months."""
    months = {(r["year"], r["month"]) for r in rows}
    year, month = cutoff.year, cutoff.month
    if (year, month) not in months:
        return None
    while True:
        previous = (year - 1, 12) if month == 1 else (year, month - 1)
        if previous not in months:
            break
        year, month = previous
    dates = [r["date"] for r in rows if (r["year"], r["month"]) == (year, month) and r["date"]]
    # Do not claim the part before the earliest actual date is complete.
    return min(dates) if dates else date(year, month, 1)


def _result(rows, cutoff, coverage_start, *, unobserved=False):
    positives = [r["date"] for r in rows if r["date"] and r["date"] <= cutoff and r["has_positive_qj"]]
    last = max(positives) if positives else None
    if last == cutoff:
        return dict(days=0, status="ok", lastPositiveDate=last.isoformat(), startDate=None, reason="当日有新增承保期交保费；不与犹退轧差")
    if unobserved:
        result = _unknown("存在目标或人力记录但没有可追溯业绩，开展起日及日级覆盖待确认")
        result["lastPositiveDate"] = last.isoformat() if last else None
        return result
    if not rows or coverage_start is None:
        return _unknown("缺少可追溯的日级业绩或完整连续月份")
    observed = [r["date"] for r in rows if r["date"] and r["date"] <= cutoff]
    if not observed:
        return _unknown("仅有月份或无效业绩日期，无法计算自然日连续天数")
    start = max(coverage_start, min(observed))
    if last and last >= coverage_start:
        start = last + timedelta(days=1)
    for row in rows:
        # A day=0 sentinel can be anywhere in its source month. Its latest
        # possible date blocks a streak unless a later confirmed sale resets it.
        uncertain_date = row["date"] or min(_month_end(row["year"], row["month"]), cutoff)
        if row["uncertain"] and start <= uncertain_date <= cutoff:
            result = _unknown("连续区间内有无效日期、缺失期交保费或正期交与承保件数不一致的记录")
            result["lastPositiveDate"] = last.isoformat() if last else None
            return result
    exact = last is not None and last >= coverage_start
    return dict(
        days=(cutoff - start).days + 1,
        status="ok" if exact else "lower_bound",
        lastPositiveDate=last.isoformat() if last else None,
        startDate=start.isoformat(),
        reason="按自然日连续，跨月不清零" if exact else "历史或开展起日不完整，仅能确认从观察起点起至少连续挂零这些天",
    )


def get_org_zero_streak(conn, year: int, selected_date: str | None, *, today: date | None = None):
    year = int(year)
    channels = list(TRANSFORM_CHANNELS)
    base = dict(basis="qj_premium", dateBasis="business_date", unit="天")
    warning = "按期交保费正向承保及业绩归属日判断，犹退不抵消出单；按已导入源表整月替换范围追溯，截止不超过全部转型业绩最近日和昨日。未出现项目不推定已开展。"
    def empty(reason):
        snapshot = dict(cutoff=None, warning=reason,
                        projects={f"{o}|{c}": _unknown(reason) for o in ORG_LIST for c in channels},
                        orgs={o: _unknown(reason) for o in ORG_LIST})
        return {**base, "year": snapshot, "month": {}}
    if not _exists(conn, "agg_org_daily_activity"):
        return empty("日级承保汇总尚未生成")
    raw = conn.execute("SELECT year,month,day,org,channel,has_positive_qj,uncertain FROM agg_org_daily_activity WHERE year<=? ORDER BY year,month,day", (year,)).fetchall()
    rows = []
    for values in raw:
        r = dict(zip(("year", "month", "day", "org", "channel", "has_positive_qj", "uncertain"), values))
        if r["org"] not in ORG_LIST or r["channel"] not in channels:
            continue
        r["date"] = date(r["year"], r["month"], r["day"]) if r["day"] else None
        rows.append(r)
    current_dates = [r["date"] for r in rows if r["date"] and r["year"] == year]
    if not current_dates:
        return empty("所选年度缺少有效业绩归属日，不能用月初或承保日代替")
    selected = date.fromisoformat(selected_date) if selected_date else _month_end(year, 12)
    cutoff = min(max(current_dates), selected, (today or _today()) - timedelta(days=1))
    if cutoff.year != year:
        return empty("所选年度没有已结束的可观察业务日")
    # Explicit targets/observed staffing ensure never-selling projects are not
    # hidden. They cannot establish an exact opening date on their own.
    targets = []
    if _exists(conn, "target_values"):
        targets = conn.execute(
            "SELECT DISTINCT org,business_line,period_type,period_value FROM target_values WHERE year=? AND target_value>0 AND org IS NOT NULL", (year,)).fetchall()
    staffing = []
    if _exists(conn, "agg_org_hr_data"):
        staffing = conn.execute("SELECT org,channel,month FROM agg_org_hr_data WHERE year=? AND (start_headcount>0 OR end_headcount>0)", (year,)).fetchall()

    def snapshot(end):
        source = [r for r in rows if (r["year"], r["month"]) <= (end.year, end.month)
                  and (r["date"] is None or r["date"] <= end)]
        start = _coverage_start(source, end)
        by_key = {}
        for r in source:
            by_key.setdefault((r["org"], r["channel"]), []).append(r)
        observed_keys = {(r["org"], r["channel"]) for r in source if r["year"] == year}
        target_keys = {(o, c) for o, c, period, value in targets
                       if period == "year" or (period == "month" and 1 <= value <= end.month)
                       or (period == "quarter" and 1 <= value <= (end.month - 1) // 3 + 1)}
        configured = target_keys | {(r[0], r[1]) for r in staffing if r[2] <= end.month}
        projects, orgs = {}, {}
        for org in ORG_LIST:
            combined = []
            has_unobserved = False
            for channel in channels:
                key = (org, channel)
                history = by_key.get(key, [])
                if key not in observed_keys and key not in configured:
                    result = _unknown("所选年度尚无该项目业绩、目标或人力依据，开展状态待确认", "not_observed")
                else:
                    has_unobserved |= not history
                    result = _result(history, end, start, unobserved=not history)
                    combined.extend(history)
                projects[f"{org}|{channel}"] = result
            # All projects share the same complete monthly source. A project
            # without any history lacks an opening date, but cannot erase the
            # institution's known last sale. Actual uncertain rows remain here.
            orgs[org] = (_result(combined, end, start) if combined else
                         _unknown("机构有目标或人力但没有可追溯业绩") if has_unobserved else
                         _unknown("机构暂无可追溯的已开展项目", "not_observed"))
        return dict(cutoff=end.isoformat(), projects=projects, orgs=orgs, warning=warning)

    return {**base, "year": snapshot(cutoff),
            "month": {str(m): snapshot(min(_month_end(year, m), cutoff)) for m in range(1, cutoff.month + 1)}}
