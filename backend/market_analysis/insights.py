from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from statistics import median
from urllib.parse import urlparse


FIRST_PARTY_TYPES = {"official", "company", "official_wechat", "association"}
RUNTIME_CALL_FIELDS = (
    "role",
    "model",
    "status",
    "elapsedMs",
    "numTurns",
    "durationApiMs",
    "cliEstimatedCostUsd",
    "inputTokens",
    "outputTokens",
    "cacheReadInputTokens",
    "webSearchRequests",
    "webFetchRequests",
)


def _text(value) -> str:
    return str(value or "").strip()


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _datetime(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


def _date(value) -> date | None:
    try:
        return date.fromisoformat(_text(value))
    except (TypeError, ValueError):
        return None


def _counter_dict(values) -> dict[str, int]:
    return dict(sorted(Counter(_text(value) for value in values if _text(value)).items()))


def _evidence_references(report: dict) -> Counter:
    references: Counter = Counter()

    def collect(item) -> None:
        if not isinstance(item, dict):
            return
        for evidence_id in item.get("evidenceIds") or []:
            if _text(evidence_id):
                references[_text(evidence_id)] += 1

    collect(report.get("executiveSummary"))
    for entries in (report.get("changeSignals") or {}).values():
        for item in entries or []:
            collect(item)
    for item in report.get("modules") or []:
        collect(item)
    for item in report.get("actions") or []:
        collect(item)
    return references


def build_runtime_assessment(
    started_at: str,
    finished_at: str,
    model_calls: list[dict] | None,
    source_scout: dict | None,
) -> dict:
    calls = [
        {key: row.get(key) for key in RUNTIME_CALL_FIELDS if row.get(key) is not None}
        for row in (model_calls or [])
        if isinstance(row, dict)
    ]
    started = _datetime(started_at)
    finished = _datetime(finished_at)
    elapsed_ms = None
    if started and finished:
        elapsed_ms = max(0, round((finished - started).total_seconds() * 1000))
    repair_calls = [row for row in calls if _text(row.get("role")).startswith("repair")]
    primary_succeeded = any(
        row.get("role") == "primary" and row.get("status") == "success" for row in calls
    )
    return {
        "startedAt": started_at,
        "finishedAt": finished_at,
        "elapsedMs": elapsed_ms,
        "firstPassSuccess": bool(primary_succeeded and not repair_calls),
        "repairCount": len(repair_calls),
        "escalated": any(row.get("role") == "repair_escalation" for row in calls),
        "modelCallCount": len(calls),
        "cliEstimatedCostUsd": round(sum(_number(row.get("cliEstimatedCostUsd")) for row in calls), 4),
        "inputTokens": int(sum(_number(row.get("inputTokens")) for row in calls)),
        "outputTokens": int(sum(_number(row.get("outputTokens")) for row in calls)),
        "webSearchRequests": int(sum(_number(row.get("webSearchRequests")) for row in calls)),
        "webFetchRequests": int(sum(_number(row.get("webFetchRequests")) for row in calls)),
        "sourceScout": dict(source_scout or {}),
        "modelCalls": calls,
    }


def build_report_metrics(report: dict) -> dict:
    sources = [row for row in report.get("sources") or [] if isinstance(row, dict)]
    external = [row for row in sources if _text(row.get("sourceType")) != "internal"]
    references = _evidence_references(report)
    source_by_id = {_text(row.get("id")): row for row in sources if _text(row.get("id"))}
    cited_ids = {source_id for source_id, count in references.items() if count > 0 and source_id in source_by_id}
    top_sources = []
    for source_id, count in sorted(references.items(), key=lambda item: (-item[1], item[0]))[:5]:
        source = source_by_id.get(source_id)
        if not source:
            continue
        top_sources.append({
            "id": source_id,
            "publisher": source.get("publisher"),
            "sourceType": source.get("sourceType"),
            "sourceLevel": source.get("sourceLevel"),
            "referenceCount": count,
        })
    verified_count = sum(
        1
        for row in sources
        if (row.get("verification") or {}).get("status")
        == ("internal" if row.get("sourceType") == "internal" else "verified")
        and (row.get("verification") or {}).get("excerptMatched") is True
    )
    first_party_count = sum(1 for row in external if _text(row.get("sourceType")) in FIRST_PARTY_TYPES)
    zhihu_count = sum(
        1
        for row in external
        if (urlparse(_text(row.get("url"))).hostname or "").lower().endswith("zhihu.com")
    )
    modules = [row for row in report.get("modules") or [] if isinstance(row, dict)]
    actions = [row for row in report.get("actions") or [] if isinstance(row, dict)]
    change_signals = report.get("changeSignals") or {}
    return {
        "sourceContribution": {
            "sourceCount": len(sources),
            "citedSourceCount": len(cited_ids),
            "citationCount": sum(references.values()),
            "citationCoverageRate": round(len(cited_ids) / len(sources), 4) if sources else 0.0,
            "verifiedSourceRate": round(verified_count / len(sources), 4) if sources else 0.0,
            "firstPartyExternalRate": round(first_party_count / len(external), 4) if external else 0.0,
            "sourceTypeCounts": _counter_dict(row.get("sourceType") for row in sources),
            "sourceLevelCounts": _counter_dict(row.get("sourceLevel") for row in sources),
            "publisherCount": len({_text(row.get("publisher")) for row in external if _text(row.get("publisher"))}),
            "domainCount": len({
                (urlparse(_text(row.get("url"))).hostname or "").lower()
                for row in external
                if urlparse(_text(row.get("url"))).hostname
            }),
            "wechatSourceCount": sum(1 for row in sources if row.get("sourceType") == "official_wechat"),
            "zhihuSourceCount": zhihu_count,
            "topSources": top_sources,
        },
        "decisionTracking": {
            "moduleCount": len(modules),
            "signalCounts": {
                key: len(change_signals.get(key) or [])
                for key in ("persistent", "strengthened", "reversed", "new", "expired")
            },
            "confidenceCounts": _counter_dict(row.get("confidence") for row in modules),
            "carriedTopicCount": sum(
                1 for row in modules if _text((row.get("history") or {}).get("state")) != "new"
            ),
            "changedTopicCount": sum(
                1
                for row in modules
                if _text((row.get("history") or {}).get("state")) in {"strengthened", "reversed", "expired"}
            ),
            "actionStatusCounts": _counter_dict(row.get("status") for row in actions),
            "actionCount": len(actions),
        },
    }


def research_observability(repository, *, limit: int = 6, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    rows: list[dict] = []
    verified_sources = 0
    all_sources = 0
    contribution_rates: list[float] = []
    first_pass_values: list[bool] = []
    escalation_values: list[bool] = []
    durations: list[float] = []
    costs: list[float] = []
    quality_scores: list[float] = []

    for item in repository.history(limit=limit):
        report = repository.get(_text(item.get("reportId"))) or {}
        metrics = report.get("researchMetrics") or build_report_metrics(report)
        source_metrics = metrics.get("sourceContribution") or {}
        runtime = report.get("runtimeAssessment") or {}
        quality = report.get("qualityAssessment") or {}
        source_count = int(source_metrics.get("sourceCount") or 0)
        verified_rate = _number(source_metrics.get("verifiedSourceRate"))
        verified_sources += round(source_count * verified_rate)
        all_sources += source_count
        contribution_rates.append(_number(source_metrics.get("citationCoverageRate")))
        quality_score = _number(quality.get("score"))
        if quality_score:
            quality_scores.append(quality_score)
        if isinstance(runtime.get("firstPassSuccess"), bool):
            first_pass_values.append(runtime["firstPassSuccess"])
            escalation_values.append(bool(runtime.get("escalated")))
        if runtime.get("elapsedMs") is not None:
            durations.append(_number(runtime.get("elapsedMs")) / 60000)
        if runtime.get("cliEstimatedCostUsd") is not None:
            costs.append(_number(runtime.get("cliEstimatedCostUsd")))
        rows.append({
            "reportId": report.get("reportId"),
            "generatedAt": report.get("generatedAt"),
            "qualityScore": quality.get("score"),
            "firstPassSuccess": runtime.get("firstPassSuccess"),
            "escalated": runtime.get("escalated"),
            "durationMinutes": round(_number(runtime.get("elapsedMs")) / 60000, 1)
            if runtime.get("elapsedMs") is not None else None,
            "cliEstimatedCostUsd": runtime.get("cliEstimatedCostUsd"),
            "sourceCount": source_count,
            "verifiedSourceRate": source_metrics.get("verifiedSourceRate"),
            "citationCoverageRate": source_metrics.get("citationCoverageRate"),
            "wechatSourceCount": source_metrics.get("wechatSourceCount", 0),
            "zhihuSourceCount": source_metrics.get("zhihuSourceCount", 0),
        })

    run_rows = repository.run_history(limit=max(limit * 3, limit)) if hasattr(repository, "run_history") else []
    if not run_rows and hasattr(repository, "status"):
        status = repository.status() or {}
        if status.get("state") in {"success", "failed"} and status.get("startedAt") and status.get("updatedAt"):
            runtime = status.get("runtimeAssessment") or build_runtime_assessment(
                status.get("startedAt"),
                status.get("updatedAt"),
                status.get("modelCalls") or [],
                status.get("sourceScout") or {},
            )
            run_rows = [{
                "state": status.get("state"),
                "startedAt": status.get("startedAt"),
                "finishedAt": status.get("updatedAt"),
                "reportId": status.get("reportId"),
                "runtimeAssessment": runtime,
            }]
    if run_rows:
        first_pass_values = []
        escalation_values = []
        durations = []
        costs = []
        for run in run_rows:
            runtime = run.get("runtimeAssessment") or {}
            first_pass_values.append(
                bool(run.get("state") == "success" and runtime.get("firstPassSuccess") is True)
            )
            escalation_values.append(bool(runtime.get("escalated")))
            if runtime.get("elapsedMs") is not None:
                durations.append(_number(runtime.get("elapsedMs")) / 60000)
            if runtime.get("cliEstimatedCostUsd") is not None:
                costs.append(_number(runtime.get("cliEstimatedCostUsd")))

    latest = repository.latest() or {}
    actions = [row for row in latest.get("actions") or [] if isinstance(row, dict)]
    active_actions = [row for row in actions if _text(row.get("status")) != "completed"]
    due_actions = [row for row in active_actions if (_date(row.get("nextReviewAt")) or date.max) <= as_of]
    upcoming_actions = [
        row
        for row in active_actions
        if as_of < (_date(row.get("nextReviewAt")) or date.max) <= as_of + timedelta(days=7)
    ]
    observed = len(first_pass_values)
    return {
        "window": {
            "targetCycles": 6,
            "availableCycles": len(rows),
            "runtimeObservedCycles": observed,
            "runAttemptCount": len(run_rows) if run_rows else observed,
            "asOf": as_of.isoformat(),
        },
        "summary": {
            "averageQualityScore": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else None,
            "firstPassSuccessRate": round(sum(first_pass_values) / observed, 4) if observed else None,
            "firstPassTarget": 0.8,
            "proEscalationRate": round(sum(escalation_values) / observed, 4) if observed else None,
            "runSuccessRate": round(
                sum(1 for row in run_rows if row.get("state") == "success") / len(run_rows), 4
            ) if run_rows else None,
            "failedRunCount": sum(1 for row in run_rows if row.get("state") == "failed"),
            "medianDurationMinutes": round(median(durations), 1) if durations else None,
            "averageCliEstimatedCostUsd": round(sum(costs) / len(costs), 4) if costs else None,
            "verifiedSourceRate": round(verified_sources / all_sources, 4) if all_sources else None,
            "averageCitationCoverageRate": round(sum(contribution_rates) / len(contribution_rates), 4)
            if contribution_rates else None,
        },
        "actions": {
            "total": len(actions),
            "active": len(active_actions),
            "completed": len(actions) - len(active_actions),
            "due": len(due_actions),
            "dueWithin7Days": len(upcoming_actions),
        },
        "reports": rows,
    }
