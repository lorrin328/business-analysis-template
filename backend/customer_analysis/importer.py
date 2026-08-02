"""Shared parsing rules, templates and aggregate audit views for customer imports."""
from __future__ import annotations

import csv
import io
from copy import copy
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from openpyxl import Workbook

from db.connection import get_db


CUSTOMER_IMPORT_COLUMNS = [
    "投保单号", "投保人id", "投保时间", "导入时间", "回销时间", "承保时间", "入账时间",
    "犹豫期退保时间", "保单状态名称", "保单终止原因",
]
REQUIRED_COLUMNS = {"投保单号", "投保人id", "导入时间", "承保时间", "保单状态名称"}
HEADER_ALIASES = {
    "保单号": "投保单号", "客户id": "投保人id", "客户ID": "投保人id", "投保人ID": "投保人id",
    "快照时间": "导入时间", "数据导入时间": "导入时间", "承保日期": "承保时间",
    "保单状态": "保单状态名称", "终止原因": "保单终止原因",
}
DATE_COLUMNS = {
    "投保时间", "导入时间", "回销时间", "承保时间", "入账时间", "犹豫期退保时间",
}


class CustomerImportError(ValueError):
    pass


@dataclass
class NormalizedPolicy:
    policy_no: str
    customer_id: str
    application_time: str
    import_time: str
    callback_time: str
    underwriting_time: str
    first_account_time: str
    latest_account_time: str
    hesitation_surrender_time: str
    policy_status: str
    termination_reason: str
    status_group: str
    raw_row_count: int = 1


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _canonical_date(value, *, required: bool = False) -> str:
    text = _text(value)
    if not text:
        if required:
            raise CustomerImportError("必需日期为空")
        return ""
    normalized = text.replace("/", "-").replace("T", " ")
    if normalized.endswith("Z"):
        normalized = normalized[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d"):
        try:
            candidate = normalized[:19] if fmt == "%Y-%m-%d %H:%M:%S" else normalized
            parsed = datetime.strptime(candidate, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise CustomerImportError("日期格式无法识别") from exc


def _status_group(status: str, reason: str, hesitation_time: str) -> str:
    status, reason = status.strip(), reason.strip()
    if status == "有效":
        return "active"
    if status == "停效":
        return "suspended"
    if reason == "退保终止":
        return "surrender"
    if reason == "契撤终止" or hesitation_time:
        return "cooling_off"
    if reason in {"到期终止", "满期终止"}:
        return "maturity"
    if reason == "一年期险种逾期未付终止":
        return "short_expiry"
    if reason in {"一般理赔终止", "死亡理赔终止", "理赔解约终止", "死亡终止", "短期健康险被保人死亡终止"}:
        return "claim"
    if status == "终止":
        return "other_terminated"
    return "unknown"


def _normalize_headers(values: Iterable) -> list[str]:
    return [HEADER_ALIASES.get(_text(value).lstrip("\ufeff"), _text(value).lstrip("\ufeff")) for value in values]


def _find_header(rows: Iterable[tuple], file_name: str) -> tuple[int, list[str]]:
    for number, row in enumerate(rows, start=1):
        headers = _normalize_headers(row)
        if REQUIRED_COLUMNS.issubset(set(headers)):
            nonempty = [item for item in headers if item]
            if len(nonempty) != len(set(nonempty)):
                raise CustomerImportError(f"{file_name}映射后存在重复字段")
            return number, headers
        if number >= 20:
            break
    raise CustomerImportError(f"{file_name}前20行未找到客户清单表头")


def _to_policy(row: dict[str, object]) -> NormalizedPolicy:
    policy_no = _text(row.get("投保单号"))
    customer_id = _text(row.get("投保人id"))
    status = _text(row.get("保单状态名称"))
    if not policy_no or not customer_id or not status:
        raise CustomerImportError("必需标识或状态为空")
    dates = {
        column: _canonical_date(row.get(column), required=column in {"导入时间", "承保时间"})
        for column in DATE_COLUMNS
    }
    account = dates["入账时间"]
    reason = _text(row.get("保单终止原因"))
    return NormalizedPolicy(
        policy_no=policy_no, customer_id=customer_id, application_time=dates["投保时间"],
        import_time=dates["导入时间"], callback_time=dates["回销时间"],
        underwriting_time=dates["承保时间"], first_account_time=account, latest_account_time=account,
        hesitation_surrender_time=dates["犹豫期退保时间"], policy_status=status,
        termination_reason=reason, status_group=_status_group(status, reason, dates["犹豫期退保时间"]),
    )


def list_customer_import_batches(limit: int = 10) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, imported_by, file_count, source_rows, normalized_policy_rows,
                      inserted_policies, updated_policies, unchanged_policies, skipped_older_policies,
                      linked_performance_policies, source_cutoff, status, imported_at, completed_at
               FROM customer_import_batches ORDER BY id DESC LIMIT ?""", (max(1, min(limit, 50)),),
        ).fetchall()
    return [{
        "batchId": int(row["id"]), "importedBy": row["imported_by"], "fileCount": int(row["file_count"]),
        "sourceRows": int(row["source_rows"]), "normalizedPolicies": int(row["normalized_policy_rows"]),
        "insertedPolicies": int(row["inserted_policies"]), "updatedPolicies": int(row["updated_policies"]),
        "unchangedPolicies": int(row["unchanged_policies"]), "skippedOlderPolicies": int(row["skipped_older_policies"]),
        "linkedPerformancePolicies": int(row["linked_performance_policies"]), "sourceCutoff": row["source_cutoff"],
        "status": row["status"], "importedAt": row["imported_at"], "completedAt": row["completed_at"],
    } for row in rows]


def build_customer_import_template(file_format: str) -> tuple[bytes, str, str]:
    if file_format == "csv":
        stream = io.StringIO(newline="")
        csv.writer(stream).writerow(CUSTOMER_IMPORT_COLUMNS)
        return ("\ufeff" + stream.getvalue()).encode("utf-8"), "text/csv; charset=utf-8", "客户清单导入模板.csv"
    if file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "客户清单"
        sheet.append(CUSTOMER_IMPORT_COLUMNS)
        for cell in sheet[1]:
            font = copy(cell.font)
            font.bold = True
            cell.font = font
        output = io.BytesIO()
        workbook.save(output)
        workbook.close()
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "客户清单导入模板.xlsx"
    raise CustomerImportError("模板仅支持csv或xlsx")
