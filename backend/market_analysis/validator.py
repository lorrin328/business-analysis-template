from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse

from market_analysis.config import CHANGE_KEYS, REPORT_SCHEMA_VERSION, SECTION_KEYS


SOURCE_TYPES = {"official", "company", "official_wechat", "association", "research", "media", "internal"}
FIRST_PARTY_TYPES = {"official", "company", "official_wechat", "association"}
HISTORY_STATES = {"new", "persistent", "strengthened", "reversed", "expired"}
TOPIC_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FACT_POLARITY_TERMS = {
    "征求意见", "正式发布", "生效", "实施", "废止", "取消", "禁止", "不得", "尚未", "未",
    "上升", "下降", "增长", "减少", "增加", "降低", "提高", "收紧", "放宽", "强化", "弱化",
}


class ReportValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _text(value) -> str:
    return str(value or "").strip()


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _evidence_ids(item: dict) -> list[str]:
    return [_text(value) for value in (item.get("evidenceIds") or []) if _text(value)]


def _limit(errors: list[str], label: str, value, maximum: int) -> None:
    if len(_text(value)) > maximum:
        errors.append(f"{label} exceeds {maximum} characters")


def _validate_evidence(errors: list[str], label: str, item: dict, sources: dict[str, dict]) -> None:
    evidence_ids = _evidence_ids(item)
    if not evidence_ids:
        errors.append(f"{label} requires evidenceIds")
        return
    missing = [evidence_id for evidence_id in evidence_ids if evidence_id not in sources]
    if missing:
        errors.append(f"{label} has unresolved evidenceIds {missing}")
    levels = {_text(sources[eid].get("sourceLevel")) for eid in evidence_ids if eid in sources}
    if levels == {"D"}:
        errors.append(f"{label} cannot rely only on D-level evidence")


def _normalized_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff.%万亿元年月日]+", "", _text(value).lower())


