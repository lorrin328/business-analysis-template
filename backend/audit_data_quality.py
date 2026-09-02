"""Run data quality audit against the configured SQLite database."""
from __future__ import annotations

import argparse
import json

from config.business_lines import DEFAULT_YEAR
from services.data_quality_audit import run_data_quality_audit


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Also fail on warnings")
    args = parser.parse_args(argv)

    try:
        result = run_data_quality_audit(args.year)
    except Exception as exc:
        result = {
            "status": "error", "year": args.year, "issue_count": 1,
            "issues": [{"severity": "error", "code": "audit_execution_failed",
                        "message": "Read-only audit could not complete; no repair was attempted",
                        "context": {"error_type": type(exc).__name__}}],
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result['status']}")
        print(f"year: {result['year']}")
        print(f"issues: {result['issue_count']}")
        for issue in result["issues"]:
            print(f"[{issue['severity']}] {issue['code']}: {issue['message']} {issue['context']}")
    return 1 if result["status"] in {"fail", "error"} or (args.strict and result["status"] != "ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
