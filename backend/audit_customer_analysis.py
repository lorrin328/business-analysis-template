"""Validate the full-history and customer-analysis database without exposing customer details."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ALLOWED_LINES = {"OTO", "证保", "蚁桥"}
ALLOWED_STATUS_GROUPS = {
    "active", "suspended", "surrender", "cooling_off", "maturity",
    "short_expiry", "claim", "other_terminated", "unmatched", "unknown",
}


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()):
    return conn.execute(sql, params).fetchone()[0]


def audit(database: Path, *, full_integrity: bool = False) -> dict:
    conn = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        batch = conn.execute(
            """SELECT id, source_cutoff, performance_rows, customer_source_rows,
                      customer_policy_rows, source_text_issue_rows, status
               FROM history_import_batches WHERE status='success' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if not batch:
            return {"ok": False, "errors": ["没有成功的全量历史导入批次"], "warnings": [], "metrics": {}}

        batch_id = int(batch["id"])
        metrics = {
            "batchId": batch_id,
            "sourceCutoff": batch["source_cutoff"],
            "performanceRows": _scalar(conn, "SELECT COUNT(*) FROM performance"),
            "performanceMonths": _scalar(conn, "SELECT COUNT(DISTINCT substr(CAST(\"年月\" AS TEXT),1,7)) FROM performance"),
            "customerSourceRows": _scalar(conn, "SELECT COALESCE(SUM(raw_row_count),0) FROM customer_policy_snapshot WHERE batch_id=?", (batch_id,)),
            "customerPolicyRows": _scalar(conn, "SELECT COUNT(*) FROM customer_policy_snapshot WHERE batch_id=?", (batch_id,)),
            "customerFactRows": _scalar(conn, "SELECT COUNT(*) FROM customer_policy_month_fact WHERE batch_id=?", (batch_id,)),
            "customerFactPolicies": _scalar(conn, "SELECT COUNT(DISTINCT policy_no) FROM customer_policy_month_fact WHERE batch_id=?", (batch_id,)),
            "longtermFactRows": _scalar(conn, "SELECT COUNT(*) FROM customer_policy_month_fact WHERE batch_id=? AND is_longterm=1", (batch_id,)),
            "sourceTextIssueRows": int(batch["source_text_issue_rows"] or 0),
        }
        errors: list[str] = []
        warnings: list[str] = []
        expected = {
            "performanceRows": int(batch["performance_rows"]),
            "customerSourceRows": int(batch["customer_source_rows"]),
            "customerPolicyRows": int(batch["customer_policy_rows"]),
        }
        for key, value in expected.items():
            if metrics[key] != value:
                errors.append(f"{key}与导入批次不一致：actual={metrics[key]}, batch={value}")

        duplicate_facts = _scalar(
            conn,
            """SELECT COUNT(*) FROM (
                   SELECT year, month, business_line, org, policy_no, COUNT(*) c
                   FROM customer_policy_month_fact WHERE batch_id=?
                   GROUP BY year, month, business_line, org, policy_no HAVING c>1
               )""",
            (batch_id,),
        )
        invalid_lines = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT business_line FROM customer_policy_month_fact WHERE batch_id=?", (batch_id,)
            ) if row[0] not in ALLOWED_LINES
        ]
        invalid_statuses = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT status_group FROM customer_policy_month_fact WHERE batch_id=?", (batch_id,)
            ) if row[0] not in ALLOWED_STATUS_GROUPS
        ]
        if duplicate_facts:
            errors.append(f"客户保单月事实存在{duplicate_facts}组重复键")
        if invalid_lines:
            errors.append(f"客户事实出现未定义业务：{','.join(invalid_lines)}")
        if invalid_statuses:
            errors.append(f"客户事实出现未定义状态：{','.join(invalid_statuses)}")
        if not metrics["customerFactRows"]:
            errors.append("客户保单月事实为空")
        if not metrics["longtermFactRows"]:
            warnings.append("长险事实为0，请复核长短险枚举和产品代码")

        matched = _scalar(
            conn,
            "SELECT COUNT(DISTINCT CASE WHEN customer_match=1 THEN policy_no END) FROM customer_policy_month_fact WHERE batch_id=?",
            (batch_id,),
        )
        metrics["policyMatchRate"] = matched / metrics["customerFactPolicies"] if metrics["customerFactPolicies"] else None
        metrics["duplicateFactKeys"] = duplicate_facts
        metrics["quickCheck"] = _scalar(conn, "PRAGMA quick_check")
        if metrics["quickCheck"] != "ok":
            errors.append(f"SQLite quick_check失败：{metrics['quickCheck']}")
        if full_integrity:
            metrics["integrityCheck"] = _scalar(conn, "PRAGMA integrity_check")
            if metrics["integrityCheck"] != "ok":
                errors.append(f"SQLite integrity_check失败：{metrics['integrityCheck']}")
        return {"ok": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="校验全量历史与客户分析数据库")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--full-integrity", action="store_true")
    args = parser.parse_args()
    result = audit(args.database, full_integrity=args.full_integrity)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
