"""Synthetic regression: no internal originals or identity mappings in Git."""
import csv
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from product_center.converter import INPUTS, build_package, convert_archive, source_path
from product_center.irr import IRRError, npv, solve_irr, verify_calculations


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    relative = "2026年产品资料/OTO职拓/太平合成养老年金保险条款.pdf"
    original = root / relative
    original.parent.mkdir(parents=True)
    original.write_bytes(b"%PDF-1.4 synthetic source only")
    hashed = hashlib.sha256(original.read_bytes()).hexdigest()
    reference = {"id": "synthetic-clause", "path": relative, "sha256": hashed,
                 "version": "SYNTHETIC-2026-01", "reviewed_physical_pages": [1]}
    flow = [{"time_year": 0, "amount": -1000, "kind": "premium"},
            {"time_year": 1, "amount": 1100, "kind": "surrender"}]
    record = {"result_id": "SYNTHETIC-1", "channel": "OTO", "product_code": "99001",
              "product_name": "太平合成养老年金保险", "age": 40, "sex": "女", "pay_years": 1,
              "pay_label": "趸交", "annual_premium": 1000, "total_premium": 1000,
              "paid_premium_at_exit": 1000, "horizon_year": 1, "irr": 0.1,
              "scenario": "guaranteed", "terminal_value": 1100, "income_total": 0,
              "sources": [reference], "cashflows": flow, "limitations": ["合成数据"]}
    objects = {
        "oto": {"review_date": "2026-09-24", "sources": [reference], "products": [
            {"product": record["product_name"], "responsibility_and_mechanism": "养老年金；非分红",
             "evidence": [reference["id"]], "core_benefits": "未成年、成年及缴费期内外按分支保留。",
             "limitations": ["合成数据"]}]},
        "zhengbao": {"audit_date": "2026-09-24", "scope": "合成", "products": []},
        "development": {"verified_on": "2026-09-24", "boundary": "合成", "products": []},
        "combined": {"as_of": "2026-09-24", "records": [record], "example_records": [],
                     "development_maturity": [], "all_calculations": [record]},
        "baseline": [{"path": relative, "sha256": hashed, "bytes": original.stat().st_size,
                      "products": ["99001"]}],
    }
    for key, obj in objects.items():
        path = root / INPUTS[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    path = root / INPUTS["index"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["相对路径", "SHA256"])
        writer.writeheader()
        writer.writerow({"相对路径": relative, "SHA256": hashed.upper()})
    return root, objects, original


def rewrite(root, key, value):
    (root / INPUTS[key]).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_unique_root_with_nonzero_initial_time_and_fractional_receipt():
    flows = [{"timeYear": 1, "amount": -1000}, {"timeYear": 2.5, "amount": 1100}]
    rate = solve_irr(flows)
    assert rate == pytest.approx(1.1 ** (1 / 1.5) - 1, abs=1e-12)
    assert abs(npv(flows, rate)) < .01


@pytest.mark.parametrize("flows", [
    [{"timeYear": 0, "amount": -100}, {"timeYear": 1, "amount": 230}, {"timeYear": 2, "amount": -132}],
    [{"timeYear": 0, "amount": 100}],
    [{"timeYear": -1, "amount": -100}, {"timeYear": 1, "amount": 110}],
    [{"timeYear": 0, "amount": -100}, {"timeYear": 1, "amount": math.inf}],
    [{"timeYear": 0, "amount": True}, {"timeYear": 1, "amount": 110}],
])
def test_invalid_or_potential_multiple_roots_rejected(flows):
    with pytest.raises(IRRError):
        solve_irr(flows)


def test_same_time_netting_does_not_create_false_multiple_root():
    flows = [{"time_year": 0, "amount": -100}, {"time_year": 1, "amount": 200},
             {"time_year": 1, "amount": -90}]
    assert solve_irr(flows) == pytest.approx(.1)


def test_deterministic_source_bound_identity_and_zip(archive, tmp_path):
    root, objects, original = archive
    first, files = convert_archive(root)
    second, _ = convert_archive(root)
    assert first == second
    assert len(first["versions"]) == 1
    assert first["versions"][0]["identityStatus"] == "confirmed"
    assert first["scenarios"][0]["versionId"] == first["versions"][0]["id"]
    assert first["report"]["arithmetic"]["passedCount"] == 1
    assert len(first["report"]["sourceInputs"]) == len(INPUTS)
    assert {x["filename"] for x in first["report"]["sourceInputs"]} == {Path(p).name for p in INPUTS.values()}
    assert all(len(x["sha256"]) == 64 for x in first["report"]["sourceInputs"])
    assert str(root) not in json.dumps(first)
    before = original.read_bytes()
    output = tmp_path / "private" / "import.zip"
    build_package(root, output)
    with zipfile.ZipFile(output) as package:
        assert set(package.namelist()) == {"manifest.json", *files}
        assert all(Path(x).name not in [Path(p).name for p in INPUTS.values()] for x in files)
    assert original.read_bytes() == before
    with pytest.raises(FileExistsError):
        build_package(root, output)


def test_timing_pending_and_missing_original_remain_null(archive):
    root, objects, _ = archive
    combined = objects["combined"]
    example = dict(combined["records"][0], result_id="EXAMPLE", verification_status="timing_pending", comparison_eligible=False)
    pending = dict(combined["records"][0], result_id="PENDING", irr=None, cashflows=[])
    combined["example_records"] = [example]
    combined["records"].append(pending)
    combined["all_calculations"].append(example)
    rewrite(root, "combined", combined)
    manifest, _ = convert_archive(root)
    assert manifest["scenarios"][1]["irr"] is None
    assert manifest["scenarios"][2]["irr"] is None
    assert manifest["scenarios"][2]["computedIrr"] == pytest.approx(.1)
    assert manifest["report"]["arithmetic"]["pendingCount"] == 1


def test_abbreviation_without_identity_evidence_quarantined(archive):
    root, objects, _ = archive
    combined = objects["combined"]
    combined["records"][0].update(product_code=None, product_name="合成", sources=[])
    combined["all_calculations"] = combined["records"]
    rewrite(root, "combined", combined)
    manifest, _ = convert_archive(root)
    assert manifest["scenarios"][0]["versionId"] is None
    assert manifest["scenarios"][0]["irr"] is None
    assert manifest["scenarios"][0]["originalIrr"] == .1
    assert manifest["scenarios"][0]["computedIrr"] == pytest.approx(.1)
    assert manifest["report"]["quarantinedScenarioCount"] == 1


def test_missing_code_abbreviation_needs_reviewed_same_source_override(archive):
    root, objects, _ = archive
    objects["baseline"][0]["products"] = ["代码待核"]
    combined = objects["combined"]
    combined["records"][0].update(product_code=None, product_name="合成简称")
    rewrite(root, "baseline", objects["baseline"])
    rewrite(root, "combined", combined)
    manifest, _ = convert_archive(root)
    assert manifest["versions"][0]["code"] is None
    assert manifest["scenarios"][0]["versionId"] is None
    mapping = {"resultId": "SYNTHETIC-1", "versionId": manifest["versions"][0]["id"],
               "sourceSha256": objects["baseline"][0]["sha256"],
               "locator": "物理页1，正式名称及示例身份人工核对", "reason": "合成原件同一来源身份已核对"}
    with pytest.raises(ValueError, match="核验日期"):
        convert_archive(root, {"scenarioMappings": [mapping]})
    with pytest.raises(ValueError, match="核验日期"):
        convert_archive(root, {"reviewDate": "2026-02-30", "scenarioMappings": [mapping]})
    reviewed, _ = convert_archive(root, {"reviewDate": "2026-10-12", "scenarioMappings": [mapping]})
    assert reviewed["scenarios"][0]["versionId"] == manifest["versions"][0]["id"]
    assert reviewed["scenarios"][0]["irr"] == .1
    assert reviewed["versions"][0]["identityStatus"] == "provisional"
    assert reviewed["report"]["identityMappings"][-1]["reviewDate"] == "2026-10-12"
    mapping["reviewDate"] = "2026-10-11"
    reviewed, _ = convert_archive(root, {"reviewDate": "2026-10-12", "scenarioMappings": [mapping]})
    assert reviewed["report"]["identityMappings"][-1]["reviewDate"] == "2026-10-11"
    mapping["sourceSha256"] = "0" * 64
    with pytest.raises(ValueError, match="身份覆盖"):
        convert_archive(root, {"scenarioMappings": [mapping]})


def test_original_hash_and_path_escape_rejected(archive, tmp_path):
    root, _, original = archive
    original.write_bytes(b"changed")
    with pytest.raises(ValueError, match="基线哈希"):
        convert_archive(root)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="允许目录"):
        source_path(root, str(outside))
    with pytest.raises(ValueError, match="上级目录"):
        source_path(root, "../outside.pdf")


