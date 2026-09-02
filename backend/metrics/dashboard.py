"""Shared dashboard metric contract for the API, cards and spreadsheet export.

Ratio values are fractions (0.5 means 50%); missing values remain None.
Legacy KPI fields stay available for existing detail views.
"""
from math import isfinite

from config.metrics import DASHBOARD_KPI_CARDS, METRICS
from metrics.formulas import safe_divide


def number(value):
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def period_target(values, period):
    values = values or {}
    mode = (period or {}).get("targetMode", "year")
    if mode == "year":
        return number(values.get("year"))
    if mode == "month":
        month = int((period.get("endDate") or "0000-01")[5:7])
        months = values.get("month") or []
        return number(months[month - 1]) if len(months) >= month else None
    return None


def ratio_metric(code, numerator, denominator, *, cutoff=None, precision="month", reason=None):
    numerator, denominator = number(numerator), number(denominator)
    if not reason:
        if numerator is None:
            reason = "缺少实绩数据"
        elif denominator is None:
            reason = "缺少分母数据"
        elif denominator <= 0:
            reason = "分母必须大于零"
    value = safe_divide(numerator, denominator) if not reason else None
    definition = METRICS[code]
    return {
        "code": code, "value": value, "calculable": value is not None,
        "status": "ok" if value is not None else "unavailable", "reason": reason,
        "numerator": numerator, "denominator": denominator,
        "unit": definition["unit"], "definition": definition["definition"],
        "cutoff": cutoff, "precision": precision, "displayDigits": 1,
    }


def _sum_complete(rows, field):
    values = [number(row.get(field)) for row in rows]
    return sum(values) if values and all(v is not None for v in values) else None


def _percapita_metric(rows, premium, months, cutoff, *, missing=False):
    complete = rows and months > 0 and all(row.get("months") == months
        and number(row.get("avg_sum")) is not None and not row.get("incomplete") for row in rows)
    avg_hc = safe_divide(_sum_complete(rows, "avg_sum"), months) if complete else None
    reason = "当前范围缺少完整的同口径月度人力数据" if not complete or missing else None
    result = ratio_metric("avg_premium", safe_divide(premium, months), avg_hc, cutoff=cutoff, reason=reason)
    result.update(coveredMonths=months, periodPremium=premium)
    return result


def _yoy(current, previous):
    ratio = safe_divide(current, previous)
    return {"value": ratio - 1 if ratio is not None else None, "unit": "%",
            "definition": "本期 / 上年同期 - 1"}


