from __future__ import annotations

import re
from collections import defaultdict

from variable_expense.xlsx_reader import CachedXlsx


RULE_VERSION = "2026-variable-expense-v1"
DATA_SOURCE_MODE = "independent_finance_workbook"
REQUIRED_SHEETS = {
    "报告数据",
    "一对一沟通会",
    "【机构可用】费用政策",
    "【机构可用】总部支援1—方案下拨",
    "【机构可用】总部支援2—总部DU号等费用",
    "【财务动支】首年直接变费",
    "【条线可用】变费可用（含证保结转）",
}
def _number(value, label: str, errors: list[dict]) -> float | None:
    if value is None or value == "" or value == "-":
        errors.append({"level": "high", "title": f"{label}缺少可用数值"})
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append({"level": "high", "title": f"{label}不是有效数值"})
        return None


def _safe_rate(actual: float | None, available: float | None) -> float | None:
    if actual is None or available is None or available <= 0:
        return None
    return actual / available


def _status(rate: float | None) -> str:
    if rate is None:
        return "not_calculable"
    if rate > 1:
        return "over"
    if rate >= 0.9:
        return "near"
    return "normal"


def _round(value: float | None, digits: int = 8) -> float | None:
    return round(value, digits) if value is not None else None


def _period(filename: str, supplied_period: str | None) -> str:
    supplied = (supplied_period or "").strip()
    if supplied and not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", supplied):
        raise ValueError("统计期间必须使用 YYYY-MM 格式")
    match = re.search(r"(?:(?P<year>20\d{2})|(?P<short>\d{2})年).*?截至\s*(?P<month>\d{1,2})月", filename)
    inferred = ""
    if match:
        year = match.group("year") or f"20{match.group('short')}"
        inferred = f"{year}-{int(match.group('month')):02d}"
    if supplied and inferred and supplied != inferred:
        raise ValueError(f"上传期间 {supplied} 与文件名识别期间 {inferred} 不一致")
    if not supplied and not inferred:
        raise ValueError("无法从文件名识别统计期间，请选择统计期间")
    return supplied or inferred


def _get_number(book: CachedXlsx, sheet: str, ref: str, label: str, errors: list[dict]) -> float | None:
    cell = book.cell(sheet, ref)
    if cell.formula and cell.value is None:
        errors.append({"level": "high", "title": f"{label}公式没有缓存结果", "source": f"{sheet}!{ref}"})
        return None
    return _number(cell.value, label, errors)


def _metric(available: float | None, actual: float | None) -> dict:
    rate = _safe_rate(actual, available)
    balance = available - actual if available is not None and actual is not None else None
    return {
        "available": _round(available),
        "actual": _round(actual),
        "rate": _round(rate),
        "balance": _round(balance),
        "status": _status(rate),
    }


def _mode_name(value) -> str:
    text = str(value or "").strip()
    return {"证券": "证保", "网服": "蚁桥"}.get(text, text or "未归属")


def _cell(row: dict, col: int):
    item = row.get(col)
    return item.value if item else None


def _aggregate_projects(book: CachedXlsx) -> list[dict]:
    values: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: {"available": 0.0, "actual": 0.0})
    available_projects: dict[tuple[str, str], set[str]] = defaultdict(set)
    actual_projects: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in book.rows("【机构可用】费用政策", 9):
        org, project, mode = _cell(row, 3), _cell(row, 4), _cell(row, 5)
        if not org:
            continue
        key = (str(org).strip(), _mode_name(mode), str(project or "未归属").strip())
        amount = _cell(row, 13)
        if isinstance(amount, (int, float)):
            values[key]["available"] += float(amount) / 10000
            if float(amount):
                available_projects[key[:2]].add(key[2])
    for row in book.rows("【机构可用】总部支援1—方案下拨", 3):
        org, mode, project = _cell(row, 2), _cell(row, 3), _cell(row, 4)
        if not org:
            continue
        key = (str(org).strip(), _mode_name(mode), str(project or "未归属").strip())
        values[key]["available"] += sum(
            float(_cell(row, col))
            for col in range(5, max(row.keys(), default=4) + 1)
            if isinstance(_cell(row, col), (int, float))
        ) / 10000
        if values[key]["available"]:
            available_projects[key[:2]].add(key[2])
    for row in book.rows("【机构可用】总部支援2—总部DU号等费用", 9):
        org, mode, project, amount = (_cell(row, col) for col in (2, 3, 4, 5))
        if not org or not isinstance(amount, (int, float)):
            continue
        key = (str(org).strip(), _mode_name(mode), str(project or "未归属").strip())
        values[key]["available"] += float(amount)
        if float(amount):
            available_projects[key[:2]].add(key[2])
    for row in book.rows("【财务动支】首年直接变费", 5):
        if str(_cell(row, 6) or "").strip().upper() != "Y":
            continue
        org, mode, project = _cell(row, 1), _cell(row, 2), _cell(row, 3)
        amount = _cell(row, 5)
        if not org or not isinstance(amount, (int, float)):
            continue
        key = (str(org).strip(), _mode_name(mode), str(project or "未归属").strip())
        values[key]["actual"] += float(amount)
        if float(amount):
            actual_projects[key[:2]].add(key[2])
    result = []
    for (org, mode, project), amounts in values.items():
        comparable = available_projects[(org, mode)] == actual_projects[(org, mode)]
        item = {"org": org, "mode": mode, "project": project, **_metric(amounts["available"], amounts["actual"])}
        item["comparisonStatus"] = "matched" if comparable else "mapping_required"
        if not comparable:
            item.update({"rate": None, "balance": None, "status": "not_calculable"})
        result.append(item)
    return sorted(result, key=lambda item: (-(item["actual"] or 0), item["org"], item["project"]))


