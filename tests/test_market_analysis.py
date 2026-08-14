import copy
import json
import os
import subprocess

import pytest
from fastapi.testclient import TestClient

import api.market_analysis as market_analysis_api
from auth import get_current_user
from main import app
from market_analysis.repository import MarketAnalysisRepository
from market_analysis.source_verifier import SourceVerificationError, _ensure_public_url, _open_pinned, _published_at_matches, _title_matches, align_module_facts_to_verified_excerpts, verify_report_sources
from market_analysis.validator import ReportValidationError, validate_report
import run_market_research
from run_market_research import (
    clamp_source_excerpts,
    parse_claude_result,
    prune_redundant_failed_sources,
    reconcile_change_signals,
    reconcile_derived_metadata,
    reconcile_history_metadata,
    redact,
    repair_model_for_attempt,
    resolve_model_plan,
    topic_ledger,
)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def valid_report(report_id="market-20260722-120000"):
    source_template = {
        "publishedAt": "2026-07-21T09:00:00+08:00",
        "retrievedAt": "2026-07-22T12:00:00+08:00",
        "excerpt": "用于测试的短事实摘要",
        "contentHash": "a" * 64,
        "verification": {"status": "verified", "contentHash": "a" * 64, "verifiedAt": "2026-07-22T12:00:00+08:00", "excerptMatched": True, "publishedAtMatched": True, "httpStatus": 200, "contentType": "text/html", "bytesRead": 1024},
    }
    sources = [
        {**source_template, "id": "S1", "title": "宏观数据", "publisher": "国家统计部门", "url": "https://www.stats.gov.cn/macro", "sourceType": "official", "sourceLevel": "A"},
        {**source_template, "id": "S2", "title": "监管文件", "publisher": "金融监管部门", "url": "https://www.gov.cn/policy", "sourceType": "official", "sourceLevel": "A"},
        {**source_template, "id": "S3", "title": "同业动作", "publisher": "某保险公司", "url": "https://example.com/company", "sourceType": "company", "sourceLevel": "B"},
        {**source_template, "id": "S4", "title": "内部经营快照", "publisher": "经营分析看板", "url": "internal://dashboard-snapshot/2026", "sourceType": "internal", "sourceLevel": "A", "publishedAt": None, "verification": {"status": "internal", "contentHash": "a" * 64, "verifiedAt": "2026-07-22T12:00:00+08:00", "excerptMatched": True}},
        {**source_template, "id": "S5", "title": "宏观交叉数据", "publisher": "中国人民银行", "url": "https://www.pbc.gov.cn/macro-2", "sourceType": "official", "sourceLevel": "A"},
        {**source_template, "id": "S6", "title": "政策解读", "publisher": "行业协会", "url": "https://example.org/policy-note", "sourceType": "association", "sourceLevel": "B"},
        {**source_template, "id": "S7", "title": "同业公告", "publisher": "另一保险公司", "url": "https://example.com/company-2", "sourceType": "company", "sourceLevel": "B"},
        {**source_template, "id": "S8", "title": "市场研究", "publisher": "研究机构", "url": "https://example.org/research", "sourceType": "research", "sourceLevel": "C"},
    ]
    for source in sources:
        if source["sourceType"] != "internal":
            source["verification"] = {**source["verification"], "finalUrl": source["url"]}
    modules = []
    for index, (section, source_id) in enumerate((("macro", "S1"), ("regulation", "S2"), ("peers", "S3"), ("business_line", "S4")), start=1):
        modules.append({
            "id": f"M{index}",
            "topicKey": f"{section}-trend",
            "section": section,
            "title": f"{section} 单一判断",
            "question": "本期发生了什么变化？",
            "fact": "用于测试的短事实摘要。",
            "judgment": "基于该事实形成的有限判断。",
            "impact": "对条线的影响需要按触发条件观察。",
            "watchCondition": "下一次官方数据或制度生效后复核。",
            "confidence": "high" if section in {"macro", "regulation"} else "medium",
            "evidenceIds": [source_id],
            "history": {"state": "new", "since": "2026-07-22", "previousReportId": None},
        })
    return {
        "schemaVersion": "1.0",
        "reportId": report_id,
        "title": "寿险市场滚动研判",
        "generatedAt": "2026-07-22T12:00:00+08:00",
        "period": {"start": "2026-07-19", "end": "2026-07-22"},
        "model": {"provider": "DeepSeek", "name": "deepseek-v4-pro[1m]"},
        "reviewStatus": "machine_validated",
        "coverage": {"queryCount": 12, "sourceCount": 8, "officialSourceCount": 3, "wechatSourceCount": 0, "limitations": []},
        "executiveSummary": {"headline": "测试主判断", "summary": "测试摘要", "evidenceIds": ["S1", "S2"]},
        "changeSignals": {
            "persistent": [], "strengthened": [], "reversed": [],
            "new": [
                {"topicKey": "macro-trend", "title": "宏观新增判断", "summary": "出现新的可验证信号", "relatedModuleIds": ["M1"], "previousReportId": None, "evidenceIds": ["S1"]},
                {"topicKey": "regulation-trend", "title": "监管新增判断", "summary": "出现新的可验证信号", "relatedModuleIds": ["M2"], "previousReportId": None, "evidenceIds": ["S2"]},
                {"topicKey": "peers-trend", "title": "同业新增判断", "summary": "出现新的可验证信号", "relatedModuleIds": ["M3"], "previousReportId": None, "evidenceIds": ["S3"]},
                {"topicKey": "business_line-trend", "title": "条线新增判断", "summary": "出现新的可验证信号", "relatedModuleIds": ["M4"], "previousReportId": None, "evidenceIds": ["S4"]},
            ],
            "expired": [],
        },
        "modules": modules,
        "actions": [{"priority": "P1", "title": "跟踪政策", "action": "建立政策清单", "owner": "业发督导室", "cadence": "每3天", "trigger": "新规发布", "evidenceIds": ["S2"]}],
        "sources": sources,
        "limitations": [],
    }


