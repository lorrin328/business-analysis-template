#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_project_root(report_path: Path, explicit: Path | None) -> Path | None:
    candidates = []
    if explicit:
        candidates.append(explicit.resolve())
    candidates.extend([Path.cwd().resolve(), report_path.resolve().parent, *report_path.resolve().parents])
    for candidate in candidates:
        if (candidate / "backend" / "market_analysis" / "validator.py").is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a market-analysis report with the canonical publication gate")
    parser.add_argument("report", type=Path)
    parser.add_argument("--project-root", type=Path)
    args = parser.parse_args()
    project_root = find_project_root(args.report, args.project_root)
    if not project_root:
        print("ERROR: canonical backend/market_analysis/validator.py was not found; validation cannot safely continue")
        return 2
    sys.path.insert(0, str(project_root / "backend"))
    from market_analysis.validator import ReportValidationError, validate_report

    report = json.loads(args.report.read_text(encoding="utf-8"))
    try:
        validate_report(report, require_verified_sources=True)
    except ReportValidationError as exc:
        for error in exc.errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: report passed the canonical publication checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
