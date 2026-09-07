import copy
import subprocess
from pathlib import Path

import pytest

from market_analysis.products import validate_product_research
from market_analysis.validator import ReportValidationError
import run_market_research


def product_report():
    return {
        "productResearch": {"status": "covered", "moduleIds": ["P1"],
                            "searchedThemes": ["分红产品条款", "养老年金产品", "产品上市公告"], "gaps": []},
        "modules": [{"id": "P1", "topicCategory": "product", "section": "peers",
                     "history": {"state": "new"}, "evidenceIds": ["S1"],
                     "productFacts": [{"field": "name", "value": "测试养老年金保险", "evidenceIds": ["S1"]},
                                      {"field": "insurer", "value": "示例人寿", "evidenceIds": ["S1"]}]}],
        "sources": [{"id": "S1", "sourceType": "company", "sourceLevel": "B",
                     "excerpt": "示例人寿测试养老年金保险条款"}],
    }


def test_product_fields_are_evidence_backed():
    validate_product_research(product_report(), required=True)


@pytest.mark.parametrize("mutation,match", [
    (lambda r: r["modules"][0]["productFacts"][0].update(value="另一款产品"), "match a cited"),
    (lambda r: r["sources"][0].update(sourceLevel="C", sourceType="media"), "first-party"),
    (lambda r: r["modules"][0].update(evidenceIds=[]), "module-linked"),
    (lambda r: r["productResearch"].update(moduleIds=[]), "every product module"),
    (lambda r: r["modules"][0].update(productFacts=[]), "name and insurer"),
    (lambda r: r["modules"][0]["history"].update(state="expired"), "current product"),
    (lambda r: r["productResearch"].update(searchedThemes=["相同"] * 3), "three distinct"),
])
def test_rejects_unverified_or_inconsistent_products(mutation, match):
    report = product_report()
    mutation(report)
    with pytest.raises(ReportValidationError, match=match):
        validate_product_research(report, required=True)


def test_honest_evidence_gap_and_legacy_compatibility():
    validate_product_research({})
    with pytest.raises(ReportValidationError, match="required"):
        validate_product_research({}, required=True)
    report = product_report()
    report["modules"] = []
    report["productResearch"].update(status="evidence_gap", moduleIds=[], gaps=["官网条款不可访问，下一期复核同公司披露。"])
    validate_product_research(report, required=True)
    report["productResearch"]["gaps"] = []
    with pytest.raises(ReportValidationError, match="explicit evidence gaps"):
        validate_product_research(report, required=True)


def test_product_gate_does_not_mutate_report():
    report = product_report()
    before = copy.deepcopy(report)
    validate_product_research(report, required=True)
    assert report == before


def test_product_benefits_cannot_drop_negation_or_negative_sign():
    for excerpt, value in [("不保证收益3%", "保证收益3%"), ("演示收益-3%", "演示收益3%")]:
        report = product_report()
        report["sources"].append({"id": "S2", "sourceType": "company", "sourceLevel": "B", "excerpt": excerpt})
        report["modules"][0]["evidenceIds"].append("S2")
        fact = {"field": "guaranteedBenefits", "value": value, "evidenceIds": ["S2"]}
        report["modules"][0]["productFacts"].append(fact)
        with pytest.raises(ReportValidationError, match="match a cited"):
            validate_product_research(report, required=True)
        fact["value"] = excerpt
        validate_product_research(report, required=True)


def test_missing_product_module_id_is_repairable_validation_error():
    report = product_report()
    extra = copy.deepcopy(report["modules"][0])
    extra.pop("id")
    report["modules"].append(extra)
    with pytest.raises(ReportValidationError, match="every product module"):
        validate_product_research(report, required=True)


def test_product_contract_in_main_and_repair_and_discovery():
    for prompt in [run_market_research.build_prompt({}, [], []),
                   run_market_research.build_repair_prompt({}, [], {}, [])]:
        assert "productResearch" in prompt
        assert "guaranteedBenefits" in prompt
        assert "nonGuaranteedBenefits" in prompt
        assert "IRR" in prompt
        assert "evidence_gap" in prompt
    assert "three of the query themes" in run_market_research.build_source_scout_prompt([], [])


def test_production_gate_cannot_omit_product_coverage(monkeypatch, tmp_path):
    from market_analysis.repository import MarketAnalysisRepository
    monkeypatch.setenv("MARKET_ANALYSIS_REQUIRE_PRODUCT_RESEARCH", "1")
    with pytest.raises(ReportValidationError, match="productResearch"):
        run_market_research.validate_draft({}, MarketAnalysisRepository(tmp_path))


def test_product_failure_never_overwrites_published_report(monkeypatch, tmp_path):
    import market_analysis.repository as repository_module
    repo = repository_module.MarketAnalysisRepository(tmp_path)
    previous = b'{"reportId":"previous-valid-report"}'
    (tmp_path / "latest.json").write_bytes(previous)
    monkeypatch.setenv("MARKET_ANALYSIS_REQUIRE_PRODUCT_RESEARCH", "1")
    monkeypatch.setattr(repository_module, "validate_report", lambda report: None)
    with pytest.raises(ReportValidationError, match="productResearch"):
        repo.publish({"reportId": "market-new"})
    assert (tmp_path / "latest.json").read_bytes() == previous
    assert not (tmp_path / "reports").exists()


def test_market_history_async_ui_regressions():
    result = subprocess.run(
        ["node", "--test", str(Path(__file__).with_name("market_history_ui.test.cjs"))],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_verified_excerpt_change_withholds_optional_claim_without_weakening_identity():
    from market_analysis.products import omit_unverified_optional_product_facts
    report = product_report()
    report['sources'][0]['verification'] = {'status': 'verified'}
    report['modules'][0]['productFacts'].append({'field': 'saleStatus', 'value': '在售', 'evidenceIds': ['S1']})
    omit_unverified_optional_product_facts(report)
    validate_product_research(report, required=True)
    assert len(report['modules'][0]['productFacts']) == 2
    assert '销售状态未通过核验' in report['productResearch']['gaps'][0]
    report['modules'][0]['productFacts'][0]['value'] = '错误产品'
    omit_unverified_optional_product_facts(report)
    with pytest.raises(ReportValidationError):
        validate_product_research(report, required=True)


def test_budget_exhaustion_is_readable_and_never_auto_retried(monkeypatch):
    import json
    monkeypatch.setattr(run_market_research.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], 1, json.dumps({'subtype': 'error_max_budget_usd'}), ''))
    with pytest.raises(run_market_research.ModelBudgetExceeded, match='已停止自动重试'):
        run_market_research.invoke_claude('claude', 'prompt', model='test', max_turns='1', max_budget='3', timeout_seconds=1)
    monkeypatch.setattr(run_market_research.sys, 'argv', ['run_market_research.py'])
    def fail(*a, **k):
        raise run_market_research.ModelBudgetExceeded('budget stopped')
    monkeypatch.setattr(run_market_research, 'run_research', fail)
    assert run_market_research.main() == 2