def test_report_validator_accepts_complete_atomic_modules():
    report = valid_report()
    assert validate_report(report) is report


def test_report_validator_rejects_uncited_and_missing_layer():
    report = valid_report()
    report["modules"] = report["modules"][:-1]
    report["modules"][0]["evidenceIds"] = ["MISSING"]
    with pytest.raises(ReportValidationError) as exc:
        validate_report(report)
    assert "unresolved evidenceIds" in str(exc.value)
    assert "section business_line requires" in str(exc.value)


def test_change_signal_requires_evidence_and_resolved_module():
    report = valid_report()
    report["changeSignals"]["new"][0]["evidenceIds"] = []
    report["changeSignals"]["new"][0]["relatedModuleIds"] = ["UNKNOWN"]
    with pytest.raises(ReportValidationError) as exc:
        validate_report(report)
    assert "requires evidenceIds" in str(exc.value)
    assert "unresolved relatedModuleIds" in str(exc.value)


def test_verified_fact_must_match_exact_source_excerpt():
    report = valid_report()
    report["modules"][0]["fact"] = "完全无关且没有正文支持的事实。"
    with pytest.raises(ReportValidationError, match="fact is not supported"):
        validate_report(report)

    report = valid_report()
    report["sources"][0]["verification"]["excerptMatched"] = False
    with pytest.raises(ReportValidationError, match="verified excerpt match"):
        validate_report(report)


def test_repository_keeps_latest_when_new_report_fails(tmp_path):
    repository = MarketAnalysisRepository(tmp_path)
    first = valid_report()
    repository.publish(first)
    invalid = copy.deepcopy(first)
    invalid["reportId"] = "market-20260722-130000"
    invalid["modules"][0]["evidenceIds"] = []
    with pytest.raises(ReportValidationError):
        repository.publish(invalid)
    assert repository.latest()["reportId"] == first["reportId"]
    assert repository.history()[0]["moduleCount"] == 4


def test_repository_validates_cross_period_topic_links_and_builds_timeline(tmp_path):
    repository = MarketAnalysisRepository(tmp_path)
    first = valid_report()
    repository.publish(first)
    second = copy.deepcopy(first)
    second["reportId"] = "market-20260725-120000"
    second["generatedAt"] = "2026-07-25T12:00:00+08:00"
    second["period"] = {"start": "2026-07-22", "end": "2026-07-25"}
    for module in second["modules"]:
        module["history"] = {"state": "persistent", "since": "2026-07-22", "previousReportId": first["reportId"]}
    second["changeSignals"]["new"] = []
    second["changeSignals"]["persistent"] = [
        {
            "topicKey": module["topicKey"], "title": f"{module['section']}持续判断", "summary": "新证据继续支持",
            "relatedModuleIds": [module["id"]], "previousReportId": first["reportId"], "evidenceIds": module["evidenceIds"],
        }
        for module in second["modules"]
    ]
    repository.publish(second)
    timeline = repository.topic_timeline("macro-trend")
    assert [item["reportId"] for item in timeline] == [first["reportId"], second["reportId"]]
    assert run_market_research.history_context(repository)[0]["actions"]

    broken = copy.deepcopy(second)
    broken["reportId"] = "market-20260728-120000"
    broken["generatedAt"] = "2026-07-28T12:00:00+08:00"
    broken["modules"][0]["history"]["previousReportId"] = "market-does-not-exist"
    broken["changeSignals"]["persistent"][0]["previousReportId"] = "market-does-not-exist"
    with pytest.raises(ReportValidationError, match="previous report does not exist"):
        repository.publish(broken)


def test_worker_reconciles_trusted_history_metadata_before_validation(tmp_path):
    repository = MarketAnalysisRepository(tmp_path)
    first = valid_report()
    repository.publish(first)
    second = copy.deepcopy(first)
    second["reportId"] = "market-20260725-120000"
    second["generatedAt"] = "2026-07-25T12:00:00+08:00"
    second["period"] = {"start": "2026-07-22", "end": "2026-07-25"}
    second["changeSignals"]["new"] = []
    second["changeSignals"]["persistent"] = []
    for module in second["modules"]:
        module["history"] = {
            "state": "persistent",
            "since": "2026-07-25",
            "previousReportId": "market-wrong",
        }
        second["changeSignals"]["persistent"].append({
            "topicKey": module["topicKey"],
            "title": f"{module['section']}持续判断",
            "summary": "新证据继续支持",
            "relatedModuleIds": [module["id"]],
            "previousReportId": "market-wrong",
            "evidenceIds": module["evidenceIds"],
        })

    reconcile_history_metadata(second, topic_ledger(repository))

    assert all(module["history"]["since"] == "2026-07-22" for module in second["modules"])
    assert all(module["history"]["previousReportId"] == first["reportId"] for module in second["modules"])
    assert all(entry["previousReportId"] == first["reportId"] for entry in second["changeSignals"]["persistent"])
    repository.publish(second)