def build_dashboard_metrics(kpi, target_payload=None):
    period = kpi.get("period") or {}
    daily = kpi.get("daily_cutoff") or {}
    month_cutoff = f"{kpi['year']}-{int(kpi.get('month') or 1):02d}"
    cutoff = {"transform": daily.get("transform"), "jingdai": daily.get("jingdai"),
              "year": kpi["year"], "monthly": month_cutoff}
    precision = "day" if daily.get("use_daily") else "month"
    sources = kpi.get("metric_sources") or {}
    qj = kpi.get("qj_premium") or {}
    value = kpi.get("value") or {}
    value_tf = sum(number(value.get(ch)) or 0 for ch in ("OTO", "证保", "蚁桥"))
    value_jd = number(value.get("经代")) or 0
    specs = {
        "overall": ("qjPremium", qj.get("total"), qj.get("jingdai"), qj.get("total_transform")),
        "value": ("value", value_tf + value_jd, value_jd, value_tf),
        "annuity": ("shangbao", kpi.get("annuity_total"), kpi.get("annuity_jd"), kpi.get("annuity_tf")),
        "protection": ("baozhang", kpi.get("protection_total"), kpi.get("protection_jd"), kpi.get("protection_tf")),
        "10year": ("tenYear", kpi.get("tenyear_total"), kpi.get("tenyear_jd"), kpi.get("tenyear_tf")),
        "longterm": ("qjPremium", kpi.get("longterm_qj"), kpi.get("longterm_qj_jd"), kpi.get("longterm_qj_tf")),
    }
    cards = {}
    definitions = {card["code"]: card["definition"] for card in DASHBOARD_KPI_CARDS}
    for code, (category, total, jd, tf) in specs.items():
        cards[code] = {}
        channel_fields = (("OTO", "oto"), ("证保", "zhengbao"), ("蚁桥", "yiqiao"))
        if code == "overall":
            channel_actuals = {ch: qj.get(field) for ch, field in channel_fields}
        elif code == "value":
            channel_actuals = {ch: value.get(ch) for ch, _ in channel_fields}
        elif code == "longterm":
            channel_actuals = kpi.get("longterm_qj_by_channel") or {}
        else:
            channel_actuals = (kpi.get("product_by_channel") or {}).get(code) or {}
        scopes = [("overall", "整体", total), ("jingdai", "经代", jd), ("transform", "转型业务", tf)]
        scopes.extend((ch, ch, channel_actuals.get(ch)) for ch, _ in channel_fields)
        for scope, label, actual in scopes:
            values = (((target_payload or {}).get("categories") or {}).get(category) or {}).get("metrics") or {}
            target = period_target(values.get(label), period)
            if scope in ("OTO", "证保", "蚁桥") and code not in ("overall", "value"):
                org_targets = [period_target(categories.get(category), period)
                               for key, categories in ((target_payload or {}).get("orgTargets") or {}).items()
                               if key.endswith("|" + scope)]
                configured = [value for value in org_targets if value is not None]
                if configured and sum(configured) > 0:
                    target = sum(configured)
            reason = None
            source_name = "value" if code == "value" else "performance"
            if sources.get(source_name) is False:
                actual, reason = None, "所选范围缺少实绩来源"
            elif period.get("targetMode") == "none":
                reason = "当前日期区间没有对应的正式目标"
            elif target is None:
                reason = "未配置对应的服务端正式目标"
            result = ratio_metric("achievement_rate", actual, target,
                                  cutoff=month_cutoff if code == "value" else cutoff,
                                  precision="month" if code == "value" else precision, reason=reason)
            result["definition"] = definitions[code]
            if code == "10year" and precision == "day" and sources.get("tenyear_jingdai_precision") == "month" and scope in ("overall", "jingdai"):
                result["precision"] = "mixed" if scope == "overall" else "month"
                result["warning"] = "经代10年期交期日表不可用，按月级数据回退"
            if code == "value" and sources.get("value_jingdai") is False and scope in ("overall", "jingdai"):
                # Preserve the approved provisional scope, with an explicit coverage warning.
                result["coverage"] = "经代+OTO+证保+蚁桥；经代价值尚未接入，按既有口径暂计0"
                result["warning"] = "经代价值尚未接入，当前为暂计口径"
                if result["calculable"]:
                    result["status"] = "provisional"
            if code == "overall":
                previous_field = {"overall": "total", "jingdai": "jingdai", "transform": "total_transform",
                                  "OTO": "oto", "证保": "zhengbao", "蚁桥": "yiqiao"}[scope]
                result["yoy"] = _yoy(actual, (kpi.get("qj_premium_prev") or {}).get(previous_field))
            elif code == "longterm":
                previous = {"overall": kpi.get("longterm_qj_prev"), "jingdai": kpi.get("longterm_qj_jd_prev"),
                            "transform": kpi.get("longterm_qj_tf_prev")}.get(scope)
                if scope in ("OTO", "证保", "蚁桥"):
                    previous = (kpi.get("longterm_qj_prev_by_channel") or {}).get(scope)
                result["yoy"] = _yoy(actual, previous)
            cards[code][scope] = result

    hr = kpi.get("hr") or {}
    current = list(hr.values())
    previous = list((kpi.get("hr_prev") or {}).values())
    # A channel with premiums but no HR cannot be silently omitted from the denominator.
    missing_channel = any(number(qj.get(field)) not in (None, 0) and channel not in hr
                          for channel, field in (("OTO", "oto"), ("证保", "zhengbao"), ("蚁桥", "yiqiao")))
    activity = ratio_metric("activity_rate", _sum_complete(current, "active"), _sum_complete(current, "avg"),
                            cutoff=month_cutoff, reason="缺少业务线人力数据" if missing_channel else None)
    prior = ratio_metric("activity_rate", _sum_complete(previous, "active"), _sum_complete(previous, "avg"),
                         cutoff=month_cutoff, reason="同期人力业务线覆盖不一致" if set(hr) != set(kpi.get("hr_prev") or {}) else None)
    activity["yoy"] = {
        "value": (activity["value"] - prior["value"]) * 100 if activity["calculable"] and prior["calculable"] else None,
        "unit": "pp", "definition": "本期活动率 - 上年同期活动率（百分点）",
    }
    activity["byChannel"] = {}
    for channel in ("OTO", "证保", "蚁桥"):
        row = hr.get(channel) or {}
        previous_row = (kpi.get("hr_prev") or {}).get(channel) or {}
        metric = ratio_metric("activity_rate", row.get("active"), row.get("avg"), cutoff=month_cutoff)
        prior_metric = ratio_metric("activity_rate", previous_row.get("active"), previous_row.get("avg"), cutoff=month_cutoff)
        metric["yoy"] = {"value": (metric["value"] - prior_metric["value"]) * 100
                         if metric["calculable"] and prior_metric["calculable"] else None, "unit": "pp"}
        activity["byChannel"][channel] = metric
    cards["activity"] = activity

    start_month = int((period.get("startDate") or f"{kpi['year']}-01")[5:7])
    end_month = int((period.get("endDate") or month_cutoff)[5:7])
    covered_months = end_month - start_month + 1
    premium_available = sources.get("performance_transform", sources.get("performance")) is not False
    percapita = _percapita_metric(current, qj.get("total_transform") if premium_available else None,
                                 covered_months, month_cutoff, missing=missing_channel)
    prior_percapita = _percapita_metric(previous, (kpi.get("qj_premium_prev") or {}).get("total_transform"),
                                       covered_months, month_cutoff, missing=set(hr) != set(kpi.get("hr_prev") or {}))
    percapita["yoy"] = {"value": percapita["value"] - prior_percapita["value"]
                        if percapita["calculable"] and prior_percapita["calculable"] else None, "unit": "万元/人"}
    percapita["byChannel"] = {}
    for channel, field in channel_fields:
        rows = [hr[channel]] if channel in hr else []
        metric = _percapita_metric(rows, qj.get(field) if premium_available else None, covered_months, month_cutoff)
        prior_rows = [kpi["hr_prev"][channel]] if channel in (kpi.get("hr_prev") or {}) else []
        prior_metric = _percapita_metric(prior_rows, (kpi.get("qj_premium_prev") or {}).get(field), covered_months, month_cutoff)
        metric["yoy"] = {"value": metric["value"] - prior_metric["value"]
                         if metric["calculable"] and prior_metric["calculable"] else None, "unit": "万元/人"}
        percapita["byChannel"][channel] = metric
    cards["percapita"] = percapita
    return {"version": 1, "ratioScale": "fraction", "cards": cards}
