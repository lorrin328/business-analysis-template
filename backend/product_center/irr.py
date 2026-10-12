"""Independent policy-year IRR verification; no calendar-date/XIRR assumptions."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Mapping


class IRRError(ValueError):
    """A cashflow cannot be assigned a unique, bounded annual IRR."""


def normalized_cashflows(cashflows: Iterable[Mapping]) -> list[tuple[float, float]]:
    grouped = defaultdict(list)
    for item in cashflows:
        time = item.get("timeYear", item.get("time_year"))
        amount = item.get("amount")
        if isinstance(time, bool) or isinstance(amount, bool):
            raise IRRError("现金流时点和金额必须为有限数值")
        try:
            time, amount = float(time), float(amount)
        except (TypeError, ValueError) as exc:
            raise IRRError("现金流时点和金额必须为有限数值") from exc
        if not math.isfinite(time) or not math.isfinite(amount) or time < 0:
            raise IRRError("现金流时点和金额必须为有限数值，时点不能为负")
        grouped[time].append(amount)
    result = [(t, math.fsum(values)) for t, values in sorted(grouped.items())]
    return [(t, a) for t, a in result if a != 0]


def npv(cashflows: Iterable[Mapping], rate: float) -> float:
    if not math.isfinite(rate) or rate <= -1:
        raise IRRError("IRR必须大于-100%且为有限数值")
    flows = normalized_cashflows(cashflows)
    try:
        return math.fsum(a * math.exp(-t * math.log1p(rate)) for t, a in flows)
    except OverflowError as exc:
        raise IRRError("折现数值超出可计算范围") from exc


def solve_irr(cashflows: Iterable[Mapping]) -> float:
    """Solve conventional flows by bounded bisection in log(1+r).

    Aggregation occurs only for root uniqueness checks, never in stored flows.
    More than one sign change is conservatively rejected, including flows that
    could have multiple roots. This is intentionally not a guessed root picker.
    """
    flows = normalized_cashflows(cashflows)
    signs = [1 if a > 0 else -1 for _, a in flows]
    if len(signs) < 2 or len(set(signs)) < 2:
        raise IRRError("现金流必须同时有投入和回收")
    changes = sum(a != b for a, b in zip(signs, signs[1:]))
    if changes != 1:
        raise IRRError("现金流存在多次符号变化，可能多根，拒绝选择任意IRR")

    def scaled_value(log_rate: float) -> float:
        exponents = [math.log(abs(a)) - t * log_rate for t, a in flows]
        scale = max(exponents)
        return math.fsum(math.copysign(math.exp(x - scale), a)
                         for x, (_, a) in zip(exponents, flows))

    low, high = math.log(1e-9), math.log(1e7)
    left, right = scaled_value(low), scaled_value(high)
    if left == 0:
        return math.expm1(low)
    if right == 0:
        return math.expm1(high)
    if left * right >= 0:
        raise IRRError("指定边界内无唯一可确认IRR")
    for _ in range(200):
        middle = (low + high) / 2
        value = scaled_value(middle)
        if value == 0 or middle == low or middle == high:
            low = high = middle
            break
        if (value > 0) == (left > 0):
            low, left = middle, value
        else:
            high = middle
    rate = math.expm1((low + high) / 2)
    if abs(npv([{"timeYear": t, "amount": a} for t, a in flows], rate)) > 0.01:
        raise IRRError("独立IRR解的NPV残差超过0.01元")
    return rate


def verify_record(record: Mapping) -> dict:
    original = record.get("irr", record.get("originalIrr"))
    row = {"id": record.get("result_id", record.get("id")),
           "originalIrr": original, "computedIrr": None,
           "irrDifference": None, "npvResidual": None, "passed": False}
    if original is None:
        row.update(status="pending", reason="原底稿IRR为空，继续待核")
        return row
    try:
        if isinstance(original, bool) or not math.isfinite(float(original)):
            raise IRRError("原底稿IRR不是有限数值")
        rate = solve_irr(record.get("cashflows", []))
        residual = abs(npv(record.get("cashflows", []), rate))
        difference = abs(rate - float(original))
        row.update(computedIrr=rate, irrDifference=difference,
                   npvResidual=residual, passed=difference <= 1e-8 and residual <= 0.01)
        row["status"] = "passed" if row["passed"] else "failed"
        if not row["passed"]:
            row["reason"] = "原IRR差异超过1e-8或NPV残差超过0.01元"
    except (IRRError, ValueError, TypeError) as exc:
        row.update(status="failed", reason=str(exc))
    return row


def verify_calculations(combined: Mapping) -> dict:
    canonical = [*combined.get("records", []), *combined.get("example_records", []),
                 *combined.get("development_maturity", [])]
    ids = [x.get("result_id") for x in canonical]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("情景result_id缺失或重复")
    numeric = [x for x in canonical if x.get("irr") is not None]
    listed = combined.get("all_calculations")
    coverage_errors = []
    if listed is not None:
        lookup = {x.get("result_id"): x for x in listed}
        if len(lookup) != len(listed) or set(lookup) != {x["result_id"] for x in numeric}:
            coverage_errors.append("all_calculations与规范情景数值记录集合不同")
        for item in numeric:
            ref = lookup.get(item["result_id"], {})
            if ref.get("cashflows") != item.get("cashflows") or ref.get("irr") != item.get("irr"):
                coverage_errors.append(f"{item['result_id']}:合并复算清单与规范记录不一致")
    rows = [verify_record(x) for x in numeric]
    failures = [x for x in rows if not x["passed"]]
    return {"method": "独立保单年度IRR；有界对数二分；单次符号变化",
            "irrTolerance": 1e-8, "npvToleranceYuan": 0.01,
            "canonicalCount": len(canonical), "numericCount": len(numeric),
            "pendingCount": len(canonical) - len(numeric),
            "passedCount": len(rows) - len(failures), "failureCount": len(failures),
            "maxIrrDifference": max((x["irrDifference"] or 0 for x in rows), default=0),
            "maxNpvResidual": max((x["npvResidual"] or 0 for x in rows), default=0),
            "coverageErrors": coverage_errors,
            "passed": not failures and not coverage_errors, "rows": rows}
