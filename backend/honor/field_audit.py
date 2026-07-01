"""Field audit for reusing existing dashboard data in the honor domain."""
from __future__ import annotations

import re
from typing import Any

from db.connection import get_db

from .config import FIELD_REQUIREMENTS


def _normalize(value: str) -> str:
    return re.sub(r"[\s_\-（）()【】\[\]/\\]+", "", str(value or "").lower())


def list_tables(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row["name"] if hasattr(row, "keys") else row[0] for row in rows}


def table_columns(conn, table_name: str) -> list[str]:
    if table_name not in list_tables(conn):
        return []
    return [row["name"] if hasattr(row, "keys") else row[1] for row in conn.execute(f'PRAGMA table_info("{table_name}")')]


def match_column(columns: list[str], candidates: list[str]) -> str | None:
    normalized_columns = {_normalize(col): col for col in columns}
    for candidate in candidates:
        if _normalize(candidate) in normalized_columns:
            return normalized_columns[_normalize(candidate)]
    return None


def audit_fields() -> dict[str, Any]:
    with get_db() as conn:
        tables = list_tables(conn)
        raw_tables: dict[str, dict[str, Any]] = {}
        flat_results: list[dict[str, Any]] = []

        for table_name, requirements in FIELD_REQUIREMENTS.items():
            exists = table_name in tables
            columns = table_columns(conn, table_name)
            rows = 0
            if exists:
                rows = int(conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0])
            table_results = []
            for required_field, candidates, level, impact in requirements:
                matched = match_column(columns, candidates)
                item = {
                    "tableName": table_name,
                    "requiredField": required_field,
                    "matchedColumn": matched,
                    "requiredLevel": level,
                    "available": bool(matched),
                    "impact": impact,
                    "fallbackStrategy": "直接使用现有字段" if matched else _fallback_for(required_field, level),
                }
                table_results.append(item)
                flat_results.append(item)
            raw_tables[table_name] = {
                "exists": exists,
                "rowCount": rows,
                "columns": columns,
                "fields": table_results,
            }

        required_items = [r for r in flat_results if r["requiredLevel"] == "required"]
        optional_items = [r for r in flat_results if r["requiredLevel"] != "required"]
        required_coverage = _coverage(required_items)
        optional_coverage = _coverage(optional_items)
        rule_assessment = assess_rules(raw_tables)
        unavailable_rules = [r for r in rule_assessment if r["grade"] in {"C", "D"}]
        return {
            "rawTables": raw_tables,
            "aggregateTables": _aggregate_tables(conn, tables),
            "requiredCoverage": required_coverage,
            "optionalCoverage": optional_coverage,
            "ruleAssessment": rule_assessment,
            "canReuseExistingData": required_coverage["available"] > 0 and any(r["grade"] in {"A", "B"} for r in rule_assessment),
            "needsHonorUpload": False,
            "minimumScope": "个人月度星钻 MVP：仅覆盖转型 OTO、证保；经代和蚁桥（网服）均不涉及星钻。",
            "unavailableRuleCount": len(unavailable_rules),
            "recommendation": "第一阶段不新增上传；先复用现有 performance/hr_data 计算 OTO、证保个人星钻，字段不足规则进入异常清单。",
        }


def assess_rules(raw_tables: dict[str, Any]) -> list[dict[str, str]]:
    def has(table: str, field: str) -> bool:
        fields = raw_tables.get(table, {}).get("fields", [])
        return any(item["requiredField"] == field and item["available"] for item in fields)

    staff_core = all(has("hr_data", f) for f in ["统计年", "统计月", "销售机构名称", "业务模式名称", "人员代码", "月末在职人力"])
    entry_core = all(has("hr_data", f) for f in ["入职年", "入职月"])
    perf_core = all(has("performance", f) for f in ["业务模式", "人员工号", "投保单号", "长短险", "折算保费", "年月"])
    perf_date = has("performance", "承保时间") or has("performance", "入账时间")
    team_core = has("hr_data", "营业组CODE") and has("hr_data", "营业部CODE") and has("hr_data", "职等")
    items = [
        ("个人月度达标", "A" if staff_core and perf_core else "C", "performance + hr_data 可按人员、月份、业务模式计算"),
        ("OTO 月度获钻", "A" if staff_core and perf_core else "C", "OTO 月度标保 >= 20000 且长险 >= 1 件"),
        ("证保月度获钻", "A" if staff_core and perf_core else "C", "证保月度标保 >= 30000 且长险 >= 1 件"),
        ("证保保号", "A" if staff_core and perf_core else "C", "证保有长险件但未达标可保号"),
        ("月度扣减", "A" if staff_core and perf_core else "C", "未达标且非保号月扣 1 颗，最低 0"),
        ("月末非在职清零", "A" if staff_core else "C", "hr_data 有月末在职字段"),
        ("会员等级", "A", "按累计钻石门槛判断"),
        ("新星人力", "A" if staff_core and entry_core else "C", "需要入职年/月"),
        ("证保季度通算", "B" if staff_core and perf_core else "C", "可计算，但完整自然季度和缺月异常需 Phase 3 加强"),
        ("主管团队星钻", "B" if staff_core and perf_core and team_core else "C", "团队字段存在时可做，但仅归集 OTO/证保；团队内蚁桥/网服人员和业绩均排除"),
        ("经理团队星钻", "B" if staff_core and perf_core and team_core else "C", "团队字段存在时可做，但仅归集 OTO/证保；团队内蚁桥/网服人员和业绩均排除"),
        ("机构季度奖励", "B" if staff_core else "C", "可基于会员等级测算，必须标识预计奖励"),
        ("人员明细导出", "A" if staff_core and perf_core else "C", "可基于 honor_person_month/summary 导出"),
        ("异常清单", "A", "字段缺失、日期降级、负保费等均可记录"),
        ("经代星钻", "N/A", "经代不涉及星钻，不纳入计算范围"),
        ("蚁桥/网服星钻", "N/A", "蚁桥（网服）不涉及星钻，不纳入计算范围"),
    ]
    if perf_core and not perf_date:
        items.append(("业绩日期归属", "B", "可按年月字段降级，但必须进入异常或提示"))
    else:
        items.append(("业绩日期归属", "A", "优先承保时间，其次入账时间，最后年月字段"))
    return [{"rule": name, "grade": grade, "note": note} for name, grade, note in items]


def _coverage(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    available = sum(1 for item in items if item["available"])
    return {
        "available": available,
        "total": total,
        "rate": (available / total if total else 0),
    }


def _aggregate_tables(conn, tables: set[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for table in sorted(t for t in tables if t.startswith("agg_")):
        result[table] = table_columns(conn, table)
    return result


def _fallback_for(required_field: str, level: str) -> str:
    if required_field == "折算保费":
        return "缺失时按年化规保和缴费年限折算系数复算，并标记 premium_source=calculated_by_payment_years"
    if required_field in {"承保时间", "入账时间"}:
        return "可按年月字段降级归属，并写入异常提示"
    if level == "optional":
        return "不阻断个人星钻，影响团队或展示深度"
    return "字段不足时不得静默计算，需进入 honor_exceptions"
