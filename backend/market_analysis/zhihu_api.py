from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ZHIHU_SEARCH_ENDPOINT = "https://developer.zhihu.com/api/v1/content/zhihu_search"
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class ZhihuApiError(RuntimeError):
    pass


def zhihu_enabled() -> bool:
    configured = os.getenv("MARKET_ANALYSIS_ZHIHU_ENABLED", "0").strip().lower()
    return configured not in {"0", "false", "no", "off"} and bool(
        os.getenv("ZHIHU_ACCESS_SECRET", "").strip()
    )


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(maximum, max(minimum, value))


def default_zhihu_queries(ledger: list[dict] | None = None) -> list[dict]:
    year = datetime.now().year
    queries = [
        {"section": "macro", "query": f"利率 储蓄 分红险 寿险需求 {year}"},
        {"section": "regulation", "query": f"寿险 监管 政策 保险消费者 {year}"},
        {"section": "peers", "query": f"寿险公司 新产品 新渠道 新模式 {year}"},
        {"section": "business_line", "query": f"保险 经代 OTO 职域 渠道 客户需求 {year}"},
        {"section": "business_line", "query": f"寿险 理赔 服务 投诉 客户体验 {year}"},
    ]
    for item in ledger or []:
        title = _clean_text(item.get("title"))
        section = str(item.get("section") or "").strip()
        if title and section in {"macro", "regulation", "peers", "business_line"}:
            queries.append({"section": section, "query": f"{title} 寿险 {year}"})
    unique: list[dict] = []
    seen: set[str] = set()
    for item in queries:
        query = _clean_text(item.get("query"))[:100]
        if not query or query in seen:
            continue
        seen.add(query)
        unique.append({"section": item["section"], "query": query})
    return unique[:_bounded_int("MARKET_ANALYSIS_ZHIHU_MAX_QUERIES", 4, 1, 8)]


def _clean_text(value: object) -> str:
    text = html.unescape(_HTML_TAG_RE.sub(" ", str(value or "")))
    return _SPACE_RE.sub(" ", text).strip(" \t\r\n…")


def _walk_dicts(value: object, *, limit: int = 500) -> list[dict]:
    rows: list[dict] = []
    stack = [value]
    while stack and len(rows) < limit:
        current = stack.pop()
        if isinstance(current, dict):
            rows.append(current)
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))
    return rows


def _nested_value(row: dict, paths: tuple[tuple[str, ...], ...]) -> object:
    for path in paths:
        current: object = row
        for part in path:
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, "", [], {}):
            return current
    return None


def _canonical_zhihu_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw.startswith(("https://", "http://")):
        return ""
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    allowed = False
    if host == "zhuanlan.zhihu.com" and re.fullmatch(r"/p/\d+", path):
        allowed = True
    elif host in {"www.zhihu.com", "zhihu.com"} and (
        re.fullmatch(r"/question/\d+", path)
        or re.fullmatch(r"/question/\d+/answer/\d+", path)
    ):
        allowed = True
        host = "www.zhihu.com"
    if not allowed:
        return ""
    return urlunsplit(("https", host, path, "", ""))


def _published_at(value: object) -> str | None:
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            return None
    text = _clean_text(value)
    return text[:40] or None


def _candidate_from_node(row: dict, *, section: str, query: str) -> dict | None:
    url = _canonical_zhihu_url(_nested_value(row, (
        ("url",), ("link",), ("href",), ("content_url",), ("target_url",), ("share_url",),
    )))
    if not url:
        return None
    title = _clean_text(_nested_value(row, (
        ("title",), ("question_title",), ("name",), ("question", "title"),
    )))[:120]
    excerpt = _clean_text(_nested_value(row, (
        ("excerpt",), ("snippet",), ("summary",), ("description",), ("content",), ("text",),
    )))[:50]
    publisher = _clean_text(_nested_value(row, (
        ("author_name",), ("publisher",), ("author", "name"), ("author", "headline"),
        ("user", "name"), ("account", "name"),
    )))[:60]
    if not title or len(excerpt) < 8:
        return None
    return {
        "queryTheme": query,
        "section": section,
        "claim": excerpt,
        "title": title,
        "publisher": publisher or "知乎公开内容",
        "url": url,
        "sourceType": "media",
        "sourceLevel": "C",
        "publishedAt": _published_at(_nested_value(row, (
            ("published_at",), ("publishedAt",), ("created_at",), ("createdAt",), ("created_time",),
        ))),
        "excerpt": excerpt,
        "discoveryChannel": "zhihu_official_api",
    }


def parse_zhihu_candidates(payload: object, *, section: str, query: str) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for row in _walk_dicts(payload):
        candidate = _candidate_from_node(row, section=section, query=query)
        if candidate is None or candidate["url"] in seen:
            continue
        seen.add(candidate["url"])
        candidates.append(candidate)
    return candidates


def search_zhihu(query: str, *, timeout_seconds: int | None = None) -> object:
    secret = os.getenv("ZHIHU_ACCESS_SECRET", "").strip()
    if not secret:
        raise ZhihuApiError("ZHIHU_ACCESS_SECRET is not configured")
    timeout = timeout_seconds or _bounded_int("MARKET_ANALYSIS_ZHIHU_TIMEOUT_SECONDS", 20, 5, 60)
    request = Request(
        f"{ZHIHU_SEARCH_ENDPOINT}?{urlencode({'Query': query})}",
        headers={
            "Authorization": f"Bearer {secret}",
            "X-Request-Timestamp": str(int(time.time())),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "business-analysis-market/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise ZhihuApiError(f"Zhihu API returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ZhihuApiError(f"Zhihu API request failed: {type(exc).__name__}") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ZhihuApiError("Zhihu API response exceeded the configured safety limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ZhihuApiError("Zhihu API returned an invalid JSON response") from exc


def scout_zhihu_sources(ledger: list[dict] | None = None) -> tuple[list[dict], dict]:
    if not zhihu_enabled():
        return [], {"enabled": False, "status": "disabled", "queryCount": 0, "candidateCount": 0}
    candidates: list[dict] = []
    failures: list[str] = []
    queries = default_zhihu_queries(ledger)
    for item in queries:
        try:
            payload = search_zhihu(item["query"])
            candidates.extend(parse_zhihu_candidates(
                payload,
                section=item["section"],
                query=item["query"],
            ))
        except ZhihuApiError as exc:
            failures.append(str(exc)[:120])
    unique: list[dict] = []
    seen: set[str] = set()
    maximum = _bounded_int("MARKET_ANALYSIS_ZHIHU_MAX_RESULTS", 12, 1, 30)
    for candidate in candidates:
        if candidate["url"] in seen:
            continue
        seen.add(candidate["url"])
        unique.append(candidate)
        if len(unique) >= maximum:
            break
    status = "success" if not failures else ("partial" if unique else "failed")
    return unique, {
        "enabled": True,
        "status": status,
        "queryCount": len(queries),
        "candidateCount": len(unique),
        "failureCount": len(failures),
        "failures": list(dict.fromkeys(failures))[:4],
    }
