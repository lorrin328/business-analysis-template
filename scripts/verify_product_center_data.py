"""Independent strict regression of source cashflows, with a private JSON report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from product_center.converter import Converter  # noqa: E402
from product_center.irr import verify_calculations  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="独立重算全部保单年度IRR；失败返回非零；详细结果仅写私人报告")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--expected-numeric", type=int, default=774)
    parser.add_argument("--expected-canonical", type=int, default=790)
    args = parser.parse_args(argv)
    report_path = args.report.resolve()
    if report_path.is_relative_to(args.source_root.resolve()):
        parser.error("验收报告不能写入只读来源项目")
    try:
        converter = Converter(args.source_root)
        arithmetic = verify_calculations(converter.data["combined"])
        if arithmetic["numericCount"] != args.expected_numeric:
            arithmetic["coverageErrors"].append("数值记录数与预期不一致")
        if arithmetic["canonicalCount"] != args.expected_canonical:
            arithmetic["coverageErrors"].append("规范记录数与预期不一致")
        arithmetic["passed"] = arithmetic["passed"] and not arithmetic["coverageErrors"]
        coverage = converter.coverage_report()
        report = {"sourceDate": converter.source_date, "arithmetic": arithmetic,
                  "coverage": coverage, "passed": arithmetic["passed"] and coverage["passed"]}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report = {"passed": False, "error": str(exc)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"passed": report["passed"],
        "numericCount": report.get("arithmetic", {}).get("numericCount"),
        "passedCount": report.get("arithmetic", {}).get("passedCount"),
        "failureCount": report.get("arithmetic", {}).get("failureCount"),
        "sourceHashesVerified": report.get("coverage", {}).get("baselineHashVerifiedCount")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
