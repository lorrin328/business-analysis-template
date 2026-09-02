import sqlite3

import pandas as pd
import pytest

from services.customer_fact_refresh import (
    CustomerFactRefreshError, ensure_policy_key_indexes, policy_key, policy_key_sql, policy_match_sql, refresh_customer_facts,
)
from services.import_safety import RawIncrementalWriteError, write_raw_table_incremental
from services.excel_pipeline import ExcelPipelineResult, write_excel_pipeline_result
from services.aggregate_rebuilder import build_aggregate_rows_from_raw


def _row(policy="0012345678901", amount=10000, **changes):
    row = {"年": 2026, "年月": "2026-08", "年月日": "2026-08-10", "业务模式": "OTO",
           "销售机构名称": "上海", "投保单号": policy, "投保人id": "C-1", "期交保费": amount,
           "年化规保": amount, "折算保费": amount, "承保件数": 1, "长短险": "长期",
           "缴费年限": 5, "是否职拓": "是", "产品代码": "TEST", "产品名称": "合成测试产品",
           "产品类型": "年金", "人员工号": "TEST-1"}
    row.update(changes)
    return row


def _seed(conn, rows=None, snapshot="880012345678901"):
    conn.execute("DROP TABLE performance")
    pd.DataFrame(rows or [_row()]).to_sql("performance", conn, index=False)
    batch = conn.execute("""INSERT INTO history_import_batches
        (source_directory,status,source_cutoff) VALUES ('synthetic','success','2026-08-31')""").lastrowid
    conn.execute("""INSERT INTO customer_policy_snapshot
        (policy_no,customer_id,underwriting_time,policy_status,status_group,batch_id)
        VALUES (?,'C-1','2026-08-10','有效','active',?)""", (snapshot, batch))
    conn.execute("""INSERT INTO customer_master
        (customer_id,first_underwriting_time,first_policy_no,batch_id)
        VALUES ('C-1','2026-08-10',?,?)""", (snapshot, batch))
    conn.commit()
    ensure_policy_key_indexes(conn)
    return batch


@pytest.mark.parametrize("raw,expected", [
    ("0012345678901", "n:12345678901"), ("12345678901", "n:12345678901"),
    ("880012345678901", "n:12345678901"), ("12345678901234", "r:12345678901234"),
    ("12345678901.0", "r:12345678901.0"), ("P-TEST", "r:P-TEST"), ("", None),
    ("0000000000000", "r:0000000000000"), ("１２３４５６７８９０１", "r:１２３４５６７８９０１"),
])
def test_policy_key_strict_format_matches_sql(raw, expected):
    with sqlite3.connect(":memory:") as conn:
        assert policy_key(raw) == expected
        assert conn.execute("SELECT " + policy_key_sql("?"), [raw] * policy_key_sql("?").count("?")).fetchone()[0] == expected


def test_customer_facts_map_alias_preserve_sources_and_use_indexes(auth_db):
    from db.connection import get_db
    from customer_analysis.repository import _raw_product_profile_sql
    with get_db() as conn:
        _seed(conn)
        raw_before = tuple(conn.execute("SELECT * FROM performance").fetchone())
        result = refresh_customer_facts(conn, [policy_key("0012345678901")])
        assert result["refreshedRows"] == 1
        fact = conn.execute("SELECT * FROM customer_policy_month_fact").fetchone()
        assert (fact["policy_no"], fact["customer_match"], fact["qj_premium"]) == ("880012345678901", 1, 10000)
        assert tuple(conn.execute("SELECT * FROM performance").fetchone()) == raw_before
        profile = conn.execute("WITH policy_keys AS (SELECT policy_no FROM customer_policy_month_fact), " +
                               _raw_product_profile_sql(conn) + " SELECT product_name FROM product_profile").fetchone()[0]
        assert profile == "合成测试产品"
        plan = conn.execute("EXPLAIN QUERY PLAN SELECT * FROM performance WHERE " + policy_key_sql('"投保单号"') + "=?", (policy_key("0012345678901"),)).fetchall()
        assert any("ix_raw_performance_policy_key" in str(tuple(row)) for row in plan)


