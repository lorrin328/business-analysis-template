"""Helpers for explicit raw table reads.

Raw Excel tables have Chinese column names that can change by source file. These
helpers keep direct reads defensive and avoid unbounded SELECT * usage in API
paths while preserving the original column names required by ETL functions.
"""
from __future__ import annotations

import pandas as pd


def quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def raw_table_columns(conn, table: str) -> list[str]:
    table_name = quote_identifier(table)
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def raw_table_column_set(conn, table: str) -> set[str]:
    return set(raw_table_columns(conn, table))


def pick_existing_column(conn, table: str, candidates: list[str]) -> str | None:
    columns = raw_table_column_set(conn, table)
    for column in candidates:
        if column in columns:
            return column
    return None


def compact_period_expr(column: str) -> str:
    expr = f"CAST({quote_identifier(column)} AS TEXT)"
    for token in ["-", "/", ".", "年", "月", "日", " ", ":"]:
        expr = f"replace({expr}, '{token}', '')"
    return expr


def append_period_filter(column: str, year: int, months: list[int] | None, params: list) -> str:
    expr = compact_period_expr(column)
    clause = f" AND CAST(substr({expr}, 1, 4) AS INTEGER) = ?"
    params.append(year)
    if months:
        placeholders = ",".join(["?"] * len(months))
        clause += f" AND CAST(substr({expr}, 5, 2) AS INTEGER) IN ({placeholders})"
        params.extend(months)
    return clause


def append_cutoff_filter(column: str, cutoff: tuple[int, int] | None, params: list) -> str:
    if not cutoff:
        return ""
    expr = compact_period_expr(column)
    params.extend([cutoff[0], cutoff[0], cutoff[1]])
    return f"""
      AND (
        CAST(substr({expr}, 5, 2) AS INTEGER) < ?
        OR (
          CAST(substr({expr}, 5, 2) AS INTEGER) = ?
          AND COALESCE(NULLIF(CAST(substr({expr}, 7, 2) AS INTEGER), 0), 31) <= ?
        )
      )
    """


def read_raw_table_dataframe(conn, table: str) -> pd.DataFrame:
    columns = raw_table_columns(conn, table)
    if not columns:
        return pd.DataFrame()
    select_list = ", ".join(quote_identifier(col) for col in columns)
    return pd.read_sql_query(f"SELECT {select_list} FROM {quote_identifier(table)}", conn)


def read_raw_table_rows(conn, table: str):
    columns = raw_table_columns(conn, table)
    if not columns:
        return []
    select_list = ", ".join(quote_identifier(col) for col in columns)
    return conn.execute(f"SELECT {select_list} FROM {quote_identifier(table)}").fetchall()