def _aggregate_products(book: CachedXlsx) -> list[dict]:
    values: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(lambda: {"premium": 0.0, "available": 0.0})
    for row in book.rows("【条线可用】变费可用（含证保结转）", 4):
        org, mode, code, name, term = (_cell(row, col) for col in (1, 11, 3, 4, 5))
        if not org or not code:
            continue
        normalized_mode = _mode_name(mode)
        if normalized_mode not in {"OTO", "蚁桥", "证保"}:
            continue
        normalized_code = str(code).split(".")[0]
        key = (str(org).strip(), normalized_mode, normalized_code, f"{str(name or '').strip()}｜{str(term or '').strip()}年交")
        premium, available = _cell(row, 7), _cell(row, 10)
        if isinstance(premium, (int, float)):
            values[key]["premium"] += float(premium) / 10000
        if isinstance(available, (int, float)):
            values[key]["available"] += float(available)
    result = [
        {
            "org": org,
            "mode": mode,
            "productCode": code,
            "product": product,
            "annualizedPremium": _round(amounts["premium"]),
            "available": _round(amounts["available"]),
        }
        for (org, mode, code, product), amounts in values.items()
    ]
    return sorted(result, key=lambda item: (-(item["available"] or 0), item["productCode"]))


def analyze_variable_expense_workbook(content: bytes, filename: str, supplied_period: str | None = None) -> dict:
    period = _period(filename, supplied_period)
    book = CachedXlsx(content)
    missing_sheets = sorted(REQUIRED_SHEETS - set(book.sheet_names))
    if missing_sheets:
        raise ValueError(f"缺少必要工作表：{'、'.join(missing_sheets)}")

    warnings: list[dict] = []
    checks: list[dict] = []
    n = lambda ref, label: _get_number(book, "报告数据", ref, label, warnings)

    transformation_first = _metric(n("AG41", "转型首年变动可用"), n("AH41", "转型首年变动动支"))
    renewal = _metric(n("AG42", "全口径续年变动可用"), n("AH42", "全口径续年变动动支"))
    transformation = _metric(n("AG43", "转型变动可用合计"), n("AH43", "转型变动动支合计"))
    agency_variable = _metric(n("C6", "经代首年变动可用"), n("D6", "经代首年变动动支"))
    agency_total = _metric(n("C5", "经代首年固定加变动可用"), n("D5", "经代首年固定加变动动支"))

    first_plus_renewal_available = (transformation_first["available"] or 0) + (renewal["available"] or 0)
    first_plus_renewal_actual = (transformation_first["actual"] or 0) + (renewal["actual"] or 0)
    for label, left, right in [
        ("转型可用合计=首年+续年", transformation["available"], first_plus_renewal_available),
        ("转型动支合计=首年+续年", transformation["actual"], first_plus_renewal_actual),
    ]:
        difference = None if left is None else left - right
        passed = difference is not None and abs(difference) <= 0.02
        checks.append({"name": label, "passed": passed, "difference": _round(difference)})
        if not passed:
            warnings.append({"level": "high", "title": f"{label}未通过", "difference": _round(difference)})

    modes = []
    for row, name in [(47, "OTO"), (48, "蚁桥"), (49, "证保"), (50, "公共")]:
        modes.append({"mode": name, **_metric(n(f"AP{row}", f"{name}变动可用"), n(f"AS{row}", f"{name}变动动支"))})

    institutions = []
    for row in book.rows("一对一沟通会", 5):
        org = str(_cell(row, 4) or "").strip()
        if not org:
            continue
        variable = _metric(
            _number(_cell(row, 9), f"{org}变费可用", warnings),
            _number(_cell(row, 10), f"{org}变费动支", warnings),
        )
        promotion = _metric(
            _number(_cell(row, 13), f"{org}业推可用", warnings),
            _number(_cell(row, 14), f"{org}业推动支", warnings),
        )
        institutions.append(
            {
                "org": org,
                "premium": _round(_number(_cell(row, 6), f"{org}期交保费", warnings)),
                "monthlyHeadcount": _round(_number(_cell(row, 7), f"{org}月均人力", warnings)),
                "perCapitaPremium": _round(_number(_cell(row, 8), f"{org}人均期交保费", warnings)),
                "variable": variable,
                "promotion": promotion,
            }
        )
        if org == "全系统合计":
            break
    system_row = next((item for item in institutions if item["org"] == "全系统合计"), None)
    institutions = [item for item in institutions if item["org"] != "全系统合计"]
    institutions.sort(key=lambda item: (-(item["variable"]["rate"] or -1), item["org"]))

    composition = {
        "basicLawFixed": n("BQ81", "基本法固定动支"),
        "basicLawFloating": n("BR81", "基本法浮动动支"),
        "commission": n("BS81", "手续费动支"),
        "promotion": n("BT81", "业务推动费动支"),
        "total": n("BU81", "机构变费动支合计"),
    }
    component_sum = sum(value or 0 for key, value in composition.items() if key != "total")
    composition["other"] = _round((composition["total"] or 0) - component_sum)
    composition = {key: _round(value) for key, value in composition.items()}
    actual_difference = None if not system_row or composition["total"] is None else system_row["variable"]["actual"] - composition["total"]
    actual_passed = actual_difference is not None and abs(actual_difference) <= 0.02
    checks.append({"name": "机构动支合计=费用构成合计", "passed": actual_passed, "difference": _round(actual_difference)})
    if not actual_passed:
        warnings.append({"level": "high", "title": "机构动支与费用构成不一致", "difference": _round(actual_difference)})

    # Formal-report snapshots are not embedded in the public source tree.
    # If a report comparison is needed, it must come from a protected,
    # versioned runtime source rather than hard-coded business figures.
    report_comparison = None

    project_details = _aggregate_projects(book)
    project_totals = {
        "available": _round(sum(item["available"] or 0 for item in project_details)),
        "actual": _round(sum(item["actual"] or 0 for item in project_details)),
    }
    official_project_basis = system_row["variable"] if system_row else None
    if official_project_basis:
        available_difference = project_totals["available"] - official_project_basis["available"]
        actual_difference = project_totals["actual"] - official_project_basis["actual"]
        project_reconciled = abs(available_difference) <= 0.02 and abs(actual_difference) <= 0.02
        checks.append(
            {
                "name": "项目源表合计=机构正式汇总",
                "passed": project_reconciled,
                "difference": _round(max(abs(available_difference), abs(actual_difference))),
                "severity": "advisory",
            }
        )
        if not project_reconciled:
            warnings.append(
                {
                    "level": "medium",
                    "title": "项目源表口径尚未与机构正式汇总完全对齐",
                    "detail": (
                        f"可用差额{available_difference:.2f}万元、动支差额{actual_difference:.2f}万元；"
                        "项目表保留源值，名称未完全匹配时不计算项目执行率。"
                    ),
                }
            )

    blocking = [item for item in warnings if item["level"] == "high"]
    summary = {
        "transformation": transformation,
        "transformationFirstYear": transformation_first,
        "renewal": renewal,
        "agencyVariable": agency_variable,
        "agencyTotal": agency_total,
        "institutionVariable": system_row["variable"] if system_row else None,
        "promotion": system_row["promotion"] if system_row else None,
    }
    return {
        "period": period,
        "ruleVersion": RULE_VERSION,
        "summary": summary,
        "details": {
            "modes": modes,
            "institutions": institutions,
            "composition": composition,
            "projects": project_details,
            "projectTotals": project_totals,
            "products": _aggregate_products(book),
        },
        "quality": {
            "status": "blocked" if blocking else ("warning" if warnings else "passed"),
            "checks": checks,
            "warnings": warnings,
            "sourceCells": {
                "transformation": "报告数据!AG41:AJ43",
                "modes": "报告数据!AL45:AU52",
                "institutions": "一对一沟通会!D5:P15",
                "composition": "报告数据!BP69:BU81",
            },
            "calculationNote": "公式取工作簿已保存的缓存值；金额按万元保存全精度，页面仅格式化显示。",
        },
        "reportComparison": report_comparison,
        "definitions": {
            "available": "依据财务月报费用政策、保费与结转计算的变动费用可用额度。",
            "actual": "财务月报中纳入统计的实际动支。",
            "rate": "实际动支÷变动费用可用；可用小于等于0时不计算。",
            "balance": "变动费用可用－实际动支。",
            "unit": "万元",
        },
    }
