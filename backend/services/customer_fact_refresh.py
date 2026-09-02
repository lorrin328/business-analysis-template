"""Transactional, indexed customer fact refresh from authoritative raw records.

Identifiers are never rewritten in source tables. Numeric aliases are candidates
only. Ambiguous keys use exact identifiers across the complete customer pipeline;
unproven short identifiers remain separate unmatched facts, with coverage warnings.
"""
from __future__ import annotations

import re
import logging
from collections.abc import Iterable

from services.raw_table_reader import compact_period_expr, quote_identifier, raw_table_columns

logger = logging.getLogger(__name__)


class CustomerFactRefreshError(ValueError):
    pass


def policy_key(value: object) -> str | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"(?:[0-9]{11,13}|[0-9]{15})", text):
        digits = (text[-13:] if len(text) == 15 else text).lstrip("0")
        if digits:
            return "n:" + digits
    return "r:" + text


def policy_key_sql(expression: str) -> str:
    """SQLite built-ins only; use this exact expression for indexes and queries."""
    text = f"TRIM(CAST({expression} AS TEXT))"
    digits = f"LTRIM(CASE WHEN length({text})=15 THEN substr({text},-13) ELSE {text} END,'0')"
    return (
        f"CASE WHEN {text} IS NULL OR {text}='' THEN NULL "
        f"WHEN length({text}) IN (11,12,13,15) AND {text} NOT GLOB '*[^0-9]*' "
        f"AND {digits}<>'' THEN 'n:'||{digits} ELSE 'r:'||{text} END"
    )


def policy_identity_sql(expression: str, *, ambiguity_table: str = "customer_policy_key_ambiguity") -> str:
    """Comparable identity: retain original identifiers for known ambiguous keys."""
    table = ".".join(quote_identifier(part) for part in ambiguity_table.split("."))
    key = policy_key_sql(expression)
    return (f"CASE WHEN EXISTS (SELECT 1 FROM {table} a WHERE a.policy_key={key}) "
            f"THEN 'r:'||TRIM(CAST({expression} AS TEXT)) ELSE {key} END")


def policy_match_sql(left: str, right: str, *, ambiguity_table: str = "customer_policy_key_ambiguity") -> str:
    """Indexable candidate equality plus exact-only fallback for ambiguous keys."""
    table = ".".join(quote_identifier(part) for part in ambiguity_table.split("."))
    left_key, right_key = policy_key_sql(left), policy_key_sql(right)
    return (f"({left_key}={right_key} AND (CAST({left} AS TEXT)=CAST({right} AS TEXT) "
            f"OR NOT EXISTS (SELECT 1 FROM {table} a WHERE a.policy_key={left_key})))")


def alias_coverage(conn, where_sql: str = "1=1", params=()) -> dict:
    """Aggregate-only warning, with exact matches and unmatched amounts separated."""
    key = policy_key_sql("f.policy_no")
    row = conn.execute(
        f"""SELECT COUNT(DISTINCT a.policy_key), COUNT(*),
                   COALESCE(SUM(f.customer_match=0),0),
                   COALESCE(SUM(CASE WHEN f.customer_match=0 THEN f.qj_premium ELSE 0 END),0),
                   COALESCE(SUM(CASE WHEN f.customer_match=0 THEN ABS(f.qj_premium) ELSE 0 END),0)
            FROM customer_policy_key_ambiguity a
            CROSS JOIN customer_policy_month_fact f ON {key}=a.policy_key
            WHERE {where_sql}""", params,
    ).fetchone()
    groups, facts, unmatched, premium, absolute_premium = row
    return {
        "ambiguousKeys": int(groups), "affectedFactRows": int(facts),
        "unmatchedFactRows": int(unmatched), "unmatchedQjPremium": float(premium),
        "unmatchedAbsoluteQjPremium": float(absolute_premium), "amountUnit": "元",
        "status": "warning" if groups else "ok",
        "message": ("保单编号存在歧义，相关编号仅作原号精确关联；未能精确关联的业绩保留在未关联范围，"
                    "不计入已关联客户的新老客及复购结论。金额与原始记录均保留。") if groups else "",
    }


POLICY_KEY_INDEXES = (
    ("performance", "投保单号", "ix_raw_performance_policy_key"),
    ("customer_policy_snapshot", "policy_no", "ix_customer_snapshot_policy_key"),
    ("customer_policy_month_fact", "policy_no", "ix_customer_fact_policy_key"),
)


def ensure_policy_key_indexes(conn) -> None:
    for table, column, name in POLICY_KEY_INDEXES:
        if column in raw_table_columns(conn, table):
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {quote_identifier(name)} ON {quote_identifier(table)}"
                f"({policy_key_sql(quote_identifier(column))})"
            )