def test_change_signals_are_rebuilt_from_module_history_states():
    report = valid_report()
    report["changeSignals"]["expired"] = [
        {
            "topicKey": "macro-trend", "title": "错误失效", "summary": "不应保留",
            "relatedModuleIds": ["M1"], "previousReportId": "market-old", "evidenceIds": ["S1"],
        },
        {
            "topicKey": "peers-trend", "title": "重复失效", "summary": "不应保留",
            "relatedModuleIds": ["M3"], "previousReportId": "market-old", "evidenceIds": ["S3"],
        },
    ]
    report["changeSignals"]["new"] = report["changeSignals"]["new"][:2]

    reconcile_change_signals(report)

    assert report["changeSignals"]["expired"] == []
    classified = [
        module_id
        for state in run_market_research.CHANGE_KEYS
        for entry in report["changeSignals"][state]
        for module_id in entry["relatedModuleIds"]
    ]
    assert classified == ["M1", "M2", "M3", "M4"]
    assert validate_report(report) is report


def test_change_signal_reconciliation_preserves_a_current_expired_module():
    report = valid_report()
    module = report["modules"][2]
    module["history"] = {
        "state": "expired",
        "since": "2026-07-19",
        "previousReportId": "market-20260719-120000",
    }
    report["changeSignals"]["expired"] = [{
        "topicKey": module["topicKey"],
        "title": "同业信号已失效",
        "summary": "当前一手证据表明原判断不再成立",
        "relatedModuleIds": [module["id"]],
        "previousReportId": module["history"]["previousReportId"],
        "evidenceIds": module["evidenceIds"],
    }]

    reconcile_change_signals(report)

    expired = report["changeSignals"]["expired"]
    assert len(expired) == 1
    assert expired[0]["relatedModuleIds"] == ["M3"]
    assert expired[0]["previousReportId"] == "market-20260719-120000"
    assert expired[0]["evidenceIds"] == ["S3"]
    assert validate_report(report) is report


def test_derived_coverage_counts_and_module_title_are_normalized():
    report = valid_report()
    report["coverage"].update({"sourceCount": 99, "officialSourceCount": 99, "wechatSourceCount": 99})
    report["modules"][0]["title"] = "标题" * 25
    report["modules"][0]["impact"] = "影响" * 100
    report["executiveSummary"]["headline"] = "摘要" * 40
    report["actions"][0]["title"] = "行动" * 25
    report["sources"][0]["excerpt"] = "用于测试的短事实摘要" * 8

    reconcile_derived_metadata(report)
    reconcile_change_signals(report)

    assert report["coverage"]["sourceCount"] == 8
    assert report["coverage"]["officialSourceCount"] == 3
    assert report["coverage"]["wechatSourceCount"] == 0
    assert len(report["modules"][0]["title"]) == 40
    assert len(report["modules"][0]["impact"]) == 180
    assert len(report["executiveSummary"]["headline"]) == 60
    assert len(report["actions"][0]["title"]) == 40
    assert len(report["sources"][0]["excerpt"]) == 50
    assert validate_report(report) is report


def test_redundant_failed_source_is_pruned_without_weakening_peer_evidence():
    report = valid_report()
    extra = copy.deepcopy(report["sources"][-1])
    extra["id"] = "S9"
    extra["url"] = "https://example.org/research-backup"
    extra["verification"]["finalUrl"] = extra["url"]
    report["sources"].append(extra)
    report["modules"][2]["evidenceIds"] = ["S3", "S8"]
    reconcile_derived_metadata(report)
    reconcile_change_signals(report)

    removed = prune_redundant_failed_sources(
        report, "source S8 failed independent verification: source returned HTTP 404"
    )

    assert removed == ["S8"]
    assert len(report["sources"]) == 8
    assert report["modules"][2]["evidenceIds"] == ["S3"]
    assert report["changeSignals"]["new"][2]["evidenceIds"] == ["S3"]
    assert report["coverage"]["sourceCount"] == 8
    assert validate_report(report) is report


def test_failed_source_is_not_pruned_when_it_is_the_only_module_evidence():
    report = valid_report()
    extra = copy.deepcopy(report["sources"][-1])
    extra["id"] = "S9"
    extra["url"] = "https://example.org/research-backup"
    extra["verification"]["finalUrl"] = extra["url"]
    report["sources"].append(extra)
    reconcile_derived_metadata(report)

    removed = prune_redundant_failed_sources(
        report, "source S4 failed independent verification: unavailable"
    )

    assert removed == []
    assert any(source["id"] == "S4" for source in report["sources"])


