from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


@dataclass(frozen=True)
class Cell:
    value: object | None
    formula: str | None = None
    data_type: str | None = None


def column_number(label: str) -> int:
    number = 0
    for ch in label.upper():
        number = number * 26 + ord(ch) - 64
    return number


def split_cell_ref(ref: str) -> tuple[int, int]:
    match = CELL_REF_RE.match(ref.upper())
    if not match:
        raise ValueError(f"无效单元格坐标：{ref}")
    return int(match.group(2)), column_number(match.group(1))


class CachedXlsx:
    """Read cached XLSX values without evaluating formulas or loading pivot caches."""

    MAX_ENTRIES = 5000
    MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
    # Pivot cache records can legitimately compress above 200:1 in finance workbooks.
    MAX_COMPRESSION_RATIO = 500

    def __init__(self, content: bytes):
        self._content = content
        self._sheets: dict[str, str] = {}
        self._shared_strings: list[str] = []
        self._sheet_cache: dict[str, dict[tuple[int, int], Cell]] = {}
        self._validate_and_index()

    @property
    def sheet_names(self) -> list[str]:
        return list(self._sheets)

    def _open(self) -> zipfile.ZipFile:
        return zipfile.ZipFile(BytesIO(self._content))

    def _validate_and_index(self) -> None:
        if not zipfile.is_zipfile(BytesIO(self._content)):
            raise ValueError("文件不是有效的 XLSX 压缩包")
        with self._open() as archive:
            infos = archive.infolist()
            if len(infos) > self.MAX_ENTRIES:
                raise ValueError("工作簿内部文件数量异常")
            total_size = sum(item.file_size for item in infos)
            if total_size > self.MAX_UNCOMPRESSED_BYTES:
                raise ValueError("工作簿解压后体积超过安全限制")
            for item in infos:
                if item.compress_size and item.file_size / item.compress_size > self.MAX_COMPRESSION_RATIO:
                    raise ValueError("工作簿压缩比异常")

            names = set(archive.namelist())
            required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(names):
                raise ValueError("工作簿缺少必要结构")

            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                self._shared_strings = [
                    "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
                    for item in root.findall(f"{{{MAIN_NS}}}si")
                ]

            rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rels = {
                node.attrib["Id"]: node.attrib["Target"]
                for node in rel_root.findall(f"{{{PKG_REL_NS}}}Relationship")
                if node.attrib.get("Id") and node.attrib.get("Target")
            }
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
            sheets_node = workbook_root.find(f"{{{MAIN_NS}}}sheets")
            if sheets_node is None:
                raise ValueError("工作簿没有工作表")
            for sheet in sheets_node.findall(f"{{{MAIN_NS}}}sheet"):
                name = sheet.attrib.get("name")
                rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
                target = rels.get(rel_id or "")
                if not name or not target:
                    continue
                clean_target = target.lstrip("/")
                normalized = posixpath.normpath(
                    clean_target if clean_target.startswith("xl/") else posixpath.join("xl", clean_target)
                )
                if normalized.startswith("../") or normalized not in names:
                    raise ValueError(f"工作表结构异常：{name}")
                self._sheets[name] = normalized

    def _load_sheet(self, sheet_name: str) -> dict[tuple[int, int], Cell]:
        if sheet_name in self._sheet_cache:
            return self._sheet_cache[sheet_name]
        sheet_path = self._sheets.get(sheet_name)
        if not sheet_path:
            raise KeyError(f"缺少工作表：{sheet_name}")
        cells: dict[tuple[int, int], Cell] = {}
        with self._open() as archive:
            root = ET.fromstring(archive.read(sheet_path))
        for cell_node in root.iter(f"{{{MAIN_NS}}}c"):
            ref = cell_node.attrib.get("r")
            if not ref:
                continue
            row, col = split_cell_ref(ref)
            data_type = cell_node.attrib.get("t")
            formula_node = cell_node.find(f"{{{MAIN_NS}}}f")
            value_node = cell_node.find(f"{{{MAIN_NS}}}v")
            inline_node = cell_node.find(f"{{{MAIN_NS}}}is")
            formula = formula_node.text if formula_node is not None else None
            raw = value_node.text if value_node is not None else None
            value: object | None
            if data_type == "inlineStr":
                value = "".join(node.text or "" for node in inline_node.iter(f"{{{MAIN_NS}}}t")) if inline_node is not None else ""
            elif data_type == "s" and raw is not None:
                idx = int(raw)
                value = self._shared_strings[idx] if 0 <= idx < len(self._shared_strings) else None
            elif data_type == "b":
                value = raw == "1"
            elif data_type in {"str", "e"}:
                value = raw
            elif raw in (None, ""):
                value = None
            else:
                try:
                    value = float(raw)
                except ValueError:
                    value = raw
            cells[(row, col)] = Cell(value=value, formula=formula, data_type=data_type)
        self._sheet_cache[sheet_name] = cells
        return cells

    def cell(self, sheet_name: str, ref: str) -> Cell:
        return self._load_sheet(sheet_name).get(split_cell_ref(ref), Cell(None))

    def value(self, sheet_name: str, ref: str) -> object | None:
        return self.cell(sheet_name, ref).value

    def rows(self, sheet_name: str, start_row: int = 1) -> list[dict[int, Cell]]:
        rows: dict[int, dict[int, Cell]] = {}
        for (row, col), cell in self._load_sheet(sheet_name).items():
            if row >= start_row:
                rows.setdefault(row, {})[col] = cell
        return [rows[row] for row in sorted(rows)]