@pytest.mark.parametrize("collision_source", ["snapshot", "raw", "identity"])
def test_existing_alias_collision_preserves_exact_facts_and_warns_without_identifiers(auth_db, collision_source):
    from db.connection import get_db
    with get_db() as conn:
        batch = _seed(conn)
        refresh_customer_facts(conn)
        conn.commit()
        if collision_source == "snapshot":
            conn.execute("""INSERT INTO customer_policy_snapshot
                (policy_no,customer_id,underwriting_time,policy_status,status_group,batch_id)
                VALUES ('990012345678901','C-1','2026-08-10','有效','active',?)""", (batch,))
        elif collision_source == "raw":
            conn.execute('UPDATE performance SET "投保单号"=\'880012345678901\'')
            from services.import_safety import append_raw_frame
            append_raw_frame(conn, "performance", pd.DataFrame([_row()]))
        else:
            conn.execute('UPDATE performance SET "投保人id"=\'C-OTHER\'')
        raw_before = [tuple(row) for row in conn.execute("SELECT * FROM performance")]
        result = refresh_customer_facts(conn)
        assert "12345678901" not in str(result)
        assert result["aliasCoverage"]["ambiguousKeys"] == 1
        assert result["aliasCoverage"]["unmatchedFactRows"] == 1
        assert conn.execute("SELECT COUNT(*) FROM customer_policy_key_ambiguity").fetchone()[0] == 1
        assert conn.execute("SELECT SUM(qj_premium) FROM customer_policy_month_fact").fetchone()[0] == sum(row[0] for row in conn.execute('SELECT "期交保费" FROM performance'))
        assert [tuple(row) for row in conn.execute("SELECT * FROM performance")] == raw_before
        short = conn.execute("SELECT * FROM customer_policy_month_fact WHERE policy_no='0012345678901'").fetchone()
        assert short["customer_match"] == 0
        assert short["status_group"] == "unmatched"
        assert short["first_customer_underwriting_time"] is None