def test_research_prompt_requires_a_current_module_for_expired_signals():
    prompt = run_market_research.build_prompt({"year": 2026}, [], [])
    repair_prompt = run_market_research.build_repair_prompt(valid_report(), [], {"year": 2026}, [])
    assert "Never emit an expired signal without a current module" in prompt
    assert "Never add an expired signal unless that current module" in repair_prompt


def test_market_analysis_api_exposes_latest_history_and_status(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_ANALYSIS_DATA_DIR", str(tmp_path))
    repository = MarketAnalysisRepository(tmp_path)
    report = valid_report()
    repository.publish(report)
    repository.write_status({"state": "success", "message": "ok", "updatedAt": report["generatedAt"]})
    client = TestClient(app)

    latest = client.get("/api/market-analysis/latest")
    assert latest.status_code == 200
    assert latest.json()["data"]["reportId"] == report["reportId"]
    assert client.get("/api/market-analysis/history").json()["data"][0]["sourceCount"] == 8
    assert client.get(f"/api/market-analysis/reports/{report['reportId']}").status_code == 200
    assert client.get("/api/market-analysis/topics/macro-trend").json()["data"][0]["reportId"] == report["reportId"]
    assert client.get("/api/market-analysis/status").json()["data"]["state"] == "success"
    assert client.get("/api/market-analysis/reports/not-found").status_code == 404


def test_admin_can_queue_one_manual_market_run(tmp_path, monkeypatch):
    trigger_file = tmp_path / "trigger" / "request"
    trigger_file.parent.mkdir()
    monkeypatch.setenv("MARKET_ANALYSIS_TRIGGER_FILE", str(trigger_file))
    monkeypatch.setattr(market_analysis_api, "log_operation", lambda *args, **kwargs: None)
    client = TestClient(app)

    response = client.post("/api/market-analysis/run")
    assert response.status_code == 202
    assert response.json()["data"]["state"] == "queued"
    assert json.loads(trigger_file.read_text(encoding="utf-8"))["requestedAt"]

    duplicate = client.post("/api/market-analysis/run")
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "已有手动运行请求正在排队"


def test_manual_market_run_requires_installed_trigger(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_ANALYSIS_TRIGGER_FILE", str(tmp_path / "missing" / "request"))
    monkeypatch.setattr(market_analysis_api, "log_operation", lambda *args, **kwargs: None)
    response = TestClient(app).post("/api/market-analysis/run")
    assert response.status_code == 503
    assert response.json()["detail"] == "手动运行触发器尚未安装"


def test_manual_market_run_requires_admin(tmp_path, monkeypatch):
    trigger_file = tmp_path / "trigger" / "request"
    trigger_file.parent.mkdir()
    monkeypatch.setenv("MARKET_ANALYSIS_TRIGGER_FILE", str(trigger_file))
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 9,
        "username": "viewer",
        "role": "normal",
        "permissions": {"market_analysis": True},
    }
    try:
        response = TestClient(app).post("/api/market-analysis/run")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert not trigger_file.exists()


def test_claude_result_parser_and_secret_redaction():
    report = valid_report()
    envelope = {"type": "result", "result": __import__("json").dumps(report, ensure_ascii=False)}
    assert parse_claude_result(__import__("json").dumps(envelope, ensure_ascii=False))["reportId"] == report["reportId"]
    wrapped = {"type": "result", "result": f"<think>已完成核验</think>\n```json\n{json.dumps(report, ensure_ascii=False)}\n```"}
    assert parse_claude_result(json.dumps(wrapped, ensure_ascii=False))["reportId"] == report["reportId"]
    assert "sk-example-secret-value" not in redact("token=sk-example-secret-value")


def test_model_plan_uses_pro_for_primary_flash_for_first_repair_and_pro_for_escalation(monkeypatch):
    for key in (
        "MARKET_ANALYSIS_MODEL", "MARKET_ANALYSIS_PRIMARY_MODEL",
        "MARKET_ANALYSIS_REPAIR_MODEL", "MARKET_ANALYSIS_ESCALATION_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    plan = resolve_model_plan()
    assert plan["primary"] == "deepseek-v4-pro[1m]"
    assert plan["repair"] == "deepseek-v4-flash"
    assert plan["escalation"] == "deepseek-v4-pro[1m]"
    assert repair_model_for_attempt(plan, 0) == ("deepseek-v4-flash", "repair_flash")
    assert repair_model_for_attempt(plan, 1) == ("deepseek-v4-pro[1m]", "repair_escalation")


def test_dry_run_reports_model_plan_without_overwriting_runtime_status(tmp_path, monkeypatch):
    repository = MarketAnalysisRepository(tmp_path)
    previous_status = {"state": "success", "message": "keep", "updatedAt": "2026-08-14T01:00:00+08:00"}
    repository.write_status(previous_status)
    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026})

    result = run_market_research.run_research(repository, dry_run=True)

    assert result["modelPlan"]["primary"] == "deepseek-v4-pro[1m]"
    assert result["modelPlan"]["repair"] == "deepseek-v4-flash"
    assert repository.status() == previous_status