def test_strict_regression_detects_wrong_irr_and_duplicate_record():
    record = {"result_id": "one", "irr": .11,
              "cashflows": [{"time_year": 0, "amount": -100}, {"time_year": 1, "amount": 110}]}
    assert not verify_calculations({"records": [record]})["passed"]
    with pytest.raises(ValueError, match="重复"):
        verify_calculations({"records": [record, record]})


def test_baseline_only_development_difference_is_explicit(archive):
    root, objects, _ = archive
    path = root / "产品开发阶段材料/synthetic.png"
    path.parent.mkdir()
    path.write_bytes(b"synthetic-development")
    objects["baseline"].append({"path": "产品开发阶段材料/synthetic.png", "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "products": []})
    rewrite(root, "baseline", objects["baseline"])
    manifest, _ = convert_archive(root)
    report = manifest["report"]["coverage"]
    assert report["baselineCount"] == 2 and report["indexCount"] == 1
    assert report["baselineOnly"][0]["reason"].startswith("开发阶段")
    assert report["passed"]


def test_cli_regression_nonzero_and_private_report(archive, tmp_path):
    from importlib.util import module_from_spec, spec_from_file_location
    script = Path(__file__).resolve().parents[1] / "scripts/verify_product_center_data.py"
    spec = spec_from_file_location("verify_product_center_data", script)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    root, _, _ = archive
    report = tmp_path / "private-report.json"
    assert module.main(["--source-root", str(root), "--report", str(report)]) == 1
    assert not json.loads(report.read_text(encoding="utf-8"))["passed"]
