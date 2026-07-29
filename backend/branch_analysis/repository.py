from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from db.connection import get_db


REFERENCE_FIELDS = {
    "参考编号",
    "网点类型",
    "证券网点",
    "归属主体",
    "所在省",
    "所在市",
    "网点等级",
    "机构类项目",
    "机构类项目细分",
    "本地异地",
    "纳入常规网点数",
    "源表行号",
}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _read_csv(source: Path) -> tuple[list[dict], str]:
    content = source.read_bytes()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = REFERENCE_FIELDS - fields
        if missing:
            raise ValueError(f"网点参考表缺少字段：{'、'.join(sorted(missing))}")
        rows = [
            {
                "reference_id": _text(row["参考编号"]),
                "branch_type": _text(row["网点类型"]),
                "branch_name": _text(row["证券网点"]),
                "parent_name": _text(row["归属主体"]),
                "province": _text(row["所在省"]),
                "city": _text(row["所在市"]),
                "grade": _text(row["网点等级"]),
                "project": _text(row["机构类项目"]),
                "subproject": _text(row["机构类项目细分"]),
                "locality": _text(row["本地异地"]),
                "include_regular": 1 if _text(row["纳入常规网点数"]) == "是" else 0,
                "source_row": int(_text(row["源表行号"]) or 0),
            }
            for row in reader
            if _text(row.get("证券网点"))
        ]
    return rows, hashlib.sha256(content).hexdigest()


def import_reference_csv(
    source: Path,
    *,
    imported_by: str = "system",
    expected_regular: int = 147,
    expected_referral: int = 86,
) -> dict:
    rows, file_hash = _read_csv(source)
    regular = [row for row in rows if row["branch_type"] == "常规网点" and row["include_regular"] == 1]
    referral = [row for row in rows if row["branch_type"] == "转介绍网点" and row["include_regular"] == 0]
    if len(regular) != expected_regular or len(referral) != expected_referral:
        raise ValueError(
            f"网点数量与确认口径不一致：常规{len(regular)}（应为{expected_regular}），"
            f"转介绍{len(referral)}（应为{expected_referral}）"
        )
    if len(rows) != len(regular) + len(referral):
        raise ValueError("网点参考表存在未识别类型或纳入口径冲突")
    if len({row["reference_id"] for row in rows}) != len(rows):
        raise ValueError("网点参考表存在重复参考编号")
    if len({row["branch_name"] for row in rows}) != len(rows):
        raise ValueError("网点参考表存在重复证券网点名称")

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            batch = conn.execute(
                """
                INSERT INTO branch_reference_batches
                    (file_name, file_hash, regular_count, referral_count, imported_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source.name, file_hash, len(regular), len(referral), imported_by),
            ).lastrowid
            conn.execute("DELETE FROM branch_reference")
            conn.executemany(
                """
                INSERT INTO branch_reference (
                    reference_id, batch_id, branch_type, branch_name, parent_name,
                    province, city, grade, project, subproject, locality,
                    include_in_regular_count, source_row
                ) VALUES (
                    :reference_id, :batch_id, :branch_type, :branch_name, :parent_name,
                    :province, :city, :grade, :project, :subproject, :locality,
                    :include_regular, :source_row
                )
                """,
                [{**row, "batch_id": batch} for row in rows],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {
        "batchId": batch,
        "fileName": source.name,
        "fileHash": file_hash,
        "regularCount": len(regular),
        "referralCount": len(referral),
        "totalCount": len(rows),
    }


def read_reference(conn) -> tuple[list[dict], dict | None]:
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT reference_id, branch_type, branch_name, parent_name, province,
                   city, grade, project, subproject, locality,
                   include_in_regular_count, source_row
            FROM branch_reference
            ORDER BY include_in_regular_count DESC, source_row, reference_id
            """
        ).fetchall()
    ]
    batch_row = conn.execute(
        """
        SELECT id, file_name, file_hash, regular_count, referral_count,
               imported_by, imported_at
        FROM branch_reference_batches
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    batch = None
    if batch_row:
        batch = {
            "id": batch_row["id"],
            "fileName": batch_row["file_name"],
            "fileHash": batch_row["file_hash"],
            "regularCount": batch_row["regular_count"],
            "referralCount": batch_row["referral_count"],
            "importedBy": batch_row["imported_by"],
            "importedAt": batch_row["imported_at"],
        }
    return rows, batch