def test_long_source_excerpt_is_clamped_to_best_fact_window():
    report = valid_report()
    report["modules"][3]["fact"] = "内部快照显示2026年期交保费123.45万元"
    internal = next(source for source in report["sources"] if source["id"] == "S4")
    internal["excerpt"] = "无关背景" * 20 + "内部快照显示2026年期交保费123.45万元，业务保持稳定"
    clamp_source_excerpts(report)
    assert len(internal["excerpt"]) <= 50
    assert "2026年期交保费123.45万元" in internal["excerpt"]


def test_worker_passes_private_context_over_stdin_and_restricts_tools(tmp_path, monkeypatch):
    captured = {}
    model_report = valid_report()

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"result": json.dumps(model_report, ensure_ascii=False)}), stderr="")

    def fake_verify(report, **kwargs):
        verified_at = run_market_research.now_iso()
        for source in report["sources"]:
            source["retrievedAt"] = verified_at
            source["verification"]["verifiedAt"] = verified_at
        return report

    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026, "kpi": {"qj": 1}})
    monkeypatch.setattr(run_market_research.shutil, "which", lambda value: "/usr/local/bin/claude")
    monkeypatch.setattr(run_market_research.subprocess, "run", fake_run)
    monkeypatch.setattr(run_market_research, "verify_report_sources", fake_verify)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-token")

    result = run_market_research.run_research(MarketAnalysisRepository(tmp_path))
    assert result["reviewStatus"] == "machine_validated"
    assert captured["command"][0] == "/usr/local/bin/claude"
    assert "Read" not in captured["command"]
    assert "WebSearch" in captured["command"] and "WebFetch" in captured["command"]
    schema_index = captured["command"].index("--json-schema") + 1
    assert json.loads(captured["command"][schema_index])["properties"]["sources"]["minItems"] == 8
    assert "research_context" in captured["input"]
    assert captured["input"] not in " ".join(captured["command"])


def test_worker_runs_bounded_evidence_repair_before_publication(tmp_path, monkeypatch):
    invalid_report = valid_report()
    invalid_report["modules"][1]["evidenceIds"] = ["S3"]
    invalid_report["modules"][2]["evidenceIds"] = ["S8"]
    repaired_report = valid_report()
    prompts = []
    models = []

    def fake_run(command, **kwargs):
        prompts.append(kwargs.get("input"))
        models.append(command[command.index("--model") + 1])
        payload = invalid_report if len(prompts) == 1 else repaired_report
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"result": json.dumps(payload, ensure_ascii=False)}), stderr="")

    def fake_verify(report, **kwargs):
        verified_at = run_market_research.now_iso()
        for source in report["sources"]:
            source["retrievedAt"] = verified_at
            source["verification"]["verifiedAt"] = verified_at
        return report

    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026})
    monkeypatch.setattr(run_market_research.shutil, "which", lambda value: "/usr/local/bin/claude")
    monkeypatch.setattr(run_market_research.subprocess, "run", fake_run)
    monkeypatch.setattr(run_market_research, "verify_report_sources", fake_verify)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-token")

    result = run_market_research.run_research(MarketAnalysisRepository(tmp_path))
    assert result["reviewStatus"] == "machine_validated"
    assert len(prompts) == 2
    assert models == ["deepseek-v4-pro[1m]", "deepseek-v4-flash"]
    assert "validationErrors" in prompts[1]
    assert "Regulation modules must cite" in prompts[1]
    assert "internalBusinessSnapshot" in prompts[1]


def test_worker_allows_second_targeted_repair_for_peer_first_party_evidence(tmp_path, monkeypatch):
    invalid_peer = valid_report()
    for source_id in ("S3", "S7"):
        source = next(source for source in invalid_peer["sources"] if source["id"] == source_id)
        source["sourceType"] = "research"
        source["sourceLevel"] = "C"
    repaired_report = valid_report()
    payloads = [invalid_peer, invalid_peer, repaired_report]
    prompts = []
    models = []

    def fake_run(command, **kwargs):
        prompts.append(kwargs.get("input"))
        models.append(command[command.index("--model") + 1])
        payload = copy.deepcopy(payloads[len(prompts) - 1])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"result": json.dumps(payload, ensure_ascii=False)}),
            stderr="",
        )

    def fake_verify(report, **kwargs):
        verified_at = run_market_research.now_iso()
        for source in report["sources"]:
            source["retrievedAt"] = verified_at
            source["verification"]["verifiedAt"] = verified_at
        return report

    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026})
    monkeypatch.setattr(run_market_research.shutil, "which", lambda value: "/usr/local/bin/claude")
    monkeypatch.setattr(run_market_research.subprocess, "run", fake_run)
    monkeypatch.setattr(run_market_research, "verify_report_sources", fake_verify)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-token")
    monkeypatch.setenv("MARKET_ANALYSIS_MAX_REPAIR_ATTEMPTS", "2")

    result = run_market_research.run_research(MarketAnalysisRepository(tmp_path))

    assert result["reviewStatus"] == "machine_validated"
    assert len(prompts) == 3
    assert models == ["deepseek-v4-pro[1m]", "deepseek-v4-flash", "deepseek-v4-pro[1m]"]
    assert "section peers requires A/B-level first-party evidence" in prompts[1]
    assert "authoritativeTopicLedger" in prompts[1]
    assert "replace that peer module" in prompts[1]


