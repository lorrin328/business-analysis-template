"""Excel file parsers - one function per Excel type."""
import pandas as pd
from etl.columns import _read_excel


def parse_performance_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'业务模式', '期交保费'})


def parse_jingdai_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'时间', '承保年化规保', '期交保费'})


def parse_hr_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'业务模式名称', '统计日期'})


def parse_value_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'业务模式名称', '价值'})