def test_customer_refresh_amount_correction_removed_policy_and_idempotence(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        _seed(conn)
        key = policy_key("0012345678901")
        refresh_customer_facts(conn, [key])
        conn.execute('UPDATE performance SET "期交保费"=-500')
        refresh_customer_facts(conn, [key])
        refresh_customer_facts(conn, [key])
        assert tuple(conn.execute("SELECT COUNT(*),SUM(qj_premium) FROM customer_policy_month_fact").fetchone()) == (1, -500)
        conn.execute("DELETE FROM performance")
        refresh_customer_facts(conn, [key])
        assert conn.execute("SELECT COUNT(*) FROM customer_policy_month_fact").fetchone()[0] == 0


def test_ambiguous_short_without_customer_stays_unmatched_and_product_profile_is_exact(auth_db):
    from db.connection import get_db
    from customer_analysis.repository import _raw_product_profile_sql, get_customer_analysis
    rows = [
        _row(policy="880012345678901", amount=10000, 年=2023, 年月="2023-08", 年月日="2023-08-10", 产品名称="完整号产品"),
        _row(amount=20000, 投保人id=None, 产品名称="短号产品"),
        _row(amount=-500, 投保人id=None, 产品名称="短号产品"),
    ]
    with get_db() as conn:
        _seed(conn, rows)
        raw_before = [tuple(row) for row in conn.execute("SELECT * FROM performance")]
        result = refresh_customer_facts(conn)
        conn.commit()
        result_again = refresh_customer_facts(conn)
        conn.commit()
        assert result_again == result
        facts = {row["policy_no"]: dict(row) for row in conn.execute("SELECT * FROM customer_policy_month_fact")}
        assert facts["880012345678901"]["customer_match"] == 1
        assert facts["0012345678901"]["customer_match"] == 0
        assert facts["0012345678901"]["customer_id"] is None
        assert facts["0012345678901"]["qj_premium"] == 19500
        assert sum(row["qj_premium"] for row in facts.values()) == 29500
        assert [tuple(row) for row in conn.execute("SELECT * FROM performance")] == raw_before
        products = dict(conn.execute("WITH policy_keys AS (SELECT DISTINCT policy_no FROM customer_policy_month_fact), " +
                                    _raw_product_profile_sql(conn) + " SELECT policy_no,product_name FROM product_profile"))
        assert products == {"880012345678901": "完整号产品", "0012345678901": "短号产品"}
        assert result["aliasCoverage"]["unmatchedQjPremium"] == 19500
        assert result["aliasCoverage"]["unmatchedFactRows"] == 1
    analysis = get_customer_analysis(year=2026)
    assert analysis["summary"]["qjPremiumWan"] == 1.95
    assert analysis["summary"]["matchedPolicies"] == 0
    assert analysis["quality"]["aliasCoverage"]["status"] == "warning"
    assert analysis["quality"]["aliasCoverage"]["unmatchedQjPremium"] == 19500


def test_ambiguity_registry_and_facts_rollback_together(auth_db):
    from db.connection import get_db
    from services.import_safety import append_raw_frame
    with get_db() as conn:
        _seed(conn)
        refresh_customer_facts(conn)
        conn.commit()
        facts_before = [tuple(row) for row in conn.execute("SELECT * FROM customer_policy_month_fact")]
        append_raw_frame(conn, "performance", pd.DataFrame([_row(policy="880012345678901")]))
        conn.commit()
        conn.execute("""CREATE TRIGGER fail_fact_insert BEFORE INSERT ON customer_policy_month_fact
                     BEGIN SELECT RAISE(ABORT,'synthetic fact failure'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="synthetic fact failure"):
            refresh_customer_facts(conn)
        assert conn.execute("SELECT COUNT(*) FROM customer_policy_key_ambiguity").fetchone()[0] == 0
        assert [tuple(row) for row in conn.execute("SELECT * FROM customer_policy_month_fact")] == facts_before


def test_history_reconciliation_does_not_merge_ambiguous_original_identifiers(auth_db):
    from db.connection import get_db
    from history_import.importer import FullHistoryImporter
    with get_db() as conn:
        rows = [_row(), _row(policy="880012345678901", amount=20000)]
        batch = _seed(conn, rows)
        # No preexisting ambiguity registry: the incoming stage must be checked too.
        pd.DataFrame(rows).to_sql("performance_full_stage", conn, index=False)
        importer = object.__new__(FullHistoryImporter)
        importer.conn = conn
        result = importer._reconcile(batch)
        assert result["matchedPolicies"] == 2
        counts = conn.execute("SELECT existing_policy_count,source_policy_count,matched_policy_count FROM history_reconciliation").fetchone()
        assert tuple(counts) == (2, 2, 2)


def test_shared_match_stays_indexable_and_exact_when_ambiguous(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        _seed(conn, [_row(), _row(policy="880012345678901")])
        refresh_customer_facts(conn)
        sql = "SELECT p.\"投保单号\" FROM customer_policy_snapshot s JOIN performance p ON " + policy_match_sql('p."投保单号"', 's.policy_no')
        assert [row[0] for row in conn.execute(sql)] == ["880012345678901"]
        plan = conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
        assert any("ix_raw_performance_policy_key" in str(tuple(row)) or "ix_customer_snapshot_policy_key" in str(tuple(row)) for row in plan)


@pytest.mark.parametrize("policy,customer", [("990012345678901", "C-1"), ("880012345678901", "C-OTHER"), ("880012345678901", "")])
def test_new_full_customer_source_ambiguity_is_rejected_before_domain_deletion(auth_db, policy, customer):
    from db.connection import get_db
    from history_import.importer import FullHistoryImporter
    with get_db() as conn:
        batch = _seed(conn)
        refresh_customer_facts(conn)
        conn.commit()
        before = [tuple(row) for row in conn.execute("SELECT * FROM customer_policy_snapshot")]
        pd.DataFrame([{"投保单号": "880012345678901", "投保人id": "C-1"},
                      {"投保单号": policy, "投保人id": customer}]).to_sql("customer_source_stage", conn, index=False)
        importer = object.__new__(FullHistoryImporter)
        importer.conn = conn
        with pytest.raises(ValueError, match="新客户源存在模糊"):
            importer._build_customer_domains(batch)
        assert [tuple(row) for row in conn.execute("SELECT * FROM customer_policy_snapshot")] == before
        assert conn.execute("SELECT COUNT(*) FROM customer_policy_month_fact").fetchone()[0] == 1


def test_raw_month_replace_blocks_missing_enabled_flag_and_allows_negative_correction():
    with sqlite3.connect(":memory:") as conn:
        pd.DataFrame([_row()]).to_sql("performance", conn, index=False)
        before = conn.execute("SELECT * FROM performance").fetchall()
        with pytest.raises(RawIncrementalWriteError, match="是否职拓"):
            write_raw_table_incremental(conn, "performance", pd.DataFrame([_row()]).drop(columns="是否职拓"))
        assert conn.execute("SELECT * FROM performance").fetchall() == before
        write_raw_table_incremental(conn, "performance", pd.DataFrame([_row(是否职拓="否")]))
        assert conn.execute('SELECT "是否职拓" FROM performance').fetchone()[0] == "否"
        conn.rollback()
        assert conn.execute("SELECT * FROM performance").fetchall() == before


def test_raw_month_replace_does_not_require_unenabled_field():
    with sqlite3.connect(":memory:") as conn:
        pd.DataFrame([_row(是否职拓=None)]).to_sql("performance", conn, index=False)
        write_raw_table_incremental(conn, "performance", pd.DataFrame([_row()]).drop(columns="是否职拓"))
        assert conn.execute("SELECT COUNT(*) FROM performance").fetchone()[0] == 1


def test_supplement_is_idempotent_preserves_flag_and_rejects_conflicting_group():
    with sqlite3.connect(":memory:") as conn:
        pd.DataFrame([_row()]).to_sql("performance", conn, index=False)
        incoming = pd.DataFrame([_row(), _row(policy="12345678902", amount=20000)]).drop(columns="是否职拓")
        assert write_raw_table_incremental(conn, "performance", incoming, mode="supplement") == 1
        assert write_raw_table_incremental(conn, "performance", incoming, mode="supplement") == 0
        assert tuple(conn.execute('SELECT COUNT(*),SUM("期交保费"),SUM("是否职拓"=\'是\') FROM performance').fetchone()) == (2, 30000, 1)
        bad = incoming.copy()
        bad.loc[0, "期交保费"] = 999
        with pytest.raises(RawIncrementalWriteError, match="不一致"):
            write_raw_table_incremental(conn, "performance", bad, mode="supplement")
        assert conn.execute('SELECT SUM("期交保费") FROM performance').fetchone()[0] == 30000


def test_pipeline_refreshes_new_performance_customer_facts_and_atomic_rollback(auth_db, monkeypatch):
    from db.connection import get_db
    import services.excel_pipeline as pipeline
    with get_db() as conn:
        _seed(conn)
        frame = pd.DataFrame([_row(amount=25000)])
        result = ExcelPipelineResult(raw_tables={"performance": frame}, rows_by_table=build_aggregate_rows_from_raw({"performance": frame}))
        write_excel_pipeline_result(conn, result, incremental=True)
        assert conn.execute("SELECT SUM(qj_premium) FROM customer_policy_month_fact").fetchone()[0] == 25000
        conn.commit()
        old_raw = [tuple(row) for row in conn.execute("SELECT * FROM performance")]
        old_fact = [tuple(row) for row in conn.execute("SELECT * FROM customer_policy_month_fact")]
        old_agg = [tuple(row) for row in conn.execute("SELECT * FROM agg_daily_performance")]
        def fail(*args, **kwargs):
            raise CustomerFactRefreshError("synthetic failure after raw writes")
        monkeypatch.setattr(pipeline, "refresh_customer_facts", fail)
        frame = pd.DataFrame([_row(amount=30000)])
        result = ExcelPipelineResult(raw_tables={"performance": frame}, rows_by_table=build_aggregate_rows_from_raw({"performance": frame}))
        with pytest.raises(CustomerFactRefreshError):
            write_excel_pipeline_result(conn, result, incremental=True)
        assert [tuple(row) for row in conn.execute("SELECT * FROM performance")] == old_raw
        assert [tuple(row) for row in conn.execute("SELECT * FROM customer_policy_month_fact")] == old_fact
        assert [tuple(row) for row in conn.execute("SELECT * FROM agg_daily_performance")] == old_agg


def test_pipeline_supplement_rebuilds_from_complete_persisted_month(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        _seed(conn)
        frame = pd.DataFrame([_row(policy="12345678902", amount=20000)]).drop(columns="是否职拓")
        result = ExcelPipelineResult(raw_tables={"performance": frame}, rows_by_table=build_aggregate_rows_from_raw({"performance": frame}))
        write_excel_pipeline_result(conn, result, incremental=True, import_mode="supplement")
        assert conn.execute('SELECT SUM("期交保费") FROM performance').fetchone()[0] == 30000
        assert conn.execute("SELECT SUM(qj_premium) FROM agg_daily_performance").fetchone()[0] == 3
        assert conn.execute("SELECT SUM(qj_premium) FROM agg_zhituo_performance").fetchone()[0] == 1
        assert conn.execute("SELECT SUM(qj_premium) FROM customer_policy_month_fact").fetchone()[0] == 30000


def test_customer_snapshot_can_arrive_before_raw_premium(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        _seed(conn)
        conn.execute("DELETE FROM performance")
        conn.commit()
        frame = pd.DataFrame([_row()])
        result = ExcelPipelineResult(raw_tables={"performance": frame}, rows_by_table=build_aggregate_rows_from_raw({"performance": frame}))
        write_excel_pipeline_result(conn, result, incremental=True)
        assert tuple(conn.execute("SELECT customer_match,qj_premium FROM customer_policy_month_fact").fetchone()) == (1, 10000)


def test_incremental_refresh_does_not_touch_unselected_facts(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        _seed(conn, [_row(), _row(policy="12345678902", amount=7000, 年月="2026-07", 年月日="2026-07-20")])
        refresh_customer_facts(conn)
        conn.commit()
        untouched = tuple(conn.execute("SELECT * FROM customer_policy_month_fact WHERE month=7").fetchone())
        conn.execute('UPDATE performance SET "期交保费"=15000 WHERE "年月"=\'2026-08\'')
        result = refresh_customer_facts(conn, [policy_key("0012345678901")])
        assert result["affectedKeys"] == 1
        assert tuple(conn.execute("SELECT * FROM customer_policy_month_fact WHERE month=7").fetchone()) == untouched
        assert conn.execute("SELECT SUM(qj_premium) FROM customer_policy_month_fact").fetchone()[0] == 22000


def test_supplement_rejects_ambiguous_numeric_aliases_without_customer_database():
    with sqlite3.connect(":memory:") as conn:
        with pytest.raises(RawIncrementalWriteError, match="一对多"):
            write_raw_table_incremental(conn, "performance", pd.DataFrame([
                _row(), _row(policy="880012345678901")
            ]), mode="supplement")
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='performance'").fetchone()[0] == 0


def test_full_refresh_supports_compact_month_without_changing_raw(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        _seed(conn, [_row(年月="202608")])
        refresh_customer_facts(conn)
        assert tuple(conn.execute("SELECT year,month,qj_premium FROM customer_policy_month_fact").fetchone()) == (2026, 8, 10000)
        assert conn.execute('SELECT "年月" FROM performance').fetchone()[0] == "202608"
