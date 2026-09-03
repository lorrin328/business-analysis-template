"""Read-only upload preview. Never returns business row values or opens a database."""
from __future__ import annotations

import hashlib
import json

import pandas as pd

from etl.parser import parse_hr_excel, parse_jingdai_excel, parse_performance_excel, parse_value_excel
from etl.columns import _pick_col
from etl.normalize import _period_year_month
from services.excel_pipeline import ExcelSource
from services.import_safety import (
    IMPORT_MODES, RawIncrementalWriteError, extract_raw_periods, prepare_supplement,
    raw_period_config, raw_periods_predicate, table_columns, validate_replacement_fields,
)
from services.raw_table_reader import quote_identifier


SOURCE_TYPES = {
    "performance": ("转型业务清单", "performance", parse_performance_excel, {"业务模式", "期交保费"}),
    "jingdai": ("经代业务清单", "jingdai", parse_jingdai_excel, {"时间", "承保年化规保", "期交保费"}),
    "hr": ("转型队伍清单", "hr_data", parse_hr_excel, {"业务模式名称", "统计日期", "月初在职人力", "月末在职人力"}),
    "value": ("价值清单", "value_data", parse_value_excel, {"业务模式名称", "价值"}),
}
# Required groups used by the existing import aggregates, including their
# accepted aliases. Detect missing columns before presenting a confirm action.
HEADER_GROUPS = {
    "performance": [("年",), ("年月", "月", "月份"), ("业务模式", "业务模式名称", "渠道"),
                    ("期交保费",), ("缴费年限",), ("人员工号", "人员代码"),
                    ("销售机构名称", "机构", "分公司", "org")],
    "jingdai": [("时间", "年月"), ("期交保费",), ("承保年化规保", "年化规保", "规模保费"), ("缴费年限",)],
    "hr": [("统计年", "年"), ("统计日期", "年月", "统计月", "月"),
           ("业务模式名称", "业务模式", "渠道"), ("月初在职人力",), ("月末在职人力",)],
    "value": [("年月", "时间"), ("业务模式名称", "业务模式", "渠道"), ("价值",)],
}
MODE_LABELS = {"replace_months": "完整月替换", "supplement": "业绩补充"}
MODE_DESCRIPTIONS = {
    "replace_months": "按所选清单中识别出的月份，替换对应来源的整月数据。请确认这些月份的记录与字段完整；未选择的来源和其他月份不变。",
    "supplement": "仅接收转型业务清单，按保单、月份和业务模式补充缺失记录。已有相同记录跳过；已有记录内容冲突则整批停止，不替换整月。",
}


def build_import_manifest(sources: list[ExcelSource], import_mode: str = "replace_months", force: bool = False) -> str:
    """Bind confirmation to every selected byte sequence, source slot and option."""
    files = sorted([
        {"kind": source.kind, "filename": source.filename, "size": len(source.content),
         "sha256": hashlib.sha256(source.content).hexdigest()}
        for source in sources
    ], key=lambda item: (item["kind"], item["filename"], item["sha256"]))
    payload = {"version": 1, "mode": import_mode, "force": bool(force), "files": files}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _existing_rows(conn, table, periods):
    columns = table_columns(conn, table)
    if not columns:
        return 0
    config = raw_period_config(table, pd.DataFrame(columns=sorted(columns)))
    where, params = raw_periods_predicate(periods, config)
    return conn.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(table)} WHERE {where}", params,
    ).fetchone()[0]


