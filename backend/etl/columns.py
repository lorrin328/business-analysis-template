"""Column detection and Excel reading utilities."""
import io
from typing import List

import pandas as pd


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith('Unnamed:')]]
    return df


def _find_header_row(file_bytes: bytes, required_cols: set[str], max_rows: int = 40) -> int:
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=max_rows)
    for i in range(len(raw)):
        row_vals = {str(v).strip() for v in raw.iloc[i].values if pd.notna(v)}
        if required_cols.issubset(row_vals):
            return i
    return 0


def _read_excel(file_bytes: bytes, required_cols: set[str]) -> pd.DataFrame:
    header_row = _find_header_row(file_bytes, required_cols)
    df = pd.read_excel(io.BytesIO(file_bytes), header=header_row)
    return _clean_columns(df)


def _pick_col(df: pd.DataFrame, candidates: List[str], contains: List[str] | None = None) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    if contains:
        for col in df.columns:
            if any(token in col for token in contains):
                return col
    return None
