"""Evidence-backed product coverage for newly generated research; old reports stay readable."""
from __future__ import annotations

from market_analysis.validator import ReportValidationError


PRODUCT_FIELDS = {
    "name": "产品名称", "insurer": "保险公司", "insuranceType": "保险责任类型",
    "benefitMechanism": "利益机制", "channel": "适用渠道", "saleStatus": "销售状态",
    "paymentTerm": "缴费期间", "insurancePeriod": "保险期间",
    "guaranteedBenefits": "合同保证利益", "nonGuaranteedBenefits": "非保证利益",
}

PRODUCT_RESEARCH_RULES = """
Life-insurance product research is mandatory in every new report:
- Search product terms, product disclosures, official launch/withdrawal notices and dividend disclosures from named life insurers. Cover annuity/whole-life/health responsibilities separately from participating/universal/traditional benefit mechanisms. Reserve at least three query themes for products, including participating products and pension/annuity products; record actual searched themes in productResearch.searchedThemes.
- Include 1-2 product-focused peers modules when first-party evidence is available. Set topicCategory=product and use a stable product topicKey. Explain relevance to 经代、OTO、证保、蚁桥 using evidence and the internal snapshot, without assuming a fixed channel/product allocation.
- Each product module has productFacts: an array of {field,value,evidenceIds}. Allowed field keys: name, insurer, insuranceType, benefitMechanism, channel, saleStatus, paymentTerm, insurancePeriod, guaranteedBenefits, nonGuaranteedBenefits. name and insurer are required. EVERY value must be an exact <=120-character fragment present in the cited <=50-character source excerpts; add separate source anchors if necessary. All product-fact evidenceIds must also be in the module evidenceIds. Use only directly supporting A/B official/company/association/verified official WeChat evidence. Omit unknown fields, never infer parameters from a product name or promotional slogan.
- Except for name and insurer, copy the ENTIRE cited excerpt as the field value, retaining negation, signs, conditions and non-guaranteed qualifiers. Do not extract a positive substring from a negative or conditional statement. Choose a complete short sentence as the source anchor.
- Separate guaranteed contract benefits, non-guaranteed illustrations, assumptions and realized dividends. Never equate pricing rate, sum-assured growth, payout rate or dividend realization rate with customer IRR. Do not calculate IRR without complete dated cashflows and a named scenario. An old launch notice does not prove current availability. Distinguish contractual coverage from service rights. Do not invent NBV, CSM, fees, product returns or current sale status.
- Add productResearch={status:covered|evidence_gap,moduleIds:[...],searchedThemes:[...],gaps:[...]}. covered requires at least one current non-expired product module; list every product module exactly once in moduleIds. If no product can be independently verified, use evidence_gap, empty moduleIds and a concrete explanation of missing documents/access and the next verification step in gaps. Lack of fresh changes alone is not lack of evidence: a still-valid product may be carried forward only with an updated implication or approaching review trigger. Never manufacture products to fill a quota. Keep all four existing sections and the original module count limits.
"""


