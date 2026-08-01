"""Build full performance history and customer analysis facts in an offline SQLite copy."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, help="Offline SQLite copy to update")
    parser.add_argument("--source-dir", required=True, help="Directory containing 12 performance and 5 customer extracts")
    parser.add_argument("--imported-by", default="cli")
    parser.add_argument("--allow-live-database", action="store_true")
    parser.add_argument("--skip-aggregate-rebuild", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    database = Path(args.database).resolve()
    if database.name == "business_data.db" and not args.allow_live_database:
        raise SystemExit("拒绝直接修改运行库；请先创建离线副本，或显式使用 --allow-live-database")
    if not database.exists():
        raise SystemExit(f"数据库副本不存在：{database}")
    os.environ["BUSINESS_ANALYSIS_DB"] = str(database)

    from db import init_db
    from history_import import FullHistoryImporter
    from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables

    init_db()
    importer = FullHistoryImporter(database, args.source_dir, imported_by=args.imported_by)
    try:
        result = importer.run()
    finally:
        importer.close()
    aggregates = None if args.skip_aggregate_rebuild else rebuild_aggregates_from_raw_tables()
    payload = {
        "batchId": result.batch_id,
        "performanceRows": result.performance_rows,
        "customerSourceRows": result.customer_source_rows,
        "customerPolicyRows": result.customer_policy_rows,
        "customerFactRows": result.fact_rows,
        "sourceTextIssueRows": result.source_text_issue_rows,
        "sourceCutoff": result.source_cutoff,
        "quickCheck": result.quick_check,
        "aggregateYears": None if aggregates is None else aggregates.years,
        "aggregateCounts": None if aggregates is None else aggregates.table_counts,
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
