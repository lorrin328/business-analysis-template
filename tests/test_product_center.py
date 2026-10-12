"""Product-center contract tests using synthetic, non-business documents only."""
import copy
import hashlib
import io
import json
import stat
import zipfile

import pytest
from fastapi.testclient import TestClient

from main import app

BASE = "/api/product-center"
PDF = b"%PDF-1.4\n% Synthetic product-center fixture, no business data.\n%%EOF\n"
DIGEST = hashlib.sha256(PDF).hexdigest()
SOURCE_ENTRY = f"files/{DIGEST}.pdf"


def manifest():
    versions = []
    facts = []
    scenarios = []
    for identifier, channel, stage in [("oto-v1", "OTO", "formal"), ("zb-v1", "证保", "formal"), ("draft-v1", "OTO", "development")]:
        versions.append({
            "id": identifier, "name": "合成产品" + identifier, "code": identifier,
            "channel": channel, "stage": stage, "insurer": "合成测试公司",
            "revision": "测试版本1", "identityStatus": "confirmed", "saleStatus": "unknown",
            "responsibilityType": "年金", "benefitMechanism": "保证", "reviewDate": "2026-10-12",
            "limitations": [], "sourceIds": ["source-1"],
        })
        facts.append({
            "id": "fact-" + identifier, "versionId": identifier, "dimension": "保障责任",
            "label": "身故责任", "text": "未成年：已交保费；成年且期交缴费期内：合同约定倍数。",
            "status": "开发稿载" if stage == "development" else "已确认",
            "sourceIds": ["source-1"], "locator": "第1页，第2条",
            "reviewDate": "2026-10-12", "limitations": ["责任分支以条款为准"],
        })
        scenarios.append({
            "id": "scenario-" + identifier, "versionId": identifier,
            "productName": "合成产品" + identifier, "channel": channel,
            "partition": "development" if stage == "development" else "guarantee",
            "benefitNature": "development" if stage == "development" else "guaranteed",
            "age": 40, "sex": "女", "payYears": 1, "payLabel": "趸交",
            "annualPremium": 1500000, "totalPremium": 1500000,
            "paidPremiumAtExit": 1500000, "horizonYear": 1,
            "irr": 0.05, "originalIrr": 0.05, "computedIrr": 0.05,
            "arithmeticStatus": "已校验", "contractStatus": "已确认",
            "terminalValue": 1575000, "incomeTotal": 0, "variant": "期末退出",
            "status": "已确认", "limitations": [], "sourceIds": ["source-1"],
            "cashflows": [{"timeYear": 0, "amount": -1500000, "kind": "premium"},
                          {"timeYear": 1, "amount": 1575000, "kind": "terminal"}],
        })
    pending = copy.deepcopy(scenarios[0])
    pending.update(id="scenario-null", irr=None, originalIrr=None, computedIrr=None,
                   arithmeticStatus="待核", status="待核", cashflows=[])
    scenarios.append(pending)
    boundary = copy.deepcopy(scenarios[0])
    boundary.update(id="scenario-timing", partition="example", benefitNature="illustrated",
                    arithmeticStatus="假设下复算", status="假设下复算",
                    limitations=["退出时点边界待核，不进入已核验比较"])
    scenarios.append(boundary)
    return {
        "formatVersion": 1, "sourceDate": "2026-10-12", "converterVersion": "1",
        "versions": versions, "facts": facts, "scenarios": scenarios,
        "sources": [{"id": "source-1", "filename": "合成条款.pdf", "sha256": DIGEST,
                     "entry": SOURCE_ENTRY, "mediaType": "application/pdf", "reviewDate": "2026-10-12",
                     "versionIds": [row["id"] for row in versions], "locator": "第1页"}],
        "gaps": [], "report": {"synthetic": True},
    }


def package(data=None, entries=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(data or manifest(), ensure_ascii=False))
        archive.writestr(SOURCE_ENTRY, PDF)
        for name, content in entries or []:
            archive.writestr(name, content)
    return stream.getvalue()


