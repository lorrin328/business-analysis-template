"""Rebuild customer facts without recomputing unrelated business aggregates."""
import json

from db import get_db, init_db
from services.customer_fact_refresh import ensure_policy_key_indexes, refresh_customer_facts
from services.operation_lock import operation_lock


def rebuild_customer_facts() -> dict:
    init_db()
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            ensure_policy_key_indexes(conn)
            result = refresh_customer_facts(conn)
            if result.get("skipped"):
                raise RuntimeError("Customer fact rebuild prerequisites are missing; required rebuild was not completed")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        conn.execute("PRAGMA optimize")
        conn.commit()
    return result


def main():
    with operation_lock("customer-fact-rebuild", timeout=1.0):
        result = rebuild_customer_facts()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
