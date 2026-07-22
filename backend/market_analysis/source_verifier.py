from __future__ import annotations

import hashlib
import http.client
import ipaddress
import os
import re
import socket
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import parse_qsl, urljoin, urlparse


ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml", "text/plain", "application/pdf"}
SENSITIVE_QUERY_KEYS = {"token", "access_token", "api_key", "apikey", "secret", "authorization"}


class SourceVerificationError(ValueError):
    pass


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_title = False
        self._ignored_depth = 0
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.meta_titles: list[str] = []

    def handle_starttag(self, tag, attrs):
        name = tag.lower()
        attributes = {str(key).lower(): str(value or "") for key, value in attrs}
        if name == "title":
            self._in_title = True
        if name in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if name == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            if key in {"og:title", "twitter:title"} and attributes.get("content"):
                self.meta_titles.append(attributes["content"].strip())

    def handle_endtag(self, tag):
        name = tag.lower()
        if name == "title":
            self._in_title = False
        if name in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data):
        text = " ".join(str(data or "").split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if not self._ignored_depth:
            self.body_parts.append(text)

    @property
    def title(self) -> str:
        value = " ".join(self.title_parts).strip() or (self.meta_titles[0] if self.meta_titles else "")
        return value[:300]

    @property
    def body(self) -> str:
        return " ".join(self.body_parts)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_public_url(url: str) -> list[str]:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SourceVerificationError("source URL must use http(s)")
    if parsed.username or parsed.password:
        raise SourceVerificationError("source URL must not contain credentials")
    if parsed.port and parsed.port not in {80, 443}:
        raise SourceVerificationError("source URL uses a non-standard port")
    if any(key.lower() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise SourceVerificationError("source URL contains a sensitive query parameter")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SourceVerificationError(f"source host cannot be resolved: {parsed.hostname}") from exc
    public_addresses: list[str] = []
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise SourceVerificationError(f"source host resolves to a non-public address: {parsed.hostname}")
        value = str(ip)
        if value not in public_addresses:
            public_addresses.append(value)
    return public_addresses


def _decode_text(data: bytes, declared_charset: str | None) -> str:
    candidates = [declared_charset, "utf-8", "gb18030"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return data.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _extract_content(data: bytes, content_type: str, charset: str | None) -> tuple[str, str]:
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = _PageParser()
        parser.feed(_decode_text(data, charset))
        return parser.title, parser.body
    if content_type == "text/plain":
        body = _decode_text(data, charset)
        return body.splitlines()[0][:300] if body else "", body
    if content_type == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            body = "\n".join((page.extract_text() or "") for page in reader.pages[:200])
        except Exception as exc:
            raise SourceVerificationError(f"PDF text extraction failed: {exc}") from exc
        if not body.strip():
            raise SourceVerificationError("PDF has no independently extractable text")
        return "", body
    raise SourceVerificationError(f"unsupported source content type: {content_type or 'unknown'}")


def _normalized_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def _title_matches(declared: str, fetched: str) -> bool:
    expected = _normalized_text(declared)
    actual = _normalized_text(fetched)
    if not expected or not actual:
        return False
    if expected in actual or actual in expected:
        return True
    return SequenceMatcher(None, expected, actual).ratio() >= 0.6


def _excerpt_matches(excerpt: str, body: str) -> bool:
    expected = _normalized_text(excerpt)
    actual = _normalized_text(body)
    return len(expected) >= 8 and expected in actual


def _published_at_matches(published_at: str, body: str) -> bool:
    value = str(published_at or "").strip()
    if not value:
        return True
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            published = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return False
    normalized_body = _normalized_text(body)
    variants = {
        _normalized_text(published.isoformat()),
        _normalized_text(f"{published.year}年{published.month}月{published.day}日"),
        _normalized_text(f"{published.year}/{published.month:02d}/{published.day:02d}"),
    }
    return any(variant and variant in normalized_body for variant in variants)


def _evidence_context(report: dict, source_id: str) -> str:
    parts: list[str] = []
    for module in report.get("modules") or []:
        if source_id in [str(value) for value in (module.get("evidenceIds") or [])]:
            parts.append(str(module.get("fact") or ""))
    executive = report.get("executiveSummary") or {}
    if source_id in [str(value) for value in (executive.get("evidenceIds") or [])]:
        parts.append(str(executive.get("summary") or ""))
    for action in report.get("actions") or []:
        if source_id in [str(value) for value in (action.get("evidenceIds") or [])]:
            parts.extend([str(action.get("action") or ""), str(action.get("trigger") or "")])
    for entries in (report.get("changeSignals") or {}).values():
        for entry in entries or []:
            if source_id in [str(value) for value in (entry.get("evidenceIds") or [])]:
                parts.append(str(entry.get("summary") or ""))
    return " ".join(part for part in parts if part)


def _best_exact_excerpt(body: str, context: str, maximum: int = 50) -> str:
    text = " ".join(str(body or "").split())
    if len(text) <= maximum:
        return text
    normalized_context = _normalized_text(context)
    numeric_tokens = re.findall(r"\d+(?:[.,]\d+)*(?:%|万|亿|元|年|月|日)?", str(context or ""))
    direction_terms = [
        term for term in ("上升", "下降", "增长", "减少", "增加", "降低", "提高", "收紧", "放宽", "实施", "生效", "不得", "尚未")
        if term in context
    ]
    search_tokens = numeric_tokens + direction_terms
    compact = re.sub(r"\s+", "", str(context or ""))
    search_tokens.extend(compact[index:index + 6] for index in range(0, max(0, len(compact) - 5), 3))
    starts: set[int] = {0}
    for token in search_tokens[:80]:
        if len(token) < 2:
            continue
        cursor = 0
        for _ in range(20):
            position = text.find(token, cursor)
            if position < 0:
                break
            starts.update({max(0, position - 10), max(0, position - maximum // 2)})
            cursor = position + 1
    for match in re.finditer(r"[^。！？；\n]{8,160}[。！？；]?", text):
        starts.add(match.start())
        if len(starts) >= 600:
            break

    def score(start: int) -> tuple[int, int, int]:
        window = text[start:start + maximum]
        normalized_window = _normalized_text(window)
        numeric_score = sum(len(token) for token in numeric_tokens if _normalized_text(token) in normalized_window)
        direction_score = sum(len(term) for term in direction_terms if term in window)
        overlap = SequenceMatcher(None, normalized_context, normalized_window).find_longest_match().size
        return numeric_score, direction_score, overlap

    best_start = max(starts, key=score)
    return text[best_start:best_start + maximum]


def align_module_facts_to_verified_excerpts(report: dict) -> dict:
    """Replace each module fact with its closest independently verified excerpt."""
    source_by_id = {
        str(source.get("id") or ""): source
        for source in report.get("sources") or []
        if str(source.get("id") or "")
    }
    for module in report.get("modules") or []:
        original_fact = str(module.get("fact") or "")
        normalized_fact = _normalized_text(original_fact)
        numeric_tokens = re.findall(r"\d+(?:[.,]\d+)*(?:%|万|亿|元|年|月|日)?", original_fact)
        polarity_terms = [
            term for term in (
                "征求意见", "正式发布", "生效", "实施", "废止", "取消", "禁止", "不得", "尚未", "未",
                "上升", "下降", "增长", "减少", "增加", "降低", "提高", "收紧", "放宽", "强化", "弱化",
            )
            if term in original_fact
        ]
        candidates: list[tuple[int, str]] = []
        for index, evidence_id in enumerate(module.get("evidenceIds") or []):
            source = source_by_id.get(str(evidence_id))
            verification = (source or {}).get("verification") or {}
            excerpt = str((source or {}).get("excerpt") or "").strip()
            if verification.get("excerptMatched") is True and excerpt:
                candidates.append((index, excerpt))
        if not candidates:
            continue

        def score(candidate: tuple[int, str]) -> tuple[int, int, int, float, int]:
            index, excerpt = candidate
            normalized_excerpt = _normalized_text(excerpt)
            numeric_score = sum(len(token) for token in numeric_tokens if _normalized_text(token) in normalized_excerpt)
            polarity_score = sum(len(term) for term in polarity_terms if term in excerpt)
            matcher = SequenceMatcher(None, normalized_fact, normalized_excerpt)
            return numeric_score, polarity_score, matcher.find_longest_match().size, matcher.ratio(), -index

        module["fact"] = max(candidates, key=score)[1]
    return report


def _open_pinned(url: str, timeout: int, max_bytes: int) -> tuple[int, str, str | None, bytes, str]:
    current_url = url
    for _ in range(6):
        addresses = _ensure_public_url(current_url)
        parsed = urlparse(current_url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_class(parsed.hostname, port, timeout=timeout)
        pinned_ip = addresses[0]
        connection._create_connection = lambda _address, timeout=None, source_address=None: socket.create_connection(  # type: ignore[attr-defined]
            (pinned_ip, port), timeout, source_address
        )
        target = parsed.path or "/"
        if parsed.query:
            target += f"?{parsed.query}"
        try:
            connection.connect()
            peer_ip = ipaddress.ip_address(connection.sock.getpeername()[0]) if connection.sock else None
            if not peer_ip or not peer_ip.is_global or str(peer_ip) != pinned_ip:
                raise SourceVerificationError("source connection peer did not match the pinned public address")
            connection.request(
                "GET",
                target,
                headers={
                    "User-Agent": "BusinessAnalysisEvidenceVerifier/1.0 (+source-validation)",
                    "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            status = int(response.status)
            location = response.getheader("Location")
            if status in {301, 302, 303, 307, 308}:
                if not location:
                    raise SourceVerificationError(f"source returned redirect HTTP {status} without Location")
                redirected = urljoin(current_url, location)
                if parsed.scheme == "https" and urlparse(redirected).scheme != "https":
                    raise SourceVerificationError("source redirect attempted to downgrade HTTPS")
                current_url = redirected
                continue
            content_type = str(response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            charset = response.headers.get_content_charset()
            data = response.read(max_bytes + 1)
            return status, content_type, charset, data, current_url
        finally:
            connection.close()
    raise SourceVerificationError("source exceeded five redirects")


def _fetch_external(url: str) -> dict:
    timeout = int(os.getenv("MARKET_ANALYSIS_SOURCE_TIMEOUT_SECONDS", "25"))
    max_bytes = int(os.getenv("MARKET_ANALYSIS_SOURCE_MAX_BYTES", str(32 * 1024 * 1024)))
    status, content_type, charset, data, final_url = _open_pinned(url, timeout, max_bytes)
    if status < 200 or status >= 400:
        raise SourceVerificationError(f"source returned HTTP {status}")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise SourceVerificationError(f"unsupported source content type: {content_type or 'unknown'}")
    if not data:
        raise SourceVerificationError("source returned an empty body")
    truncated = len(data) > max_bytes
    if truncated:
        raise SourceVerificationError(f"source exceeds {max_bytes} byte verification limit")
    page_title, body = _extract_content(data, content_type, charset)
    return {
        "status": "verified",
        "httpStatus": status,
        "finalUrl": final_url,
        "pageTitle": page_title,
        "contentType": content_type,
        "verifiedAt": _now_iso(),
        "contentHash": hashlib.sha256(data).hexdigest(),
        "bytesRead": len(data),
        "truncated": False,
        "_body": body,
    }


def verify_report_sources(report: dict, *, internal_content_hash: str, internal_content_text: str) -> dict:
    errors: list[str] = []
    for source in report.get("sources") or []:
        source_id = str(source.get("id") or "?")
        if source.get("sourceType") == "internal":
            excerpt_matched = _excerpt_matches(str(source.get("excerpt") or ""), internal_content_text)
            if not excerpt_matched:
                source["excerpt"] = _best_exact_excerpt(
                    internal_content_text,
                    _evidence_context(report, source_id),
                )
                excerpt_matched = _excerpt_matches(str(source.get("excerpt") or ""), internal_content_text)
                if not excerpt_matched:
                    errors.append(f"source {source_id} evidence excerpt was not found in the internal snapshot")
                    continue
            verified_at = _now_iso()
            source["retrievedAt"] = verified_at
            source["contentHash"] = internal_content_hash
            source["verification"] = {
                "status": "internal",
                "verifiedAt": verified_at,
                "contentHash": internal_content_hash,
                "excerptMatched": True,
            }
            continue
        try:
            verification = _fetch_external(str(source.get("url") or ""))
        except Exception as exc:
            errors.append(f"source {source_id} failed independent verification: {exc}")
            continue
        content_type = verification.get("contentType")
        if content_type in {"text/html", "application/xhtml+xml", "text/plain"}:
            verification["titleMatched"] = _title_matches(str(source.get("title") or ""), str(verification.get("pageTitle") or ""))
            if not verification["titleMatched"]:
                fetched_title = str(verification.get("pageTitle") or "").strip()
                if not fetched_title:
                    errors.append(f"source {source_id} page title does not match the declared source title")
                    continue
                source["title"] = fetched_title[:120]
                verification["titleMatched"] = True
        else:
            verification["titleMatched"] = None
        body = str(verification.pop("_body", ""))
        verification["excerptMatched"] = _excerpt_matches(str(source.get("excerpt") or ""), body)
        if not verification["excerptMatched"]:
            source["excerpt"] = _best_exact_excerpt(body, _evidence_context(report, source_id))
            verification["excerptMatched"] = _excerpt_matches(str(source.get("excerpt") or ""), body)
            if not verification["excerptMatched"]:
                errors.append(f"source {source_id} evidence excerpt was not found in the source body")
                continue
        published_at = str(source.get("publishedAt") or "").strip()
        verification["publishedAtMatched"] = _published_at_matches(published_at, body) if published_at else None
        if published_at and verification["publishedAtMatched"] is not True:
            source["publishedAt"] = None
            verification["publishedAtMatched"] = None
        source["url"] = verification["finalUrl"]
        source["retrievedAt"] = verification["verifiedAt"]
        source["contentHash"] = verification["contentHash"]
        source["verification"] = verification
    if errors:
        raise SourceVerificationError("; ".join(errors))
    return report
