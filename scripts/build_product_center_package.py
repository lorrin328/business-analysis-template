"""Create an offline admin import ZIP from the read-only 007 allowlist."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from product_center.converter import build_package  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线构建产品研究中心导入包；来源项目只读，原件不进入Git")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="受保护目录的全新ZIP路径，不覆盖既有成果")
    parser.add_argument("--overrides", type=Path, help="有来源哈希及定位的私人身份更正JSON")
    args = parser.parse_args(argv)
    try:
        manifest = build_package(args.source_root, args.output, args.overrides)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"success": True, "versions": len(manifest["versions"]),
        "scenarios": len(manifest["scenarios"]), "sources": len(manifest["sources"]),
        "arithmeticPassed": manifest["report"]["arithmetic"]["passedCount"],
        "quarantined": manifest["report"]["quarantinedScenarioCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
