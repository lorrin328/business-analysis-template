import copy
import json
import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from main import app
from market_analysis.repository import MarketAnalysisRepository
from market_analysis.source_verifier import SourceVerificationError, _ensure_public_url, _published_at_matches, _title_matches
from market_analysis.validator import ReportValidationError, validate_report
import run_market_research
from run_market_research import parse_claude_result, redact


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

    broken = copy.deepcopy(second)
    broken["reportId"] = "market-20260728-120000"
    broken["generatedAt"] = "2026-07-28T12:00:00+08:00"
    broken["modules"][0]["history"]["previousReportId"] = "market-does-not-exist"
    broken["changeSignals"]["persistent"][0]["previousReportId"] = "market-does-not-exist"
    with pytest.raises(ReportValidationError, match="previous report does not exist"):
        repository.publish(broken)


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


def test_claude_result_parser_and_secret_redaction():
    report = valid_report()
    envelope = {"type": "result", "result": __import__("json").dumps(report, ensure_ascii=False)}
    assert parse_claude_result(__import__("json").dumps(envelope, ensure_ascii=False))["reportId"] == report["reportId"]
    assert "sk-example-secret-value" not in redact("token=sk-example-secret-value")


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
    assert "research_context" in captured["input"]
    assert captured["input"] not in " ".join(captured["command"])


def test_source_verifier_rejects_private_and_credentialed_urls():
    with pytest.raises(SourceVerificationError):
        _ensure_public_url("http://127.0.0.1/admin")
    with pytest.raises(SourceVerificationError):
        _ensure_public_url("https://user:password@example.com/source")
    assert _title_matches("2026年保险业经营情况", "2026年保险业经营情况 - 国家金融监督管理总局")
    assert not _title_matches("保险业经营情况", "网站登录验证")
    assert _published_at_matches("2026-07-21T09:00:00+08:00", "发布时间：2026年7月21日")
    assert not _published_at_matches("2026-07-21", "发布时间：2026年7月20日")


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
    assert "executiveEvidence" in page
    assert "entries.slice(0, 3)" in script
    assert "innerHTML" not in script
    assert 'data-permission="market_analysis"' in dashboard
    assert "location = /market-analysis.html" in nginx


def test_market_timer_runs_every_three_days_and_template_has_no_secret():
    timer = open(os.path.join(ROOT, "deploy", "market-analysis.timer"), "r", encoding="utf-8").read()
    env_template = open(os.path.join(ROOT, "deploy", "market-analysis.env.example"), "r", encoding="utf-8").read()
    service = open(os.path.join(ROOT, "deploy", "market-analysis.service"), "r", encoding="utf-8").read()
    assert "OnUnitActiveSec=3d" in timer
    assert "Persistent=true" in timer
    assert "ANTHROPIC_AUTH_TOKEN=\n" in env_template
    assert "AI_READONLY_TOKEN=\n" in env_template
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=strict" in service
