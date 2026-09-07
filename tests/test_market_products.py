import copy

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