def _selected_keys(conn, keys: Iterable[str] | None) -> int:
    conn.execute("DROP TABLE IF EXISTS temp.customer_refresh_keys")
    conn.execute("CREATE TEMP TABLE customer_refresh_keys(policy_key TEXT PRIMARY KEY)")
    if keys is None:
        conn.execute("INSERT OR IGNORE INTO customer_refresh_keys SELECT policy_key FROM customer_policy_key_ambiguity")
        for table, column in (("performance", "投保单号"), ("customer_policy_month_fact", "policy_no")):
            expression = policy_key_sql(quote_identifier(column))
            conn.execute(
                f"INSERT OR IGNORE INTO customer_refresh_keys SELECT {expression} "
                f"FROM {quote_identifier(table)} WHERE {expression} IS NOT NULL"
            )
    else:
        conn.executemany(
            "INSERT OR IGNORE INTO customer_refresh_keys VALUES (?)",
            ((key,) for key in keys if key),
        )
    return int(conn.execute("SELECT COUNT(*) FROM customer_refresh_keys").fetchone()[0])


def _validate_aliases(conn, columns: set[str]) -> None:
    """Recompute exact-only keys in the same transaction as the facts they govern."""
    conn.execute("DELETE FROM customer_policy_key_ambiguity WHERE policy_key IN (SELECT policy_key FROM customer_refresh_keys)")
    for table, column in (("performance", "投保单号"), ("customer_policy_snapshot", "policy_no")):
        identifier = quote_identifier(column)
        expression = policy_key_sql(identifier)
        collision_count = "COUNT(*)" if table == "customer_policy_snapshot" else f"COUNT(DISTINCT TRIM(CAST({identifier} AS TEXT)))"
        conn.execute(
            f"INSERT OR IGNORE INTO customer_policy_key_ambiguity(policy_key,reason) "
            f"SELECT {expression}, ? FROM {quote_identifier(table)} "
            f"WHERE {expression} IN (SELECT policy_key FROM customer_refresh_keys) "
            f"GROUP BY {expression} HAVING {collision_count}>1",
            ("multiple_raw_identifiers" if table == "performance" else "multiple_snapshot_identifiers",),
        )
    if "投保人id" in columns:
        raw_key = policy_key_sql('p."投保单号"')
        snapshot_key = policy_key_sql("s.policy_no")
        conn.execute(
            f"""INSERT OR IGNORE INTO customer_policy_key_ambiguity(policy_key,reason)
                SELECT DISTINCT {raw_key}, 'alias_customer_conflict' FROM performance p
                JOIN customer_policy_snapshot s ON {snapshot_key}={raw_key}
                WHERE {raw_key} IN (SELECT policy_key FROM customer_refresh_keys)
                  AND TRIM(CAST(p."投保单号" AS TEXT))<>s.policy_no
                  AND TRIM(COALESCE(p."投保人id",''))<>''
                  AND TRIM(p."投保人id")<>s.customer_id"""
        )