def _fact_supported_by_verified_excerpt(fact: str, evidence_ids: list[str], sources: dict[str, dict]) -> bool:
    normalized_fact = _normalized_text(fact)
    excerpts = [_normalized_text(sources[eid].get("excerpt")) for eid in evidence_ids if eid in sources]
    excerpts = [excerpt for excerpt in excerpts if excerpt]
    if not normalized_fact or not excerpts:
        return False
    combined = "".join(excerpts)
    numeric_tokens = re.findall(r"\d+(?:[.,]\d+)*(?:%|万|亿|元|年|月|日)?", normalized_fact)
    if any(token not in combined for token in numeric_tokens):
        return False
    if any(term in normalized_fact and term not in combined for term in FACT_POLARITY_TERMS):
        return False
    for excerpt in excerpts:
        if excerpt in normalized_fact or normalized_fact in excerpt:
            return True
        matcher = SequenceMatcher(None, normalized_fact, excerpt)
        minimum_run = min(12, max(8, len(excerpt) // 3))
        if matcher.find_longest_match().size >= minimum_run and matcher.ratio() >= 0.2:
            return True
    return False


def validate_report(report: dict, *, require_verified_sources: bool = True) -> dict:
    """Validate structural, evidence, history and independent-verification gates."""
    errors: list[str] = []
    if not isinstance(report, dict):
        raise ReportValidationError(["report must be a JSON object"])

    if _text(report.get("schemaVersion")) != REPORT_SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {REPORT_SCHEMA_VERSION}")
    for field in ("reportId", "title", "generatedAt"):
        if not _text(report.get(field)):
            errors.append(f"{field} is required")
    if _text(report.get("reviewStatus")) != "machine_validated":
        errors.append("reviewStatus must be machine_validated")
    _limit(errors, "title", report.get("title"), 60)
    generated_at = _parse_iso_datetime(_text(report.get("generatedAt")))
    if _text(report.get("generatedAt")) and not generated_at:
        errors.append("generatedAt must be timezone-aware ISO-8601")

    period = report.get("period") or {}
    period_start = _parse_date(_text(period.get("start")))
    period_end = _parse_date(_text(period.get("end")))
    if not period_start or not period_end:
        errors.append("period.start and period.end are required")
    elif period_start > period_end:
        errors.append("period.start must not be after period.end")
    elif generated_at and period_end > generated_at.date():
        errors.append("period.end must not be after generatedAt")

    sources = report.get("sources") or []
    if not isinstance(sources, list):
        sources = []
        errors.append("sources must be a list")
    if not 8 <= len(sources) <= 60:
        errors.append("sources must contain 8-60 items")
    source_by_id: dict[str, dict] = {}
    for index, source in enumerate(sources):
        source_id = _text(source.get("id"))
        if not source_id:
            errors.append(f"sources[{index}].id is required")
            continue
        if source_id in source_by_id:
            errors.append(f"duplicate source id: {source_id}")
        source_by_id[source_id] = source
        required_source_fields = ["title", "publisher", "url", "sourceType", "sourceLevel", "retrievedAt", "excerpt"]
        if require_verified_sources:
            required_source_fields.append("contentHash")
        for field in required_source_fields:
            if not _text(source.get(field)):
                errors.append(f"source {source_id}: {field} is required")
        _limit(errors, f"source {source_id}.title", source.get("title"), 120)
        _limit(errors, f"source {source_id}.publisher", source.get("publisher"), 60)
        _limit(errors, f"source {source_id}.excerpt", source.get("excerpt"), 50)
        level = _text(source.get("sourceLevel"))
        source_type = _text(source.get("sourceType"))
        if level not in {"A", "B", "C", "D"}:
            errors.append(f"source {source_id}: sourceLevel must be A/B/C/D")
        if source_type not in SOURCE_TYPES:
            errors.append(f"source {source_id}: unsupported sourceType")
        if level == "A" and source_type not in {"official", "internal"}:
            errors.append(f"source {source_id}: A-level evidence must be official or internal")
        url = _text(source.get("url"))
        parsed = urlparse(url)
        is_internal = source_type == "internal"
        if is_internal:
            if parsed.scheme != "internal":
                errors.append(f"source {source_id}: internal evidence must use internal:// URL")
        elif parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"source {source_id}: external evidence must use http(s) URL")
        if source_type == "official" and parsed.hostname and not (parsed.hostname == "gov.cn" or parsed.hostname.endswith(".gov.cn")):
            errors.append(f"source {source_id}: official evidence must use a verified gov.cn domain")
        retrieved_at = _parse_iso_datetime(_text(source.get("retrievedAt")))
        if _text(source.get("retrievedAt")) and not retrieved_at:
            errors.append(f"source {source_id}: retrievedAt must be timezone-aware ISO-8601")
        published_at = _text(source.get("publishedAt"))
        published_date = None
        if published_at:
            published_date = (_parse_iso_datetime(published_at) or _parse_date(published_at))
            if not published_date:
                errors.append(f"source {source_id}: publishedAt must be ISO-8601 or YYYY-MM-DD")
            else:
                published_date = published_date.date() if isinstance(published_date, datetime) else published_date
                if retrieved_at and published_date > retrieved_at.date():
                    errors.append(f"source {source_id}: publishedAt must not be after retrievedAt")
        if require_verified_sources:
            verification = source.get("verification") or {}
            expected_status = "internal" if is_internal else "verified"
            if verification.get("status") != expected_status:
                errors.append(f"source {source_id}: independent verification is required")
            if _text(verification.get("contentHash")) != _text(source.get("contentHash")):
                errors.append(f"source {source_id}: verification hash does not match contentHash")
            if not SHA256_PATTERN.fullmatch(_text(source.get("contentHash"))):
                errors.append(f"source {source_id}: contentHash must be SHA-256")
            if verification.get("excerptMatched") is not True:
                errors.append(f"source {source_id}: verified excerpt match is required")
            if published_at and not is_internal and verification.get("publishedAtMatched") is not True:
                errors.append(f"source {source_id}: publishedAt must be independently matched in the source body")
            verified_at = _parse_iso_datetime(_text(verification.get("verifiedAt")))
            if not verified_at or not retrieved_at or verified_at != retrieved_at:
                errors.append(f"source {source_id}: retrievedAt must equal the independent verification time")
            elif generated_at and verified_at > generated_at:
                errors.append(f"source {source_id}: verification time must not be after generatedAt")
            if not is_internal:
                if _text(verification.get("finalUrl")) != url:
                    errors.append(f"source {source_id}: finalUrl must match the published source URL")
                if not isinstance(verification.get("httpStatus"), int) or not 200 <= verification.get("httpStatus") < 400:
                    errors.append(f"source {source_id}: a successful verification HTTP status is required")
                if not _text(verification.get("contentType")) or not isinstance(verification.get("bytesRead"), int):
                    errors.append(f"source {source_id}: verification content metadata is required")

    coverage = report.get("coverage") or {}
    try:
        query_count = int(coverage.get("queryCount"))
    except (TypeError, ValueError):
        query_count = 0
    if query_count < 8:
        errors.append("coverage.queryCount must be at least eight")
    if coverage.get("sourceCount") != len(source_by_id):
        errors.append("coverage.sourceCount must equal the number of sources")
    official_count = sum(1 for source in sources if _text(source.get("sourceType")) == "official")
    wechat_count = sum(1 for source in sources if _text(source.get("sourceType")) == "official_wechat")
    if coverage.get("officialSourceCount") != official_count:
        errors.append("coverage.officialSourceCount does not match sources")
    if coverage.get("wechatSourceCount") != wechat_count:
        errors.append("coverage.wechatSourceCount does not match sources")

    modules = report.get("modules") or []
    if not isinstance(modules, list) or not 4 <= len(modules) <= 16:
        errors.append("modules must contain 4-16 items")
        modules = modules if isinstance(modules, list) else []
    module_ids: set[str] = set()
    topic_keys: set[str] = set()
    module_by_id: dict[str, dict] = {}
    section_counts = {key: 0 for key in SECTION_KEYS}
    for index, module in enumerate(modules):
        module_id = _text(module.get("id"))
        if not module_id:
            errors.append(f"modules[{index}].id is required")
        elif module_id in module_ids:
            errors.append(f"duplicate module id: {module_id}")
        module_ids.add(module_id)
        module_by_id[module_id] = module
        topic_key = _text(module.get("topicKey"))
        if not TOPIC_KEY_PATTERN.fullmatch(topic_key):
            errors.append(f"module {module_id or index}: topicKey must be a stable lowercase slug")
        elif topic_key in topic_keys:
            errors.append(f"duplicate topicKey: {topic_key}")
        topic_keys.add(topic_key)
        section = _text(module.get("section"))
        if section not in SECTION_KEYS:
            errors.append(f"module {module_id or index}: invalid section")
        else:
            section_counts[section] += 1
        for field, maximum in (("title", 40), ("question", 80), ("fact", 180), ("judgment", 180), ("impact", 180), ("watchCondition", 180)):
            if not _text(module.get(field)):
                errors.append(f"module {module_id or index}: {field} is required")
            _limit(errors, f"module {module_id or index}.{field}", module.get(field), maximum)
        if _text(module.get("confidence")) not in {"high", "medium", "low"}:
            errors.append(f"module {module_id or index}: confidence must be high/medium/low")
        history = module.get("history") or {}
        state = _text(history.get("state"))
        if state not in HISTORY_STATES:
            errors.append(f"module {module_id or index}: invalid history.state")
        since = _parse_date(_text(history.get("since")))
        if not since:
            errors.append(f"module {module_id or index}: history.since is required")
        elif period_end and since > period_end:
            errors.append(f"module {module_id or index}: history.since must not be after period.end")
        if state != "new" and not _text(history.get("previousReportId")):
            errors.append(f"module {module_id or index}: non-new history requires previousReportId")
        if state == "new" and _text(history.get("previousReportId")):
            errors.append(f"module {module_id or index}: new history must not reference previousReportId")
        _validate_evidence(errors, f"module {module_id or index}", module, source_by_id)
        if require_verified_sources and not _fact_supported_by_verified_excerpt(module.get("fact"), _evidence_ids(module), source_by_id):
            errors.append(f"module {module_id or index}: fact is not supported by its verified source excerpts")

    for section, count in section_counts.items():
        if not 1 <= count <= 4:
            errors.append(f"section {section} requires 1-4 modules")

    for section in ("macro", "regulation"):
        section_evidence = {
            evidence_id
            for module in modules
            if _text(module.get("section")) == section
            for evidence_id in _evidence_ids(module)
        }
        if not any(
            _text(source_by_id.get(eid, {}).get("sourceLevel")) == "A"
            and _text(source_by_id.get(eid, {}).get("sourceType")) == "official"
            for eid in section_evidence
        ):
            errors.append(f"section {section} requires official A-level evidence")

    peer_evidence = {
        evidence_id
        for module in modules
        if _text(module.get("section")) == "peers"
        for evidence_id in _evidence_ids(module)
    }
    if not any(
        _text(source_by_id.get(eid, {}).get("sourceLevel")) in {"A", "B"}
        and _text(source_by_id.get(eid, {}).get("sourceType")) in FIRST_PARTY_TYPES
        for eid in peer_evidence
    ):
        errors.append("section peers requires A/B-level first-party evidence")

    changes = report.get("changeSignals") or {}
    classified_module_ids: list[str] = []
    for key in CHANGE_KEYS:
        entries = changes.get(key)
        if not isinstance(entries, list):
            errors.append(f"changeSignals.{key} must be a list")
            continue
        if len(entries) > 16:
            errors.append(f"changeSignals.{key} must contain no more than sixteen items")
        for index, entry in enumerate(entries):
            label = f"changeSignals.{key}[{index}]"
            if not _text(entry.get("title")) or not _text(entry.get("summary")):
                errors.append(f"{label} requires title and summary")
            _limit(errors, f"{label}.title", entry.get("title"), 40)
            _limit(errors, f"{label}.summary", entry.get("summary"), 180)
            topic_key = _text(entry.get("topicKey"))
            if not TOPIC_KEY_PATTERN.fullmatch(topic_key):
                errors.append(f"{label} requires a stable topicKey")
            related = [_text(value) for value in (entry.get("relatedModuleIds") or []) if _text(value)]
            if not related:
                errors.append(f"{label} requires relatedModuleIds")
            elif any(module_id not in module_by_id for module_id in related):
                errors.append(f"{label} contains unresolved relatedModuleIds")
            elif any(_text(module_by_id[module_id].get("topicKey")) != topic_key for module_id in related):
                errors.append(f"{label} topicKey does not match its related module")
            else:
                classified_module_ids.extend(related)
                if any(_text((module_by_id[module_id].get("history") or {}).get("state")) != key for module_id in related):
                    errors.append(f"{label} does not match related module history.state")
            if key != "new" and not _text(entry.get("previousReportId")):
                errors.append(f"{label} requires previousReportId")
            if key == "new" and _text(entry.get("previousReportId")):
                errors.append(f"{label} must not reference previousReportId")
            if related and all(module_id in module_by_id for module_id in related):
                module_previous_ids = {
                    _text((module_by_id[module_id].get("history") or {}).get("previousReportId"))
                    for module_id in related
                }
                if module_previous_ids != {_text(entry.get("previousReportId"))}:
                    errors.append(f"{label} previousReportId does not match its related module")
            _validate_evidence(errors, label, entry, source_by_id)

    for module_id in module_ids:
        count = classified_module_ids.count(module_id)
        if count != 1:
            errors.append(f"module {module_id} must appear in exactly one change signal")

    executive = report.get("executiveSummary") or {}
    for field in ("headline", "summary"):
        if not _text(executive.get(field)):
            errors.append(f"executiveSummary.{field} is required")
    _limit(errors, "executiveSummary.headline", executive.get("headline"), 60)
    _limit(errors, "executiveSummary.summary", executive.get("summary"), 240)
    _validate_evidence(errors, "executiveSummary", executive, source_by_id)

    actions = report.get("actions") or []
    if not isinstance(actions, list) or not 1 <= len(actions) <= 6:
        errors.append("actions must contain 1-6 items")
        actions = actions if isinstance(actions, list) else []
    for index, action in enumerate(actions):
        for field, maximum in (("title", 40), ("action", 180), ("owner", 60), ("cadence", 80), ("trigger", 120)):
            if not _text(action.get(field)):
                errors.append(f"actions[{index}].{field} is required")
            _limit(errors, f"actions[{index}].{field}", action.get(field), maximum)
        _validate_evidence(errors, f"actions[{index}]", action, source_by_id)

    if errors:
        raise ReportValidationError(errors)
    return report