def validate_product_research(report: dict, *, required: bool = False) -> None:
    coverage = report.get("productResearch")
    modules = [m for m in report.get("modules", []) if isinstance(m, dict)]
    product_modules = [m for m in modules if m.get("topicCategory") == "product"]
    if coverage is None and not required and not product_modules:
        return
    errors = []
    if not isinstance(coverage, dict):
        raise ReportValidationError(["productResearch is required for new product research"])
    themes = coverage.get("searchedThemes")
    if not isinstance(themes, list) or len({s.strip() for s in themes if isinstance(s, str) and s.strip()}) < 3:
        errors.append("productResearch.searchedThemes requires at least three distinct product searches")
    gaps = coverage.get("gaps")
    if not isinstance(gaps, list) or any(not isinstance(g, str) or not g.strip() for g in gaps):
        errors.append("productResearch.gaps must be a list of nonempty explanations")
    ids = coverage.get("moduleIds")
    expected = [m.get("id") for m in product_modules]
    if (not isinstance(ids, list) or any(not isinstance(i, str) for i in ids)
            or any(not isinstance(i, str) or not i for i in expected)
            or len(set(expected)) != len(expected) or sorted(ids) != sorted(expected)):
        errors.append("productResearch.moduleIds must list every product module exactly once")
    status = coverage.get("status")
    if status == "covered":
        if not any((m.get("history") or {}).get("state") != "expired" for m in product_modules):
            errors.append("covered product research requires a current product module")
    elif status == "evidence_gap":
        if product_modules or ids != [] or not gaps:
            errors.append("product evidence_gap requires no product modules and explicit evidence gaps")
    else:
        errors.append("productResearch.status must be covered or evidence_gap")
    sources = {s.get("id"): s for s in report.get("sources", []) if isinstance(s, dict)}
    for module in product_modules:
        label = f"product module {module.get('id')}"
        if module.get("section") != "peers":
            errors.append(f"{label} must belong to peers")
        facts = module.get("productFacts")
        if not isinstance(facts, list):
            errors.append(f"{label} requires productFacts")
            continue
        seen = set()
        for fact in facts:
            if not isinstance(fact, dict):
                errors.append(f"{label} productFacts item must be an object")
                continue
            key, value, refs = fact.get("field"), fact.get("value"), fact.get("evidenceIds")
            if not isinstance(key, str) or key not in PRODUCT_FIELDS or key in seen:
                errors.append(f"{label} has invalid or duplicate product field")
                continue
            seen.add(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                errors.append(f"{label}.{key} requires a short exact source fragment")
                continue
            if not isinstance(refs, list) or not refs or any(not isinstance(r, str) for r in refs):
                errors.append(f"{label}.{key} requires evidenceIds")
                continue
            supported = []
            for ref in refs:
                source = sources.get(ref, {})
                if ref not in (module.get("evidenceIds") or []) or source.get("sourceLevel") not in {"A", "B"} or source.get("sourceType") not in {"official", "company", "association", "official_wechat"}:
                    errors.append(f"{label}.{key} requires module-linked first-party evidence")
                else:
                    supported.append("".join(str(source.get("excerpt") or "").split()))
            normalized = "".join(value.split())
            matches = any(normalized in excerpt if key in {"name", "insurer"}
                          else normalized == excerpt for excerpt in supported)
            if not normalized or not matches:
                errors.append(f"{label}.{key} must match a cited first-party excerpt exactly")
        if not {"name", "insurer"}.issubset(seen):
            errors.append(f"{label} requires verified name and insurer")
    if errors:
        raise ReportValidationError(errors)


def omit_unverified_optional_product_facts(report: dict) -> None:
    """Verification may replace an excerpt; withhold optional claims it no longer supports."""
    sources = {s.get("id"): s for s in report.get("sources", []) if isinstance(s, dict)}
    coverage = report.get("productResearch")
    if not isinstance(coverage, dict) or not isinstance(coverage.get("gaps"), list):
        return
    for module in report.get("modules", []):
        if module.get("topicCategory") != "product" or not isinstance(module.get("productFacts"), list):
            continue
        kept = []
        for fact in module["productFacts"]:
            key = fact.get("field") if isinstance(fact, dict) else None
            refs = fact.get("evidenceIds") if isinstance(fact, dict) else None
            # Preserve required/malformed claims so the normal validator still rejects them.
            if key not in PRODUCT_FIELDS or key in {"name", "insurer"} or not isinstance(refs, list) or not refs:
                kept.append(fact)
                continue
            anchors = [sources.get(ref, {}) for ref in refs if isinstance(ref, str)]
            if len(anchors) != len(refs) or not all((s.get("verification") or {}).get("status") == "verified" for s in anchors):
                kept.append(fact)
                continue
            value = "".join(str(fact.get("value") or "").split())
            if value and any(value == "".join(str(s.get("excerpt") or "").split()) for s in anchors):
                kept.append(fact)
                continue
            gap = f"{module.get('id')}：{PRODUCT_FIELDS[key]}未通过核验，暂不展示；需补充直接支持该字段的完整官方原文。"
            if gap not in coverage["gaps"]:
                coverage["gaps"].append(gap)
        module["productFacts"] = kept