def refresh_customer_facts(conn, policy_keys: Iterable[str] | None = None, *, batch_id: int | None = None) -> dict:
    """Refresh selected logical policies (all their months), without committing.

    None selects all raw/fact policies for the one-time migration. Incremental
    callers pass keys from both the pre-write and post-write source scope, so
    deleted/corrected policies cannot leave stale facts behind.
    """
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"performance", "customer_policy_snapshot", "customer_master", "customer_policy_month_fact", "history_import_batches"}
    if not required.issubset(tables):
        return {"refreshedRows": 0, "affectedKeys": 0, "skipped": True}
    if batch_id is None:
        base = conn.execute("SELECT id FROM history_import_batches WHERE status='success' ORDER BY id DESC LIMIT 1").fetchone()
        if not base:
            return {"refreshedRows": 0, "affectedKeys": 0, "skipped": True}
        batch_id = int(base[0])
    columns = set(raw_table_columns(conn, "performance"))
    if not {"投保单号", "业务模式", "期交保费"}.issubset(columns):
        raise CustomerFactRefreshError("客户事实更新缺少业绩保单号、业务模式或期交保费字段，请使用完整业绩源")
    period = next((name for name in ("年月", "年月日", "入账时间") if name in columns), None)
    if not period:
        raise CustomerFactRefreshError("客户事实更新缺少可识别的业绩期间字段")
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("SAVEPOINT customer_fact_refresh")
    try:
        ensure_policy_key_indexes(conn)
        key_count = _selected_keys(conn, policy_keys)
        _validate_aliases(conn, columns)
        def raw(name, default="NULL"):
            return "p." + quote_identifier(name) if name in columns else default
        period_expr = compact_period_expr(period).replace(quote_identifier(period), "p." + quote_identifier(period))
        year = f"CAST(substr({period_expr},1,4) AS INTEGER)"
        month = f"CAST(substr({period_expr},5,2) AS INTEGER)"
        line = "CASE TRIM(p.\"业务模式\") WHEN '证券' THEN '证保' WHEN '网服' THEN '蚁桥' ELSE TRIM(p.\"业务模式\") END"
        raw_key = policy_key_sql('p."投保单号"')
        snapshot_key = policy_key_sql("s.policy_no")
        fact_key = policy_key_sql("policy_no")
        term, pay, product = raw("长短险", "''"), raw("缴费年限", "0"), raw("产品代码", "''")
        conn.execute("DROP TABLE IF EXISTS temp.customer_refresh_rows")
        conn.execute(
            f"""CREATE TEMP TABLE customer_refresh_rows AS
                SELECT {year} year, {month} month,
                       MIN(CAST({raw('年月日')} AS TEXT)) transaction_date, {line} business_line,
                       TRIM(COALESCE({raw('销售机构名称')},'')) org,
                       COALESCE(s.policy_no,TRIM(CAST(p."投保单号" AS TEXT))) policy_no,
                       COALESCE(s.customer_id,MAX(NULLIF(TRIM({raw('投保人id')}),''))) customer_id,
                       s.underwriting_time, m.first_underwriting_time first_customer_underwriting_time,
                       MAX(CASE
                         WHEN TRIM(COALESCE({term},'')) IN ('长期','长险','长期险','长','一年期以上','一年以上','1年期以上') THEN 1
                         WHEN TRIM(COALESCE({term},'')) IN ('短期','极短期','一年期','一年期以下','一年以下','1年期','1年期以下') THEN 0
                         WHEN TRIM(COALESCE({product},'')) IN ('4281','4281.0') THEN 1
                         WHEN TRIM(COALESCE({term},''))='' AND
                           (CAST({pay} AS REAL)>=2 OR CAST({pay} AS TEXT) GLOB '*终身*'
                            OR CAST({pay} AS TEXT) GLOB '*长期*' OR CAST({pay} AS TEXT) GLOB '*永久*') THEN 1 ELSE 0 END) is_longterm,
                       SUM(COALESCE(p."期交保费",0)) qj_premium,
                       SUM(COALESCE({raw('年化规保')},0)) gm_premium,
                       SUM(COALESCE({raw('折算保费')},0)) zs_premium,
                       SUM(COALESCE({raw('价值规保')},0)) value_premium,
                       SUM(COALESCE({raw('承保件数')},0)) accepted_count,
                       s.policy_status, s.termination_reason, COALESCE(s.status_group,'unmatched') status_group,
                       CASE WHEN s.policy_no IS NULL THEN 0 ELSE 1 END customer_match,
                       ? batch_id
                FROM performance p
                LEFT JOIN customer_policy_snapshot s ON {policy_match_sql('s.policy_no', 'p."投保单号"')}
                LEFT JOIN customer_master m ON m.customer_id=COALESCE(s.customer_id,TRIM({raw('投保人id')}))
                    AND (s.policy_no IS NOT NULL OR NOT EXISTS
                        (SELECT 1 FROM customer_policy_key_ambiguity a WHERE a.policy_key={raw_key}))
                WHERE {raw_key} IN (SELECT policy_key FROM customer_refresh_keys)
                  AND {line} IN ('OTO','证保','蚁桥')
                  AND {year} BETWEEN 1900 AND 2100 AND {month} BETWEEN 1 AND 12
                GROUP BY 1,2,4,5,6""", (batch_id,),
        )
        count = int(conn.execute("SELECT COUNT(*) FROM customer_refresh_rows").fetchone()[0])
        fields = [row[1] for row in conn.execute("PRAGMA temp.table_info(customer_refresh_rows)")]
        names = ",".join(quote_identifier(field) for field in fields)
        conn.execute(f"DELETE FROM customer_policy_month_fact WHERE {fact_key} IN (SELECT policy_key FROM customer_refresh_keys)")
        conn.execute(f"INSERT INTO customer_policy_month_fact ({names}) SELECT {names} FROM customer_refresh_rows")
        coverage = alias_coverage(conn, f"{policy_key_sql('f.policy_no')} IN (SELECT policy_key FROM customer_refresh_keys)")
        conn.execute("DROP TABLE customer_refresh_rows")
        conn.execute("DROP TABLE customer_refresh_keys")
        conn.execute("RELEASE SAVEPOINT customer_fact_refresh")
        if coverage["ambiguousKeys"]:
            logger.warning("Customer alias coverage: exact-only keys=%d, unmatched fact rows=%d",
                           coverage["ambiguousKeys"], coverage["unmatchedFactRows"])
        return {"refreshedRows": count, "affectedKeys": key_count, "skipped": False, "aliasCoverage": coverage}
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT customer_fact_refresh")
        conn.execute("RELEASE SAVEPOINT customer_fact_refresh")
        raise
