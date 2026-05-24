"""Rebuild SQLite aggregate tables from raw detail tables.

Use this after code changes that alter aggregate definitions when production
does not keep the original Excel files on disk.
"""
from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables


def main():
    result = rebuild_aggregates_from_raw_tables()
    print(f"rebuilt years: {result.years}")
    print(f"raw counts: {result.raw_counts}")
    print(f"aggregate counts: {result.table_counts}")


if __name__ == "__main__":
    main()
