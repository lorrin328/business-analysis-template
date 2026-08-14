#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate(report: dict, minimum: int = 0) -> list[str]:
    errors: list[str] = []
    sources = [
        source for source in report.get("sources") or []
        if isinstance(source, dict) and source.get("sourceType") == "official_wechat"
    ]
    if len(sources) < minimum:
        errors.append(f"official WeChat source count {len(sources)} is below required {minimum}")
    for index, source in enumerate(sources):
        label = str(source.get("id") or f"wechat[{index}]")
        parsed = urlparse(str(source.get("url") or ""))
        verification = source.get("verification") or {}
        if (
            parsed.scheme != "https"
            or parsed.hostname != "mp.weixin.qq.com"
            or not (parsed.path == "/s" or parsed.path.startswith("/s/"))
        ):
            errors.append(f"{label}: URL must be a public mp.weixin.qq.com HTTPS article")
        if source.get("sourceLevel") != "B":
            errors.append(f"{label}: sourceLevel must be B")
        if not str(source.get("publisher") or "").strip():
            errors.append(f"{label}: publisher is required")
        if verification.get("status") != "verified":
            errors.append(f"{label}: independent verification is required")
        if verification.get("publisherMatched") is not True:
            errors.append(f"{label}: publisher identity must match the article account")
        if verification.get("titleMatched") is not True:
            errors.append(f"{label}: title must match the fetched article")
        if verification.get("excerptMatched") is not True:
            errors.append(f"{label}: excerpt must occur in the article body")
        status = verification.get("httpStatus")
        if not isinstance(status, int) or not 200 <= status < 400:
            errors.append(f"{label}: successful HTTP status is required")
        if not SHA256.fullmatch(str(source.get("contentHash") or "")):
            errors.append(f"{label}: SHA-256 contentHash is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate independently verified official WeChat sources")
    parser.add_argument("report", type=Path)
    parser.add_argument("--require-at-least", type=int, default=0)
    args = parser.parse_args()
    payload = json.loads(args.report.read_text(encoding="utf-8"))
    errors = validate(payload, max(0, args.require_at_least))
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False))
        return 1
    count = sum(
        1 for source in payload.get("sources") or []
        if isinstance(source, dict) and source.get("sourceType") == "official_wechat"
    )
    print(json.dumps({"status": "ok", "officialWechatSources": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
