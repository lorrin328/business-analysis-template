"""Excel file parsers - one function per Excel type."""
import pandas as pd
from etl.columns import _read_excel


def parse_performance_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'业务模式', '期交保费'})


def parse_jingdai_excel(file_bytes: bytes) -> pd.DataFrame:
    frame = _read_excel(file_bytes, {'时间', '承保年化规保', '期交保费'})
    # The standard export ends with a grand total in the time column. It is not
    # a transaction and must neither invalidate the preview nor enter raw data.
    # Only recognize explicit trailing totals with no business dimensions.
    period = next((name for name in ('时间', '年月') if name in frame.columns), None)
    amount_columns = {'承保年化规保', '年化规保', '规模保费', '期交保费'}
    labels = {'合计', '总计', 'total', 'grand total'}
    end, ignored = len(frame), 0
    while period and end:
        row = frame.iloc[end - 1]
        if row.isna().all():
            end -= 1
            continue
        label = str(row[period]).strip().lower()
        dimensions = [c for c in frame.columns if c != period and c not in amount_columns]
        if label not in labels or any(pd.notna(row[c]) and str(row[c]).strip() for c in dimensions):
            break
        end -= 1
        ignored += 1
    result = frame.iloc[:end].copy()
    result.attrs['ignored_summary_rows'] = ignored
    return result


def parse_hr_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'业务模式名称', '统计日期', '月初在职人力', '月末在职人力'})


def parse_value_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'业务模式名称', '价值'})