@pytest.fixture()
def center(auth_db, tmp_path, monkeypatch):
    monkeypatch.setenv("PRODUCT_CENTER_DATA_DIR", str(tmp_path / "product-data"))
    monkeypatch.setenv("BUSINESS_ANALYSIS_LOCK", str(tmp_path / "write.lock"))
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "Test-only-admin-2026!"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["data"]["token"]}
    return client, headers


def preview(center, data=None, payload=None):
    client, headers = center
    return client.post(BASE + "/imports/preview", headers=headers,
                       files={"file": ("synthetic.zip", payload or package(data), "application/zip")})


def publish(center, data=None):
    response = preview(center, data)
    assert response.status_code == 200, response.text
    batch = response.json()["data"]["batch"]["id"]
    client, headers = center
    response = client.post(f"{BASE}/imports/{batch}/publish", headers=headers)
    assert response.status_code == 200, response.text
    return batch


def data_get(center, suffix):
    client, headers = center
    response = client.get(BASE + suffix, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_preview_is_private_and_idempotent_until_published(center):
    assert data_get(center, "/products")["items"] == []
    first = preview(center)
    assert first.status_code == 200, first.text
    result = first.json()["data"]
    again = preview(center).json()["data"]
    assert again["batch"]["id"] == result["batch"]["id"]
    assert again["duplicate"] is True
    assert data_get(center, "/products")["items"] == []
    client, headers = center
    assert client.get(BASE + "/sources/source-1/file", headers=headers).status_code == 404
    assert len(data_get(center, "/imports")["items"]) == 1


def test_publish_defaults_to_formal_filters_and_keeps_independent_statuses(center):
    batch = publish(center)
    listed = data_get(center, "/products")
    assert listed["activeBatchId"] == batch
    assert {row["id"] for row in listed["items"]} == {"oto-v1", "zb-v1"}
    assert {row["id"] for row in data_get(center, "/products?stage=development")["items"]} == {"draft-v1"}
    assert {row["id"] for row in data_get(center, "/products?channel=OTO")["items"]} == {"oto-v1"}
    assert data_get(center, "/products?q=zb-v1")["total"] == 1
    detail = data_get(center, "/products/oto-v1")
    assert detail["product"]["saleStatus"] == "unknown"
    assert "未成年" in detail["facts"][0]["text"]
    assert detail["sources"][0]["id"] == "source-1"
    assert "entry" not in detail["sources"][0]


def test_null_irr_and_timing_limitations_survive_roundtrip(center):
    publish(center)
    items = data_get(center, "/products/oto-v1/scenarios")["items"]
    null = next(row for row in items if row["id"] == "scenario-null")
    assert null["irr"] is None
    cash = data_get(center, "/scenarios/scenario-oto-v1/cashflows")
    assert cash["cashflows"] == manifest()["scenarios"][0]["cashflows"]
    client, headers = center
    comparison = client.post(BASE + "/compare", headers=headers,
                             json={"versionIds": ["oto-v1", "zb-v1"], "partition": "guarantee"})
    assert comparison.status_code == 200, comparison.text
    result = comparison.json()["data"]
    assert len(result["dimensions"]) == 7
    assert "scenario-timing" not in json.dumps(result["scenarios"], ensure_ascii=False)


def test_mismatched_conditions_are_explicit_not_ranked(center):
    source = manifest()
    source["scenarios"][1]["age"] = 41
    publish(center, source)
    client, headers = center
    response = client.post(BASE + "/compare", headers=headers,
                           json={"versionIds": ["oto-v1", "zb-v1"], "partition": "guarantee"})
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["differences"]
    assert "rank" not in result


@pytest.mark.parametrize("ids", [["oto-v1"], ["oto-v1"] * 5, ["oto-v1", "oto-v1"]])
def test_compare_requires_two_to_four_distinct_versions(center, ids):
    publish(center)
    client, headers = center
    response = client.post(BASE + "/compare", headers=headers, json={"versionIds": ids})
    assert response.status_code in (400, 422)


def test_source_file_requires_auth_and_hides_internal_paths(center, tmp_path):
    publish(center)
    client, headers = center
    response = client.get(BASE + "/sources/source-1/file", headers=headers)
    assert response.status_code == 200, response.text
    assert response.content == PDF
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["content-type"].startswith("application/pdf")
    assert str(tmp_path) not in str(response.headers)
    assert client.get(BASE + "/sources/source-1/file").status_code == 401
    assert client.get(BASE + "/sources/missing/file", headers=headers).status_code == 404


@pytest.mark.parametrize("role", ["normal", "senior"])
def test_admin_role_required_even_with_module_permission(center, role):
    publish(center)
    client, headers = center
    created = client.post("/api/admin/users", headers=headers,
                          json={"username": role + "_pc", "password": "Product-test-123!", "role": role,
                                "permissions": {"product_structure": True, "product_config": True, "upload": True}})
    assert created.status_code == 200, created.text
    login = client.post("/api/auth/login", json={"username": role + "_pc", "password": "Product-test-123!"})
    restricted = {"Authorization": "Bearer " + login.json()["data"]["token"]}
    for path in ["/products", "/products/oto-v1", "/products/oto-v1/scenarios", "/scenarios/scenario-oto-v1/cashflows", "/imports", "/sources/source-1/file", "/sources/source-1/text?page=1"]:
        assert client.get(BASE + path, headers=restricted).status_code == 403, path
        assert client.get(BASE + path).status_code == 401, path
    assert client.post(BASE + "/compare", headers=restricted, json={"versionIds": ["oto-v1", "zb-v1"]}).status_code == 403
    assert client.post(BASE + "/imports/preview", headers=restricted,
                       files={"file": ("test.zip", package(), "application/zip")}).status_code == 403


def test_withdraw_restores_previous_batch_without_newer_data_leak(center):
    first = publish(center)
    replacement = manifest()
    replacement["versions"][0]["name"] = "替换后的合成产品"
    second = publish(center, replacement)
    assert second != first
    assert data_get(center, "/products/oto-v1")["product"]["name"] == "替换后的合成产品"
    client, headers = center
    undone = client.post(f"{BASE}/imports/{second}/withdraw", headers=headers)
    assert undone.status_code == 200, undone.text
    assert data_get(center, "/products")["activeBatchId"] == first
    assert data_get(center, "/products/oto-v1")["product"]["name"] == "合成产品oto-v1"
    repeated = client.post(f"{BASE}/imports/{second}/withdraw", headers=headers)
    assert repeated.status_code in (200, 409)
    assert data_get(center, "/products")["activeBatchId"] == first


@pytest.mark.parametrize("damage", ["source", "package"])
def test_withdraw_refuses_broken_previous_batch_without_switching_current(center, tmp_path, damage):
    from db import get_db

    first = publish(center)
    replacement = manifest()
    replacement["versions"][0]["name"] = "当前有效批次"
    second = publish(center, replacement)
    root = tmp_path / "product-data"
    if damage == "source":
        (root / SOURCE_ENTRY).write_bytes(b"%PDF-1.4 changed after first publication")
    else:
        with get_db() as conn:
            sha = conn.execute("SELECT manifest_hash FROM product_center_batches WHERE id=?", (first,)).fetchone()[0]
        (root / "packages" / f"{sha}.zip").unlink()
    client, headers = center
    response = client.post(f"{BASE}/imports/{second}/withdraw", headers=headers)
    assert response.status_code in (400, 409), response.text
    assert data_get(center, "/products")["activeBatchId"] == second
    assert data_get(center, "/products/oto-v1")["product"]["name"] == "当前有效批次"


@pytest.mark.parametrize("mutation", ["hash", "fact_version", "source_ref", "duplicate_id", "source_traversal"])
def test_invalid_manifest_never_replaces_active_batch(center, mutation):
    first = publish(center)
    invalid = manifest()
    if mutation == "hash":
        invalid["sources"][0]["sha256"] = "0" * 64
    elif mutation == "fact_version":
        invalid["facts"][0]["versionId"] = "missing-version"
    elif mutation == "source_ref":
        invalid["facts"][0]["sourceIds"] = ["missing-source"]
    elif mutation == "duplicate_id":
        invalid["versions"].append(copy.deepcopy(invalid["versions"][0]))
    else:
        invalid["sources"][0]["entry"] = "../outside.pdf"
    response = preview(center, invalid)
    assert response.status_code in (400, 422), response.text
    assert data_get(center, "/products")["activeBatchId"] == first
    assert len(data_get(center, "/imports")["items"]) == 1


@pytest.mark.parametrize("entry", ["../outside.pdf", "/absolute.pdf", "files/unlisted.pdf", "files\\windows.pdf"])
def test_unsafe_or_unlisted_zip_entries_are_rejected(center, entry):
    response = preview(center, payload=package(entries=[(entry, PDF)]))
    assert response.status_code in (400, 422), response.text
    assert data_get(center, "/imports")["items"] == []


def test_zip_symlink_rejected(center):
    stream = io.BytesIO(package())
    with zipfile.ZipFile(stream, "a") as archive:
        info = zipfile.ZipInfo("files/link.pdf")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../secret")
    response = preview(center, payload=stream.getvalue())
    assert response.status_code in (400, 422)


@pytest.mark.parametrize("payload", [b"not a zip", b"PK\x03\x04broken"])
def test_corrupt_package_returns_controlled_error(center, payload):
    response = preview(center, payload=payload)
    assert response.status_code in (400, 422)
    assert data_get(center, "/imports")["items"] == []


def test_duplicate_zip_filename_rejected(center):
    stream = io.BytesIO(package())
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(stream, "a") as archive:
            archive.writestr("manifest.json", json.dumps(manifest()))
    response = preview(center, payload=stream.getvalue())
    assert response.status_code in (400, 422)


def test_same_name_different_versions_remain_distinct(center):
    source = manifest()
    for product in source["versions"]:
        product["name"] = "完全同名的合成产品"
    publish(center, source)
    items = data_get(center, "/products?q=完全同名")["items"]
    assert {row["id"] for row in items} == {"oto-v1", "zb-v1"}
    assert data_get(center, "/products/oto-v1")["product"]["channel"] == "OTO"
    assert data_get(center, "/products/zb-v1")["product"]["channel"] == "证保"


def test_publish_rechecks_preview_files_before_atomic_switch(center, tmp_path):
    first = publish(center)
    candidate = manifest()
    candidate["versions"][0]["name"] = "尚未发布的新版本"
    response = preview(center, candidate)
    assert response.status_code == 200, response.text
    batch_id = response.json()["data"]["batch"]["id"]
    file = tmp_path / "product-data" / SOURCE_ENTRY
    file.write_bytes(b"%PDF-1.4\nchanged after preview\n%%EOF")
    client, headers = center
    response = client.post(f"{BASE}/imports/{batch_id}/publish", headers=headers)
    assert response.status_code in (400, 409), response.text
    assert data_get(center, "/products")["activeBatchId"] == first
    assert data_get(center, "/products/oto-v1")["product"]["name"] == "合成产品oto-v1"
    assert client.get(BASE + "/sources/source-1/file", headers=headers).status_code == 409


def test_publish_rechecks_package_after_preview(center, tmp_path):
    response = preview(center)
    assert response.status_code == 200, response.text
    batch_id = response.json()["data"]["batch"]["id"]
    packages = list((tmp_path / "product-data" / "packages").glob("*.zip"))
    assert len(packages) == 1
    changed = manifest()
    changed["versions"][0]["name"] = "未预检内容"
    packages[0].write_bytes(package(changed))
    client, headers = center
    response = client.post(f"{BASE}/imports/{batch_id}/publish", headers=headers)
    assert response.status_code in (400, 409), response.text
    assert data_get(center, "/products")["activeBatchId"] is None


def test_expansion_and_upload_limits_reject_before_writing(center, monkeypatch):
    import product_center.service as service

    monkeypatch.setattr(service, "MAX_EXPANDED_BYTES", 50)
    assert preview(center).status_code in (400, 413)
    assert data_get(center, "/imports")["items"] == []
    monkeypatch.setattr(service, "MAX_EXPANDED_BYTES", 300 * 1024 * 1024)
    monkeypatch.setattr(service, "MAX_PACKAGE_BYTES", 50)
    assert preview(center).status_code == 413
    assert data_get(center, "/imports")["items"] == []


@pytest.mark.parametrize("field", ["code", "responsibilityType", "benefitMechanism"])
def test_invalid_product_field_types_are_validation_errors(center, field):
    source = manifest()
    source["versions"][0][field] = {"invalid": "must be text"}
    response = preview(center, source)
    assert response.status_code in (400, 422), response.text
    assert data_get(center, "/imports")["items"] == []


@pytest.mark.parametrize("collection,field", [("versions", "sourceIds"), ("sources", "versionIds")])
def test_unhashable_reference_values_are_validation_errors(center, collection, field):
    source = manifest()
    source[collection][0][field] = [{"invalid": "reference"}]
    response = preview(center, source)
    assert response.status_code in (400, 422), response.text


@pytest.mark.parametrize("collection", ["facts", "scenarios"])
def test_unhashable_version_reference_is_validation_error(center, collection):
    source = manifest()
    source[collection][0]["versionId"] = {"invalid": "reference"}
    response = preview(center, source)
    assert response.status_code in (400, 422), response.text


@pytest.mark.parametrize("field,path", [("report", "C:\\private\\product-source.pdf"), ("gaps", "/var/lib/private/product-source.pdf")])
def test_private_absolute_paths_rejected_even_in_nested_report_metadata(center, field, path):
    source = manifest()
    if field == "report":
        source["report"]["nested"] = {"originalPath": path}
    else:
        source["gaps"].append({"details": {"originalPath": path}})
    response = preview(center, source)
    assert response.status_code in (400, 422), response.text
    assert data_get(center, "/imports")["items"] == []


def test_missing_code_requires_explicit_provisional_identity(center):
    source = manifest()
    source["versions"][0]["code"] = None
    response = preview(center, source)
    assert response.status_code in (400, 422), response.text
    source["versions"][0]["identityStatus"] = "provisional"
    assert preview(center, source).status_code == 200


def test_unlinked_scenario_is_quarantined_while_valid_products_publish(center):
    source = manifest()
    unlinked = copy.deepcopy(source["scenarios"][0])
    unlinked.update(id="scenario-unlinked", versionId=None, productName="身份待核")
    source["scenarios"].append(unlinked)
    publish(center, source)
    assert data_get(center, "/products")["total"] == 2
    assert "scenario-unlinked" not in json.dumps(data_get(center, "/products/oto-v1/scenarios"))
    client, headers = center
    assert client.get(BASE + "/scenarios/scenario-unlinked/cashflows", headers=headers).status_code == 404


def test_logout_revokes_file_access(center):
    publish(center)
    client, headers = center
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get(BASE + "/sources/source-1/file", headers=headers).status_code == 401


def test_policy_year_irr_independent_solver_and_tolerances():
    from product_center.irr import npv, solve_irr, verify_record

    flows = [{"timeYear": 0, "amount": -1500000}, {"timeYear": 1, "amount": 1575000}]
    rate = solve_irr(flows)
    assert abs(rate - 0.05) <= 1e-8
    assert abs(npv(flows, rate)) <= 0.01
    assert verify_record({"id": "matching", "irr": 0.05, "cashflows": flows})["passed"]
    assert not verify_record({"id": "wrong", "irr": 0.06, "cashflows": flows})["passed"]
    pending = verify_record({"id": "pending", "irr": None, "cashflows": []})
    assert pending["computedIrr"] is None
    assert pending["status"] == "pending"


@pytest.mark.parametrize("flows", [
    [{"timeYear": 0, "amount": -100}, {"timeYear": 1, "amount": 230}, {"timeYear": 2, "amount": -132}],
    [{"timeYear": 0, "amount": 100}, {"timeYear": 1, "amount": 110}],
    [{"timeYear": -1, "amount": -100}, {"timeYear": 1, "amount": 110}],
    [{"timeYear": 0, "amount": -100}, {"timeYear": 1, "amount": float("nan")}],
])
def test_irr_rejects_ambiguous_or_invalid_cashflows(flows):
    from product_center.irr import IRRError, solve_irr

    with pytest.raises(IRRError):
        solve_irr(flows)


def test_calculation_coverage_mismatch_cannot_report_success():
    from product_center.irr import verify_calculations

    row = {"result_id": "fixture", "irr": 0.05,
           "cashflows": [{"timeYear": 0, "amount": -100}, {"timeYear": 1, "amount": 105}]}
    result = verify_calculations({"records": [row], "all_calculations": []})
    assert result["numericCount"] == 1
    assert result["coverageErrors"]
    assert result["passed"] is False


def publish_original(center, raw, suffix=".pdf", media_type="application/pdf"):
    source = manifest()
    sha = hashlib.sha256(raw).hexdigest()
    entry = f"files/{sha}{suffix}"
    source["sources"][0].update(sha256=sha, entry=entry, filename="合成原件" + suffix, mediaType=media_type)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("manifest.json", json.dumps(source, ensure_ascii=False))
        archive.writestr(entry, raw)
    response = preview(center, payload=stream.getvalue())
    assert response.status_code == 200, response.text
    batch = response.json()["data"]["batch"]["id"]
    client, headers = center
    response = client.post(f"{BASE}/imports/{batch}/publish", headers=headers)
    assert response.status_code == 200, response.text


def blank_pdf():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.add_blank_page(width=300, height=400)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_authenticated_pdf_text_preview_preserves_page_counts_cache_boundary_and_audit(center, tmp_path):
    publish_original(center, blank_pdf())
    client, headers = center
    response = client.get(BASE + "/sources/source-1/text?page=1", headers=headers)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    result = response.json()["data"]
    assert result["source"]["id"] == "source-1"
    assert result["page"] == 1
    assert result["pageCount"] == 2
    assert result["text"] == ""
    assert str(tmp_path) not in response.text
    assert client.get(BASE + "/sources/source-1/text?page=2", headers=headers).status_code == 200
    assert client.get(BASE + "/sources/source-1/text?page=1").status_code == 401
    logs = client.get("/api/admin/operation-logs?limit=30", headers=headers).json()["data"]["logs"]
    accesses = [row for row in logs if row["action"].startswith("product_center_source")]
    assert any(json.loads(row["detail"]).get("sourceId") == "source-1" and json.loads(row["detail"]).get("page") == 1 for row in accesses)
    assert all(str(tmp_path) not in row["detail"] for row in accesses)


@pytest.mark.parametrize("page", [0, -1, 3])
def test_pdf_text_preview_rejects_invalid_page(center, page):
    publish_original(center, blank_pdf())
    client, headers = center
    response = client.get(f"{BASE}/sources/source-1/text?page={page}", headers=headers)
    assert response.status_code in (400, 422), response.text


def test_pdf_text_preview_rejects_nonpdf_original(center):
    publish_original(center, b"\x89PNG\r\n\x1a\nsynthetic", ".png", "image/png")
    client, headers = center
    response = client.get(BASE + "/sources/source-1/text?page=1", headers=headers)
    assert response.status_code == 400, response.text


def test_invalid_pdf_text_error_contains_no_internal_path_or_traceback(center, tmp_path):
    publish(center)
    client, headers = center
    response = client.get(BASE + "/sources/source-1/text?page=1", headers=headers)
    assert response.status_code == 400, response.text
    assert str(tmp_path) not in response.text
    assert "Traceback" not in response.text
    assert "PDF" in response.text


def test_historical_preview_refreshes_difference_against_current_publication(center):
    first = publish(center)
    replacement = manifest()
    replacement['facts'][0]['text'] = '有来源的更正责任，保留原历史版本'
    second = publish(center, replacement)
    result = data_get(center, '/imports/' + first)
    assert result['diff']['previousBatchId'] == second
    assert result['diff']['retainedVersions'] == 3
    assert result['diff']['addedVersions'] == 0
    assert result['diff']['changedFacts'] == 1
