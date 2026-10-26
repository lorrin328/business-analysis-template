"""Read the policy-level Jingdai export without materializing Excel cell objects.

Only explicit vertical merge ranges are restored. A blank transaction cell is
never filled from an unrelated preceding transaction.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import io
import posixpath
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile

import pandas as pd


_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
_NEW_HEADER = {'统计时间_年月日', '销售平台', '投保单号', '期交保费', '年化规保'}
_SUMMARY = {'小计', '合计', '总计', 'subtotal', 'total', 'grand total'}
_MERGE = re.compile(rb'<(?:\w+:)?mergeCell\b[^>]*\bref=[\"\x27]([^\"\x27]+)[\"\x27]')
_CELL = re.compile(r'([A-Za-z]+)(\d+)$')


class _LegacySheet(Exception):
    pass


def _column_number(text: str) -> int:
    value = 0
    for char in text.upper():
        value = value * 26 + ord(char) - 64
    return value


def _tag(name: str) -> str:
    return name.rsplit(':', 1)[-1]


def _shared_strings(archive, names) -> list[str]:
    if 'xl/sharedStrings.xml' not in names:
        return []
    result, pieces = [], []
    in_text = False
    parser = expat.ParserCreate()

    def start(name, attrs):
        nonlocal in_text
        if _tag(name) == 'si':
            pieces.clear()
        elif _tag(name) == 't':
            in_text = True

    def end(name):
        nonlocal in_text
        if _tag(name) == 't':
            in_text = False
        elif _tag(name) == 'si':
            result.append(''.join(pieces))

    def chars(value):
        if in_text:
            pieces.append(value)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    with archive.open(names['xl/sharedStrings.xml']) as stream:
        parser.ParseFile(stream)
    return result


def _sheet_metadata(archive, sheet_name) -> dict[int, list[tuple[int, int]]]:
    """Merge definitions follow sheetData; scan compressed XML with bounded memory."""
    ranges: dict[int, list[tuple[int, int]]] = {}
    seen = set()
    tail = b''
    with archive.open(sheet_name) as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            block = tail + chunk
            for match in _MERGE.finditer(block):
                ref = match[1]
                if ref in seen:
                    continue
                seen.add(ref)
                parts = ref.decode('ascii').split(':')
                if len(parts) != 2:
                    continue
                left, right = (_CELL.fullmatch(part) for part in parts)
                if left and right and left[1] == right[1]:
                    ranges.setdefault(_column_number(left[1]), []).append((int(left[2]), int(right[2])))
            tail = block[-1024:]
    for values in ranges.values():
        values.sort()
    return ranges


def _date_text(value, epoch: datetime, cache: dict):
    if value is None or pd.isna(value):
        return None
    if value in cache:
        return cache[value]
    text = str(value).strip()
    result = text
    try:
        number = float(text)
        if 1 <= number <= 100000:
            result = (epoch + timedelta(days=number)).strftime('%Y-%m-%d')
        elif re.fullmatch(r'\d{8}', text):
            result = datetime.strptime(text, '%Y%m%d').strftime('%Y-%m-%d')
    except (ValueError, TypeError, OverflowError):
        pass
    cache[value] = result
    return result


def read_policy_detail(file_bytes: bytes) -> pd.DataFrame | None:
    """Return canonical policy detail, or None for the older aggregate export."""
    if not file_bytes.startswith(b'PK'):
        return None
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        names = {name.replace('\\', '/'): name for name in archive.namelist()}
        workbook = ET.fromstring(archive.read(names['xl/workbook.xml']))
        sheet = workbook.find(_NS + 'sheets')[0]
        relationships = ET.fromstring(archive.read(names['xl/_rels/workbook.xml.rels']))
        rel = next(item for item in relationships if item.get('Id') == sheet.get(_REL))
        if rel.get('TargetMode') == 'External':
            raise ValueError('经代工作表引用格式不受支持。')
        target = rel.get('Target', '').replace('\\', '/')
        target = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
        sheet_name = names[target]
        date1904 = workbook.find(_NS + 'workbookPr')
        epoch = datetime(1904, 1, 1) if date1904 is not None and date1904.get('date1904') in {'1', 'true'} else datetime(1899, 12, 30)
        strings = _shared_strings(archive, names)
        merges = _sheet_metadata(archive, sheet_name)
        positions = {col: 0 for col in merges}
        anchors = {}
        header = None
        columns = {}
        data = {}
        row_number = 0
        row = {}
        cell_column = 0
        cell_type = ''
        cell_parts = []
        in_value = False
        source_rows = ignored = filled = 0
        parser = expat.ParserCreate()

        def start(name, attrs):
            nonlocal row_number, row, cell_column, cell_type, in_value
            name = _tag(name)
            if name == 'row':
                row_number = int(attrs.get('r', row_number + 1))
                row = {}
            elif name == 'c':
                cell_column = _column_number(re.sub(r'\d', '', attrs.get('r', '')))
                cell_type = attrs.get('t', '')
                cell_parts.clear()
            elif name in {'v', 't'}:
                in_value = True

        def chars(value):
            if in_value:
                cell_parts.append(value)

        def end(name):
            nonlocal header, columns, data, in_value, source_rows, ignored, filled
            name = _tag(name)
            if name in {'v', 't'}:
                in_value = False
            elif name == 'c':
                value = ''.join(cell_parts) if cell_parts else None
                if cell_type == 's' and value is not None:
                    value = strings[int(value)]
                row[cell_column] = value
            elif name == 'row':
                if header is None:
                    values = {str(value).strip() for value in row.values() if value is not None}
                    if _NEW_HEADER.issubset(values):
                        header = {col: str(value).strip() for col, value in row.items() if value is not None}
                        if len(set(header.values())) != len(header):
                            raise ValueError('经代基表存在重复表头，请核对后导入。')
                        columns = {value: col for col, value in header.items()}
                        data = {name: [] for name in header.values()}
                    elif row_number >= 40:
                        raise _LegacySheet()
                    return
                if not any(value is not None and str(value).strip() for value in row.values()):
                    return
                source_rows += 1
                for col, ranges in merges.items():
                    index = positions[col]
                    while index < len(ranges) and ranges[index][1] < row_number:
                        index += 1
                    positions[col] = index
                    if index == len(ranges):
                        continue
                    first, last = ranges[index]
                    if row_number == first:
                        anchors[col] = row.get(col)
                    elif first < row_number <= last and row.get(col) is None:
                        row[col] = anchors.get(col)
                        filled += row[col] is not None
                platform = str(row.get(columns['销售平台']) or '').strip().lower()
                period = str(row.get(columns['统计时间_年月日']) or '').strip().lower()
                # Summary rows carry no policy/product identity. Do not drop a
                # real transaction merely because a label happens to match.
                no_identity = not any(row.get(columns.get(key)) for key in ('投保单号', '产品代码', '产品名称'))
                if no_identity and (platform in _SUMMARY or period in _SUMMARY):
                    ignored += 1
                    return
                for col, label in header.items():
                    value = row.get(col)
                    if label in {'期交保费', '年化规保'} and value is not None:
                        try:
                            value = float(value)
                        except (TypeError, ValueError):
                            pass  # Shared numeric validation reports only safe counts.
                    data[label].append(value)

        parser.StartElementHandler = start
        parser.EndElementHandler = end
        parser.CharacterDataHandler = chars
        try:
            with archive.open(sheet_name) as stream:
                parser.ParseFile(stream)
        except _LegacySheet:
            return None
        if header is None:
            return None
    frame = pd.DataFrame(data, dtype=object)
    cache = {}
    frame['时间'] = frame['统计时间_年月日'].map(lambda value: _date_text(value, epoch, cache))
    frame['经代机构'] = frame['销售平台']
    frame['承保年化规保'] = frame['年化规保']
    frame['经代源格式'] = 'policy_detail'
    # Force IDs to remain text, including leading zeroes in shared strings.
    frame['投保单号'] = frame['投保单号'].map(lambda value: str(value).strip() if pd.notna(value) else None)
    warnings = []
    if source_rows >= 1_000_000:
        warnings.append('经代源达到100万行，可能为截断导出；本文件覆盖不代表完整月份或全年。')
    frame.attrs.update(
        source_format='jingdai_policy_detail', ignored_summary_rows=ignored,
        source_record_count=source_rows - ignored, source_capped=source_rows >= 1_000_000,
        source_warnings=warnings, restored_merge_cells=filled,
    )
    from etl.jingdai_contract import normalize_jingdai_source
    return normalize_jingdai_source(frame, source_format='policy_detail')