def test_worker_repairs_unprunable_source_in_same_run_with_flash(tmp_path, monkeypatch):
    draft = valid_report()
    repaired = valid_report()
    prompts = []
    models = []
    verification_calls = 0

    def fake_run(command, **kwargs):
        prompts.append(kwargs.get("input"))
        models.append(command[command.index("--model") + 1])
        payload = draft if len(prompts) == 1 else repaired
        envelope = {
            "type": "result", "subtype": "success", "num_turns": 2,
            "duration_api_ms": 1000, "total_cost_usd": 0.1,
            "usage": {"input_tokens": 100, "output_tokens": 50, "server_tool_use": {}},
            "result": json.dumps(payload, ensure_ascii=False),
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(envelope, ensure_ascii=False), stderr="")

    def fake_verify(report, **kwargs):
        nonlocal verification_calls
        verification_calls += 1
        if verification_calls == 1:
            raise SourceVerificationError("source S3 failed independent verification: source returned HTTP 404")
        verified_at = run_market_research.now_iso()
        for source in report["sources"]:
            source["retrievedAt"] = verified_at
            source["verification"]["verifiedAt"] = verified_at
        return report

    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026})
    monkeypatch.setattr(run_market_research.shutil, "which", lambda value: "/usr/local/bin/claude")
    monkeypatch.setattr(run_market_research.subprocess, "run", fake_run)
    monkeypatch.setattr(run_market_research, "verify_report_sources", fake_verify)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-token")

    repository = MarketAnalysisRepository(tmp_path)
    result = run_market_research.run_research(repository)

    assert result["reviewStatus"] == "machine_validated"
    assert verification_calls == 2
    assert models == ["deepseek-v4-pro[1m]", "deepseek-v4-flash"]
    assert "source S3 failed independent verification" in prompts[1]
    status = repository.status()
    assert [call["role"] for call in status["modelCalls"]] == ["primary", "repair_flash"]
    assert status["modelPlan"]["strategy"] == "pro_primary_flash_first_repair_pro_escalation"


def test_private_repair_checkpoint_is_resumable_and_clearable(tmp_path):
    repository = MarketAnalysisRepository(tmp_path)
    report = valid_report()
    repository.write_repair_checkpoint(stage="repair", report=report, errors=["evidence repair required"])
    checkpoint = repository.repair_checkpoint()
    assert checkpoint["stage"] == "repair"
    assert checkpoint["report"]["reportId"] == report["reportId"]
    assert checkpoint["errors"] == ["evidence repair required"]
    repository.clear_repair_checkpoint()
    assert repository.repair_checkpoint() is None


def test_metadata_only_checkpoint_skips_another_model_call(tmp_path, monkeypatch):
    repository = MarketAnalysisRepository(tmp_path)
    report = valid_report()
    repository.write_repair_checkpoint(
        stage="repair",
        report=report,
        errors=["source S1 evidence excerpt was not found in the source body"],
    )

    def fake_verify(candidate, **kwargs):
        verified_at = run_market_research.now_iso()
        for source in candidate["sources"]:
            source["retrievedAt"] = verified_at
            source["verification"]["verifiedAt"] = verified_at
        return candidate

    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026})
    monkeypatch.setattr(run_market_research.shutil, "which", lambda value: "/usr/local/bin/claude")
    monkeypatch.setattr(run_market_research.subprocess, "run", lambda *args, **kwargs: pytest.fail("model should not run"))
    monkeypatch.setattr(run_market_research, "verify_report_sources", fake_verify)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-token")
    result = run_market_research.run_research(repository)
    assert result["reviewStatus"] == "machine_validated"
    assert repository.repair_checkpoint() is None


def test_change_signal_checkpoint_is_reconciled_without_another_model_call(tmp_path, monkeypatch):
    repository = MarketAnalysisRepository(tmp_path)
    report = valid_report()
    report["changeSignals"]["new"] = report["changeSignals"]["new"][:2]
    report["coverage"].update({"sourceCount": 99, "officialSourceCount": 99})
    report["modules"][2]["title"] = "同业标题" * 12
    report["changeSignals"]["expired"] = [
        {
            "topicKey": "macro-trend", "title": "错误失效", "summary": "状态冲突",
            "relatedModuleIds": ["M1"], "previousReportId": "market-old", "evidenceIds": ["S1"],
        },
        {
            "topicKey": "macro-trend", "title": "重复失效", "summary": "重复映射",
            "relatedModuleIds": ["M1"], "previousReportId": "market-old", "evidenceIds": ["S1"],
        },
    ]
    repository.write_repair_checkpoint(
        stage="repair",
        report=report,
        errors=[
            "changeSignals.expired[0] does not match related module history.state",
            "module M3 must appear in exactly one change signal",
            "coverage.sourceCount must equal the number of sources",
            "coverage.officialSourceCount does not match sources",
            "module M3.title exceeds 40 characters",
        ],
    )

    def fake_verify(candidate, **kwargs):
        verified_at = run_market_research.now_iso()
        for source in candidate["sources"]:
            source["retrievedAt"] = verified_at
            source["verification"]["verifiedAt"] = verified_at
        return candidate

    monkeypatch.setattr(run_market_research, "fetch_internal_snapshot", lambda: {"year": 2026})
    monkeypatch.setattr(run_market_research.shutil, "which", lambda value: "/usr/local/bin/claude")
    monkeypatch.setattr(run_market_research.subprocess, "run", lambda *args, **kwargs: pytest.fail("model should not run"))
    monkeypatch.setattr(run_market_research, "verify_report_sources", fake_verify)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-token")

    result = run_market_research.run_research(repository)

    assert result["reviewStatus"] == "machine_validated"
    assert result["changeSignals"]["expired"] == []
    assert len(result["changeSignals"]["new"]) == 4
    assert result["coverage"]["sourceCount"] == 8
    assert result["coverage"]["officialSourceCount"] == 3
    assert len(result["modules"][2]["title"]) == 40
    assert repository.repair_checkpoint() is None


