"""Run data quality audit against the configured SQLite database."""
from __future__ import annotations

import argparse
import json

from config.business_lines import DEFAULT_YEAR
from services.data_quality_audit import run_data_quality_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_data_quality_audit(args.year)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"status: {result['status']}")
    print(f"year: {result['year']}")
    print(f"issues: {result['issue_count']}")
    for issue in result["issues"]:
        print(f"[{issue['severity']}] {issue['code']}: {issue['message']} {issue['context']}")


if __name__ == "__main__":
    main()
