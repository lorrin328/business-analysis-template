from __future__ import annotations

import hashlib
import os
import re
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

from market_analysis.validator import ReportValidationError, validate_report


FIRST_PARTY_TYPES = {"official", "company", "official_wechat", "association"}
ACTION_STATES = {"new", "continuing", "adjusted", "completed"}
ACTION_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
OBSERVABLE_TERMS = {
    "若", "当", "连续", "达到", "超过", "高于", "低于", "上升", "下降", "回升", "回落",
    "增长", "减少", "发布", "生效", "实施", "披露", "停止", "恢复", "月", "日", "%",
}


def _text(value) -> str:
    return str(value or "").strip()


def _normalized(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", _text(value).lower())


def legacy_action_key(action: dict) -> str:
    seed = "|".join((_normalized(action.get("owner")), _normalized(action.get("title"))))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"legacy-{digest}"


def action_for_context(action: dict, report_id: str | None) -> dict:
    row = dict(action or {})
    row["actionKey"] = _text(row.get("actionKey")) or legacy_action_key(row)
    row.setdefault("status", "legacy")
    row.setdefault("previousReportId", None)
    row["reportId"] = report_id
    return row


def action_ledger(repository, limit: int = 100) -> list[dict]:
    ledger: dict[str, dict] = {}
    for item in reversed(repository.history(limit=limit)):
        report_id = _text(item.get("reportId"))
        report = repository.get(report_id) or {}
        for action in report.get("actions") or []:
            row = action_for_context(action, report_id)
            ledger[row["actionKey"]] = row
    return list(ledger.values())


def reconcile_action_metadata(report: dict, ledger: list[dict]) -> None:
    known = {_text(row.get("actionKey")): row for row in ledger if _text(row.get("actionKey"))}
    for action in report.get("actions") or []:
        key = _text(action.get("actionKey"))
        previous = known.get(key)
        if previous:
            action["previousReportId"] = previous.get("reportId")
            if _text(action.get("status")) not in {"continuing", "adjusted", "completed"}:
                action["status"] = "continuing"
        else:
            action["previousReportId"] = None
            action["status"] = "new"


def _action_similarity(left: dict, right: dict) -> float:
    left_text = _normalized(f"{left.get('title', '')}{left.get('action', '')}")
    right_text = _normalized(f"{right.get('title', '')}{right.get('action', '')}")
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def action_continuity_errors(report: dict, repository) -> list[str]:
    errors: list[str] = []
    ledger = action_ledger(repository)
    known = {_text(row.get("actionKey")): row for row in ledger if _text(row.get("actionKey"))}
    latest = repository.latest() or {}
    latest_actions = [action_for_context(row, latest.get("reportId")) for row in latest.get("actions") or []]
    source_by_id = {_text(source.get("id")): source for source in report.get("sources") or []}
    seen: set[str] = set()
    period_end = None
    try:
        period_end = date.fromisoformat(_text((report.get("period") or {}).get("end")))
    except ValueError:
        pass

    for index, action in enumerate(report.get("actions") or []):
        label = f"actions[{index}]"
        key = _text(action.get("actionKey"))
        if not ACTION_KEY_PATTERN.fullmatch(key):
            errors.append(f"{label}.actionKey must be a stable lowercase slug")
            continue
        if key in seen:
            errors.append(f"duplicate actionKey: {key}")
        seen.add(key)
        status = _text(action.get("status"))
        if status not in ACTION_STATES:
            errors.append(f"{label}.status must be new/continuing/adjusted/completed")
        previous = known.get(key)
        previous_id = _text(action.get("previousReportId"))
        if previous:
            if status == "new":
                errors.append(f"{label} existing actionKey cannot be classified as new")
            if previous_id != _text(previous.get("reportId")):
                errors.append(f"{label}.previousReportId must reference the latest action occurrence")
            old_progress = _normalized(previous.get("progress"))
            new_progress = _normalized(action.get("progress"))
            if old_progress and new_progress and old_progress == new_progress:
                errors.append(f"{label}.progress must update the prior action rather than repeat it")
        else:
            if status != "new" or previous_id:
                errors.append(f"{label} new actionKey must use status=new without previousReportId")
            repeated = [row for row in latest_actions if _action_similarity(action, row) >= 0.86]
            if repeated:
                errors.append(f"{label} appears to repeat a prior action; reuse its stable actionKey")

        if status == "completed":
            if not any(
                _text(source_by_id.get(evidence_id, {}).get("sourceType")) == "internal"
                for evidence_id in action.get("evidenceIds") or []
            ):
                errors.append(f"{label} completed status requires internal evidence")
        try:
            next_review = date.fromisoformat(_text(action.get("nextReviewAt")))
        except ValueError:
            next_review = None
        if not next_review:
            errors.append(f"{label}.nextReviewAt must be YYYY-MM-DD")
        elif period_end and (next_review < period_end or next_review > period_end + timedelta(days=31)):
            errors.append(f"{label}.nextReviewAt must be within 31 days after period.end")
    return errors


def _sources(report: dict) -> tuple[dict[str, dict], list[dict]]:
    rows = [row for row in report.get("sources") or [] if isinstance(row, dict)]
    return {_text(row.get("id")): row for row in rows if _text(row.get("id"))}, rows


def _section_evidence(report: dict, section: str) -> set[str]:
    return {
        _text(evidence_id)
        for module in report.get("modules") or []
        if _text(module.get("section")) == section
        for evidence_id in module.get("evidenceIds") or []
        if _text(evidence_id)
    }


def _peer_modules_have_first_party(report: dict, source_by_id: dict[str, dict]) -> bool:
    peer_modules = [row for row in report.get("modules") or [] if _text(row.get("section")) == "peers"]
    return bool(peer_modules) and all(
        any(
            _text(source_by_id.get(evidence_id, {}).get("sourceType")) in FIRST_PARTY_TYPES
            and _text(source_by_id.get(evidence_id, {}).get("sourceLevel")) in {"A", "B"}
            for evidence_id in module.get("evidenceIds") or []
        )
        for module in peer_modules
    )


def _observable_watch_ratio(report: dict) -> float:
    modules = report.get("modules") or []
    if not modules:
        return 0.0
    count = 0
    for module in modules:
        value = _text(module.get("watchCondition"))
        if re.search(r"\d", value) or any(term in value for term in OBSERVABLE_TERMS):
            count += 1
    return count / len(modules)


def _new_evidence_ratio(report: dict, repository) -> float:
    source_by_id, _ = _sources(report)
    carried = []
    for module in report.get("modules") or []:
        previous_id = _text((module.get("history") or {}).get("previousReportId"))
        if not previous_id:
            continue
        previous_report = repository.get(previous_id) or {}
        previous_module = next(
            (row for row in previous_report.get("modules") or [] if row.get("topicKey") == module.get("topicKey")),
            None,
        )
        if not previous_module:
            carried.append(False)
            continue
        previous_sources, _ = _sources(previous_report)
        old_urls = {_text(previous_sources.get(eid, {}).get("url")) for eid in previous_module.get("evidenceIds") or []}
        new_urls = {_text(source_by_id.get(eid, {}).get("url")) for eid in module.get("evidenceIds") or []}
        changed = bool(new_urls - old_urls)
        if not changed:
            for evidence_id in module.get("evidenceIds") or []:
                current = source_by_id.get(_text(evidence_id), {})
                url = _text(current.get("url"))
                current_hash = _text(current.get("contentHash"))
                if not url or not current_hash:
                    continue
                for old in previous_sources.values():
                    if _text(old.get("url")) == url and _text(old.get("contentHash")) and _text(old.get("contentHash")) != current_hash:
                        changed = True
                        break
                if changed:
                    break
        carried.append(changed)
    return 1.0 if not carried else sum(carried) / len(carried)


def maturity_draft_errors(report: dict, repository) -> list[str]:
    """Return repairable professional-quality gaps before external source verification."""
    errors: list[str] = []
    source_by_id, sources = _sources(report)
    coverage = report.get("coverage") or {}
    external = [row for row in sources if _text(row.get("sourceType")) != "internal"]
    publishers = {_text(row.get("publisher")) for row in external if _text(row.get("publisher"))}
    domains = {urlparse(_text(row.get("url"))).hostname for row in external if urlparse(_text(row.get("url"))).hostname}
    official = [row for row in sources if _text(row.get("sourceType")) == "official"]
    first_party = [row for row in external if _text(row.get("sourceType")) in FIRST_PARTY_TYPES]
    if int(coverage.get("queryCount") or 0) < 12:
        errors.append("maturity.queryCount requires at least 12 targeted search themes")
    if len(sources) < 12:
        errors.append("maturity.sourceCount requires at least 12 independently verifiable sources")
    if len(official) < 4:
        errors.append("maturity.officialSourceCount requires at least four official sources")
    if len(publishers) < 5:
        errors.append("maturity.sourceDiversity requires at least five external publishers")
    if len(domains) < 5:
        errors.append("maturity.domainDiversity requires at least five external domains")
    if external and len(first_party) / len(external) < 0.5:
        errors.append("maturity.firstPartyRatio requires at least 50% first-party external sources")
    if not _peer_modules_have_first_party(report, source_by_id):
        errors.append("maturity.peers requires A/B-level first-party evidence for every peer module")
    section_counts = {
        section: sum(1 for row in report.get("modules") or [] if _text(row.get("section")) == section)
        for section in ("macro", "regulation", "peers", "business_line")
    }
    if any(count < 2 for count in section_counts.values()) or not 8 <= len(report.get("modules") or []) <= 14:
        errors.append("maturity.moduleDepth requires 2-4 modules per section and 8-14 modules overall")
    if _observable_watch_ratio(report) < 0.8:
        errors.append("maturity.watchConditions requires observable triggers for at least 80% of modules")
    required_action_fields = {
        "actionKey", "status", "progress", "acceptanceMetric", "nextReviewAt", "previousReportId",
    }
    for index, action in enumerate(report.get("actions") or []):
        missing = [field for field in required_action_fields if field not in action or (field != "previousReportId" and not _text(action.get(field)))]
        if missing:
            errors.append(f"actions[{index}] maturity fields missing: {sorted(missing)}")
        if len(_text(action.get("progress"))) < 8 or len(_text(action.get("acceptanceMetric"))) < 6:
            errors.append(f"actions[{index}] requires substantive progress and acceptanceMetric")
    errors.extend(action_continuity_errors(report, repository))
    return list(dict.fromkeys(errors))


def assess_report_quality(report: dict, repository, model_calls: list[dict] | None = None) -> dict:
    source_by_id, sources = _sources(report)
    external = [row for row in sources if _text(row.get("sourceType")) != "internal"]
    publishers = {_text(row.get("publisher")) for row in external if _text(row.get("publisher"))}
    domains = {urlparse(_text(row.get("url"))).hostname for row in external if urlparse(_text(row.get("url"))).hostname}
    official = [row for row in sources if _text(row.get("sourceType")) == "official"]
    first_party = [row for row in external if _text(row.get("sourceType")) in FIRST_PARTY_TYPES]
    checks: list[dict] = []
    dimensions: dict[str, dict] = {
        "evidence": {"key": "evidence", "label": "证据完整性", "score": 0.0, "maxScore": 3.0},
        "coverage": {"key": "coverage", "label": "来源权威与覆盖", "score": 0.0, "maxScore": 2.0},
        "rolling": {"key": "rolling", "label": "滚动分析质量", "score": 0.0, "maxScore": 2.0},
        "actions": {"key": "actions", "label": "行动闭环", "score": 0.0, "maxScore": 2.0},
        "operations": {"key": "operations", "label": "运行可靠性", "score": 0.0, "maxScore": 1.0},
    }

    def add(dimension: str, key: str, label: str, maximum: float, passed: bool, detail: str) -> None:
        awarded = maximum if passed else 0.0
        dimensions[dimension]["score"] += awarded
        checks.append({"key": key, "label": label, "passed": bool(passed), "score": awarded, "maxScore": maximum, "detail": detail})

    verified = all(
        (row.get("verification") or {}).get("status") == ("internal" if row.get("sourceType") == "internal" else "verified")
        and (row.get("verification") or {}).get("excerptMatched") is True
        for row in sources
    )
    try:
        validate_report(report, require_verified_sources=True)
        anchored = True
    except ReportValidationError:
        anchored = False
    macro_official = any(
        source_by_id.get(eid, {}).get("sourceType") == "official" and source_by_id.get(eid, {}).get("sourceLevel") == "A"
        for eid in _section_evidence(report, "macro")
    )
    regulation_official = any(
        source_by_id.get(eid, {}).get("sourceType") == "official" and source_by_id.get(eid, {}).get("sourceLevel") == "A"
        for eid in _section_evidence(report, "regulation")
    )
    add("evidence", "verified_sources", "来源独立复核", 1.0, verified, f"{sum(1 for row in sources if (row.get('verification') or {}).get('excerptMatched') is True)}/{len(sources)}")
    add("evidence", "fact_anchors", "事实锚点匹配", 0.75, anchored, "全部模块事实须与已核验原文片段匹配")
    add("evidence", "macro_regulation_a", "宏观监管A级证据", 0.75, macro_official and regulation_official, f"宏观={macro_official}，监管={regulation_official}")
    peer_ok = _peer_modules_have_first_party(report, source_by_id)
    add("evidence", "peer_first_party_each", "同业逐模块一手证据", 0.5, peer_ok, "每个同业模块均须有A/B级一手来源")

    query_count = int((report.get("coverage") or {}).get("queryCount") or 0)
    add("coverage", "query_depth", "检索主题深度", 0.4, query_count >= 12, f"{query_count}/12")
    add("coverage", "source_volume", "有效来源规模", 0.4, len(sources) >= 12, f"{len(sources)}/12")
    add("coverage", "publisher_diversity", "发布主体多样性", 0.4, len(publishers) >= 5, f"{len(publishers)}/5")
    add("coverage", "domain_diversity", "来源域名多样性", 0.4, len(domains) >= 5, f"{len(domains)}/5")
    ratio = len(first_party) / len(external) if external else 0.0
    add("coverage", "authority_floor", "一手与官方来源底线", 0.4, ratio >= 0.5 and len(official) >= 4, f"一手占比{ratio:.0%}，官方{len(official)}项")

    new_evidence_ratio = _new_evidence_ratio(report, repository)
    module_ids = {_text(row.get("id")) for row in report.get("modules") or []}
    classified = [
        _text(module_id)
        for entries in (report.get("changeSignals") or {}).values()
        for row in entries or []
        for module_id in row.get("relatedModuleIds") or []
    ]
    classifications_ok = all(classified.count(module_id) == 1 for module_id in module_ids)
    watch_ratio = _observable_watch_ratio(report)
    section_counts = {
        section: sum(1 for row in report.get("modules") or [] if _text(row.get("section")) == section)
        for section in ("macro", "regulation", "peers", "business_line")
    }
    depth_ok = all(count >= 2 for count in section_counts.values()) and 8 <= len(report.get("modules") or []) <= 14
    add("rolling", "new_evidence", "延续主题新增证据", 0.8, new_evidence_ratio >= 1.0, f"覆盖率{new_evidence_ratio:.0%}")
    add("rolling", "classification_integrity", "变化分类唯一映射", 0.4, classifications_ok, f"模块{len(module_ids)}项")
    add("rolling", "observable_watch", "可观测复核条件", 0.4, watch_ratio >= 0.8, f"覆盖率{watch_ratio:.0%}")
    add("rolling", "module_depth", "四层分析深度", 0.4, depth_ok, str(section_counts))

    actions = report.get("actions") or []
    action_fields_ok = bool(actions) and all(
        ACTION_KEY_PATTERN.fullmatch(_text(row.get("actionKey")))
        and _text(row.get("status")) in ACTION_STATES
        and _text(row.get("progress"))
        and _text(row.get("acceptanceMetric"))
        for row in actions
    )
    continuity_errors = action_continuity_errors(report, repository)
    period_end = date.fromisoformat(_text((report.get("period") or {}).get("end")))
    review_dates_ok = True
    for row in actions:
        try:
            next_review = date.fromisoformat(_text(row.get("nextReviewAt")))
        except ValueError:
            review_dates_ok = False
            break
        review_dates_ok = review_dates_ok and period_end <= next_review <= period_end + timedelta(days=31)
    substantive = bool(actions) and all(len(_text(row.get("progress"))) >= 8 and len(_text(row.get("acceptanceMetric"))) >= 6 for row in actions)
    add("actions", "accountability_fields", "责任闭环字段", 0.6, action_fields_ok, f"{len(actions)}项行动")
    add("actions", "action_continuity", "跨期行动连续性", 0.5, not continuity_errors, "；".join(continuity_errors[:2]) or "通过")
    add("actions", "review_dates", "复核日期有效", 0.3, review_dates_ok, "复核日期不超过31天")
    add("actions", "progress_acceptance", "进度与验收标准", 0.6, substantive, "每项行动均含进度和验收指标")

    calls = list(model_calls or [])
    primary_success = any(row.get("role") == "primary" and row.get("status") == "success" for row in calls)
    telemetry_ok = bool(calls) and all(row.get("role") and row.get("model") and isinstance(row.get("elapsedMs"), int) for row in calls)
    repairs = [row for row in calls if str(row.get("role") or "").startswith("repair")]
    escalated = any(row.get("role") == "repair_escalation" for row in calls)
    add("operations", "primary_completion", "主研究调用完成", 0.4, primary_success, f"调用{len(calls)}次")
    add("operations", "model_telemetry", "模型调用可观测", 0.2, telemetry_ok, "角色、模型和耗时已记录")
    reliability_points = 0.4 if not repairs else (0.2 if not escalated else 0.0)
    dimensions["operations"]["score"] += reliability_points
    checks.append({
        "key": "first_pass_reliability",
        "label": "首次成稿可靠性",
        "passed": not repairs,
        "score": reliability_points,
        "maxScore": 0.4,
        "detail": "首次通过" if not repairs else ("首次修复后通过" if not escalated else "升级修复后通过"),
    })

    dimension_rows = []
    for row in dimensions.values():
        row["score"] = round(row["score"], 2)
        dimension_rows.append(row)
    score = round(sum(row["score"] for row in dimension_rows), 2)
    minimum = float(os.getenv("MARKET_ANALYSIS_MIN_QUALITY_SCORE", "0") or 0)
    return {
        "score": score,
        "minimumScore": minimum,
        "status": "passed" if score >= minimum else "failed",
        "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "dimensions": dimension_rows,
        "checks": checks,
    }