def test_source_verifier_rejects_private_and_credentialed_urls():
    with pytest.raises(SourceVerificationError):
        _ensure_public_url("http://127.0.0.1/admin")
    with pytest.raises(SourceVerificationError):
        _ensure_public_url("https://user:password@example.com/source")
    assert _title_matches("2026年保险业经营情况", "2026年保险业经营情况 - 国家金融监督管理总局")
    assert not _title_matches("保险业经营情况", "网站登录验证")
    assert _published_at_matches("2026-07-21T09:00:00+08:00", "发布时间：2026年7月21日")
    assert not _published_at_matches("2026-07-21", "发布时间：2026年7月20日")


def test_pinned_source_peer_is_checked_before_connection_close(monkeypatch):
    class FakeSocket:
        def getpeername(self):
            return ("93.184.216.34", 80)

    class FakeHeaders:
        def get_content_charset(self):
            return "utf-8"

    class FakeResponse:
        status = 200
        headers = FakeHeaders()

        def getheader(self, name):
            return "text/plain" if name == "Content-Type" else None

        def read(self, _limit):
            return b"verified body"

    class FakeConnection:
        def __init__(self, *_args, **_kwargs):
            self.sock = None

        def connect(self):
            self.sock = FakeSocket()

        def request(self, *_args, **_kwargs):
            return None

        def getresponse(self):
            self.sock = None
            return FakeResponse()

        def close(self):
            self.sock = None

    monkeypatch.setattr("market_analysis.source_verifier._ensure_public_url", lambda _url: ["93.184.216.34"])
    monkeypatch.setattr("market_analysis.source_verifier.http.client.HTTPConnection", FakeConnection)
    status, content_type, charset, body, final_url = _open_pinned("http://example.com/source", 5, 1024)
    assert (status, content_type, charset, body, final_url) == (
        200, "text/plain", "utf-8", b"verified body", "http://example.com/source"
    )


def test_source_verifier_canonicalizes_metadata_but_keeps_fact_gate(monkeypatch):
    report = valid_report()
    source = report["sources"][0]
    source["title"] = "模型声明的错误标题"
    source["publishedAt"] = "2026-07-20"
    source["excerpt"] = "模型生成但网页中不存在的摘录"
    report["modules"][0]["fact"] = "官方正文确认2026年保费增长12.3%"
    body = "网站导航。官方正文确认2026年保费增长12.3%，并披露统计范围。其他内容。"

    def fake_fetch(_url):
        return {
            "status": "verified",
            "httpStatus": 200,
            "finalUrl": source["url"],
            "pageTitle": "实际网页标题",
            "contentType": "text/html",
            "verifiedAt": "2026-07-22T14:00:00+08:00",
            "contentHash": "b" * 64,
            "bytesRead": len(body.encode("utf-8")),
            "truncated": False,
            "_body": body,
        }

    monkeypatch.setattr("market_analysis.source_verifier._fetch_external", fake_fetch)
    verify_report_sources({"sources": [source], "modules": [report["modules"][0]]}, internal_content_hash="a" * 64, internal_content_text="{}")
    assert source["title"] == "实际网页标题"
    assert source["publishedAt"] is None
    assert "2026年保费增长12.3%" in source["excerpt"]
    assert source["verification"]["excerptMatched"] is True


def test_module_facts_are_aligned_to_the_closest_verified_excerpt():
    report = valid_report()
    report["modules"][0]["fact"] = "官方数据显示2026年保费增长12.3%，趋势进一步增强。"
    report["modules"][0]["evidenceIds"] = ["S1", "S2"]
    report["sources"][0]["excerpt"] = "官方数据显示2026年保费增长12.3%"
    report["sources"][1]["excerpt"] = "另一项无关但已核验的市场事实"

    align_module_facts_to_verified_excerpts(report)

    assert report["modules"][0]["fact"] == "官方数据显示2026年保费增长12.3%"
    validate_report(report)