def build_import_preview(conn, sources: list[ExcelSource], *, import_mode: str = "replace_months", force: bool = False) -> dict:
    """Parse selected workbooks and inspect affected periods using a read-only connection.

    The caller enforces upload size and permissions. No schema setup, configuration
    extraction, import logging or aggregate writes occur here. Validation is repeated
    during the actual write because source data may change after a preview.
    """
    result = {
        "canImport": False, "importMode": import_mode,
        "modeLabel": MODE_LABELS.get(import_mode, "未知模式"),
        "modeDescription": MODE_DESCRIPTIONS.get(import_mode, ""),
        "manifestHash": build_import_manifest(sources, import_mode, force),
        "files": [], "warnings": [], "errors": [], "dataYears": [],
    }
    if import_mode not in IMPORT_MODES:
        result["errors"].append("请选择完整月替换或业绩补充模式。")
        return result
    if not sources:
        result["errors"].append("请先选择需要导入的 Excel 清单。")
        return result
    if import_mode == "supplement" and any(source.kind != "performance" for source in sources):
        result["errors"].append("业绩补充模式仅允许转型业务清单；其他清单请使用完整月替换。")
        return result
    if len({source.kind for source in sources}) != len(sources):
        result["errors"].append("每种清单只能选择一个文件。")
        return result

    all_years = set()
    has_imports = bool(table_columns(conn, "data_imports"))
    for source in sources:
        if source.kind not in SOURCE_TYPES:
            result["errors"].append("不支持的清单类型。")
            continue
        label, table, parser, required = SOURCE_TYPES[source.kind]
        entry = {"kind": source.kind, "label": label, "fileName": source.filename,
                 "sizeBytes": len(source.content), "rowCount": None, "periods": [],
                 "existingRows": None, "writeRows": None, "coverageLabel": "尚未完成校验",
                 "duplicateSkipped": False}
        result["files"].append(entry)
        try:
            frame = parser(source.content)
            entry["rowCount"] = len(frame)
            entry["ignoredSummaryRows"] = int(frame.attrs.get("ignored_summary_rows", 0))
            if entry["ignoredSummaryRows"]:
                result["warnings"].append(f"{label}末尾的 {entry['ignoredSummaryRows']} 行合计已识别，不计入业务明细和导入行数。")
            missing = [group[0] for group in HEADER_GROUPS[source.kind] if not _pick_col(frame, list(group))]
            if missing:
                raise RawIncrementalWriteError(f"{label}缺少必要表头：{'、'.join(missing)}。请确认文件放在正确的清单位置，并补齐统计年月及业务字段。")
            periods, config = extract_raw_periods(table, frame)
            year_col, month_col, date_col = config
            valid = _period_year_month(frame, year_col, month_col if not date_col else None, date_col)
            if not periods or len(valid) != len(frame) or any(not 2000 <= year <= 2100 for year, _ in periods):
                raise RawIncrementalWriteError(f"{label}存在空数据或无法识别的统计年月，请补齐有效期间后重新预览。")
            entry["periods"] = [f"{year:04d}-{month:02d}" for year, month in sorted(periods)]
            all_years.update(year for year, _ in periods)
            entry["existingRows"] = _existing_rows(conn, table, periods)
            duplicate = bool(has_imports and not force and conn.execute(
                "SELECT 1 FROM data_imports WHERE file_hash=? AND status='success' LIMIT 1",
                (hashlib.sha256(source.content).hexdigest(),),
            ).fetchone())
            entry["duplicateSkipped"] = duplicate
            if duplicate:
                entry["writeRows"] = 0
                entry["coverageLabel"] = "文件与历史成功导入相同，本次跳过"
            elif import_mode == "supplement":
                entry["writeRows"] = len(prepare_supplement(conn, table, frame))
                entry["coverageLabel"] = f"预计新增 {entry['writeRows']} 行；已有相同记录跳过，保留整月原记录"
            else:
                validate_replacement_fields(conn, table, frame)
                entry["writeRows"] = len(frame)
                entry["coverageLabel"] = f"替换上述 {len(periods)} 个月的 {entry['existingRows']} 行，写入 {len(frame)} 行"
        except RawIncrementalWriteError as exc:
            result["errors"].append(str(exc))
            entry["coverageLabel"] = "校验未通过，不会导入"
        except Exception:
            # Parser errors may contain cells or column values. Never echo them.
            result["errors"].append(f"{label}无法完成预览，请确认 Excel 格式、表头与期间字段；当前数据未改变。")
            entry["coverageLabel"] = "校验未通过，不会导入"

    result["dataYears"] = sorted(all_years)
    result["canImport"] = bool(result["files"]) and not result["errors"]
    result["warnings"].append("预览不会写入数据。确认导入时将再次校验；预览后如文件、模式或强制重写选项改变，须重新预览。")
    if force:
        result["warnings"].append("已开启强制重写：文件相同也会按当前模式处理，字段缺失和记录冲突校验仍然生效。")
    if result["canImport"] and all(entry["duplicateSkipped"] for entry in result["files"]):
        result["warnings"].append("所选文件均与历史成功导入相同，本次确认不会写入数据。")
    return result