def test_market_analysis_page_is_modular_and_whitelisted():
    page = open(os.path.join(ROOT, "market-analysis.html"), "r", encoding="utf-8").read()
    script = open(os.path.join(ROOT, "js", "market-analysis.js"), "r", encoding="utf-8").read()
    dashboard = open(os.path.join(ROOT, "经营分析模板.html"), "r", encoding="utf-8").read()
    nginx = open(os.path.join(ROOT, "deploy", "nginx.conf"), "r", encoding="utf-8").read()
    assert "本期变化信号" in page
    assert "四层研判模块" in page
    assert "条线行动提示" in page
    assert "证据与来源" in page
    assert "CHANGE_LABELS" in script
    assert "跨期轨迹" in script
    assert "modelPlanLabel" in script
    assert "模型组合" in script
    assert "executiveEvidence" in page
    assert "entries.slice(0, 3)" in script
    assert "innerHTML" not in script
    assert 'data-permission="market_analysis"' in dashboard
    assert "location = /market-analysis.html" in nginx
    assert 'id="runNowButton"' in page
    assert "user?.role === 'admin'" in script
    assert "api('/api/market-analysis/run', { method: 'POST' })" in script


def test_market_timer_runs_at_1am_when_three_calendar_days_are_due_and_template_has_no_secret():
    timer = open(os.path.join(ROOT, "deploy", "market-analysis.timer"), "r", encoding="utf-8").read()
    env_template = open(os.path.join(ROOT, "deploy", "market-analysis.env.example"), "r", encoding="utf-8").read()
    service = open(os.path.join(ROOT, "deploy", "market-analysis.service"), "r", encoding="utf-8").read()
    scheduled_service = open(os.path.join(ROOT, "deploy", "market-analysis-scheduled.service"), "r", encoding="utf-8").read()
    scheduler = open(os.path.join(ROOT, "deploy", "market-analysis-schedule.sh"), "r", encoding="utf-8").read()
    installer = open(os.path.join(ROOT, "deploy", "install-market-analysis.sh"), "r", encoding="utf-8").read()
    configurator = open(os.path.join(ROOT, "deploy", "configure-market-analysis.sh"), "r", encoding="utf-8").read()
    trigger = open(os.path.join(ROOT, "deploy", "market-analysis-trigger.sh"), "r", encoding="utf-8").read()
    trigger_service = open(os.path.join(ROOT, "deploy", "market-analysis-manual.service"), "r", encoding="utf-8").read()
    trigger_path = open(os.path.join(ROOT, "deploy", "market-analysis-manual.path"), "r", encoding="utf-8").read()
    assert "OnCalendar=*-*-* 01:00:00" in timer
    assert "AccuracySec=1min" in timer
    assert "RandomizedDelaySec=0" in timer
    assert "Unit=market-analysis-scheduled.service" in timer
    assert "Persistent=true" in timer
    assert "ExecStart=/usr/local/sbin/business-analysis-market-schedule" in scheduled_service
    assert "NoNewPrivileges=true" in scheduled_service
    assert "ReadOnlyPaths=/var/lib/business-analysis-market" in scheduled_service
    assert 'timedelta(days=3)' in scheduler
    assert 'ZoneInfo("Asia/Shanghai")' in scheduler
    assert 'SYSTEMCTL_BIN="${MARKET_ANALYSIS_SYSTEMCTL:-/usr/bin/systemctl}"' in scheduler
    assert '"$SYSTEMCTL_BIN" start --no-block "$SERVICE_NAME"' in scheduler
    assert "ANTHROPIC_AUTH_TOKEN=\n" in env_template
    assert "AI_READONLY_TOKEN=\n" in env_template
    assert "ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash" in env_template
    assert "CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash" in env_template
    assert "MARKET_ANALYSIS_PRIMARY_MODEL=deepseek-v4-pro[1m]" in env_template
    assert "MARKET_ANALYSIS_REPAIR_MODEL=deepseek-v4-flash" in env_template
    assert "MARKET_ANALYSIS_ESCALATION_MODEL=deepseek-v4-pro[1m]" in env_template
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=strict" in service
    assert "Restart=on-failure" in service
    assert "StartLimitBurst=2" in service
    assert "tr -d '\\r'" in installer
    assert "ensure_env_value ANTHROPIC_DEFAULT_HAIKU_MODEL 'deepseek-v4-flash'" in installer
    assert "ensure_env_value MARKET_ANALYSIS_REPAIR_MODEL 'deepseek-v4-flash'" in installer
    assert "ensure_env_value MARKET_ANALYSIS_ESCALATION_MODEL 'deepseek-v4-pro[1m]'" in installer
    assert "apt-get install -y curl ca-certificates nodejs npm" not in installer
    assert "@anthropic-ai/claude-code@latest" in installer
    assert "set +x" in configurator
    assert "read -r -s" in configurator
    assert "openssl rand -hex 32" in configurator
    assert configurator.index("/api/health") < configurator.index("systemctl start --no-block market-analysis.service")
    assert "market-analysis-manual.path" in installer
    assert "market-analysis-scheduled.service" in installer
    assert "business-analysis-market-schedule" in installer
    assert "sudoers" not in installer
    assert "COOLDOWN_SECONDS=300" in trigger
    assert 'LOCK_FILE="$STATE_DIR/trigger.lock"' in trigger
    assert "systemctl start --no-block" in trigger
    assert "NoNewPrivileges=true" in trigger_service
    assert "PathExists=/run/business-analysis-market-trigger/request" in trigger_path
