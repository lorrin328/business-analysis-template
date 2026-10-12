"""Offline, allowlisted conversion of the 007 research archive.

This module never edits the source archive and does not send data over a network.
ZIP outputs contain normalized facts and referenced originals, not input JSON.
"""
from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from .irr import verify_calculations


INPUTS = {
    "oto": "01-产品学习/20260924_原件再核对/OTO事实.json",
    "zhengbao": "01-产品学习/20260924_原件再核对/证保事实.json",
    "development": "01-产品学习/20260924_原件再核对/开发事实.json",
    "combined": "02-竞争力分析/20260924_分缴别IRR/combined_results.json",
    "baseline": "00-项目管理/产品分类基线.json",
    "index": "00-项目管理/资料索引.csv",
}
DIMENSIONS = ("客户需求", "保障责任", "利益水平", "退出与灵活性", "服务权益", "渠道承接", "公司经济性")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg"}


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_id(prefix: str, *parts) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return prefix + digest_bytes(encoded)[:32]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_path(root: Path, value: str) -> Path:
    """Permit archive-contained paths only, including old absolute references."""
    if not isinstance(value, str) or not value:
        raise ValueError("来源路径缺失")
    candidate = Path(value.replace("\\", "/"))
    if ".." in candidate.parts:
        raise ValueError("来源路径包含上级目录")
    candidate = candidate if candidate.is_absolute() else root / candidate
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("来源超出允许目录")
    for component in [candidate, *candidate.parents]:
        if component == root.parent:
            break
        if component.is_symlink():
            raise ValueError("来源包含符号链接")
    if not resolved.is_file():
        raise ValueError("来源必须是普通文件")
    return resolved


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root.resolve()).as_posix()


def _safe_text(value) -> str:
    # Known scalar fields only. Absolute source paths are replaced rather than
    # copied into data, error messages, or browser responses.
    text = str(value)
    text = re.sub(r"[A-Za-z]:[\\/][^\s\"<>]*", "[本地来源路径已隐去]", text)
    return text


def _strings(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [_safe_text(x) for x in values if x not in (None, "")]


def _formal_name(filename: str) -> str | None:
    """An exact formal name embedded in an original's title, never a short alias."""
    match = re.search(r"(太平.+?)(?=产品说明|现金价值|费率表|条款|责任免除|责免)", filename)
    return match.group(1).rstrip(" -_") if match else None


def load_source_data(source_root: str | Path) -> dict:
    root = Path(source_root).resolve(strict=True)
    result = {key: read_json(source_path(root, path))
              for key, path in INPUTS.items() if key != "index"}
    with source_path(root, INPUTS["index"]).open(encoding="utf-8-sig", newline="") as stream:
        result["index"] = list(csv.DictReader(stream))
    return result


class Converter:
    def __init__(self, source_root: str | Path, overrides: dict | None = None):
        self.root = Path(source_root).resolve(strict=True)
        self.data = load_source_data(self.root)
        self.overrides = overrides or {}
        self.baseline = {}
        self.by_hash = defaultdict(list)
        self.sources = {}
        self.files = {}
        self.versions = []
        self.facts = []
        self.gaps = []
        self.identity_report = []
        self.source_date = self.data["combined"]["as_of"]
        date.fromisoformat(self.source_date)
        for row in self.data["baseline"]:
            path = source_path(self.root, row["path"])
            relative = _relative(self.root, path)
            if relative in self.baseline:
                raise ValueError("分类基线来源重复")
            hashed = digest_bytes(path.read_bytes())
            if hashed != row["sha256"].lower() or path.stat().st_size != row["bytes"]:
                raise ValueError(f"基线哈希或大小不符: {path.name}")
            self.baseline[relative] = {**row, "sha256": hashed}
            self.by_hash[hashed].append(relative)

    def add_source(self, ref: dict, review_date: str) -> str:
        path = source_path(self.root, ref["path"])
        row = self.baseline.get(_relative(self.root, path))
        if row is None:
            raise ValueError(f"来源未列入分类白名单: {path.name}")
        actual = row["sha256"]
        expected = ref.get("sha256", ref.get("source_sha256"))
        if expected and expected.lower() != actual:
            raise ValueError(f"引用来源哈希不符: {path.name}")
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的原件格式: {path.suffix}")
        sid = "src_" + actual
        if sid not in self.sources:
            entry = f"files/{actual}{path.suffix.lower()}"
            pages = ref.get("reviewed_physical_pages", ref.get("focused_review_physical_pages", ref.get("page")))
            self.sources[sid] = {"id": sid, "filename": path.name,
                "sha256": actual, "entry": entry,
                "mediaType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "reviewDate": review_date, "versionIds": [],
                "locator": _safe_text(pages) if pages is not None else _safe_text(ref.get("locator", ""))}
            self.files[entry] = path
        return sid

    def _link(self, source_ids: list[str], version_id: str):
        for sid in source_ids:
            if version_id not in self.sources[sid]["versionIds"]:
                self.sources[sid]["versionIds"].append(version_id)

    def add_fact(self, version: dict, dimension: str, label: str, value,
                 source_ids: list[str], locator: str, status: str | None = None):
        if value in (None, "", [], {}):
            return
        text = _safe_text(value) if isinstance(value, (str, int, float)) else _safe_text(json.dumps(value, ensure_ascii=False))
        self.facts.append({"id": stable_id("fact_", version["id"], label, text, locator),
            "versionId": version["id"], "dimension": dimension, "label": label,
            "text": text, "status": status or ("开发稿载" if version["stage"] == "development" else "已确认"),
            "sourceIds": source_ids, "locator": locator,
            "reviewDate": version["reviewDate"], "limitations": version["limitations"]})

    def _version(self, *, name, code, channel, stage, refs, review_date,
                 mechanism=None, responsibility=None, limitations=None, locator=""):
        source_ids = sorted({self.add_source(ref, review_date) for ref in refs})
        if not source_ids:
            raise ValueError("产品版本缺来源")
        # Baseline identity is accepted only when every single-product original
        # agrees. Multi-product documents cannot invent an identity.
        codes = set()
        for sid in source_ids:
            for relative in self.by_hash[sid[4:]]:
                values = self.baseline[relative].get("products", [])
                if len(values) == 1 and re.fullmatch(r"\d+", str(values[0])):
                    codes.add(str(values[0]))
        if code is None and len(codes) == 1:
            code = next(iter(codes))
        if code is not None:
            code = str(code)
            if codes and codes != {code}:
                raise ValueError("产品代码与来源身份冲突")
        revisions = sorted({x["version"] for x in refs if x.get("version")})
        revision = " / ".join(revisions) if revisions else "source-" + stable_id("", source_ids)[:20]
        vid = stable_id("ver_", "太平人寿", code, name, channel, stage, revision)
        version = {"id": vid, "name": name, "code": code, "channel": channel,
            "stage": stage, "insurer": "太平人寿", "revision": revision,
            "identityStatus": "confirmed" if code and revisions else "provisional",
            "saleStatus": "unknown", "responsibilityType": responsibility,
            "benefitMechanism": mechanism, "reviewDate": review_date,
            "limitations": _strings(limitations), "sourceIds": source_ids}
        self.versions.append(version)
        self._link(source_ids, vid)
        self.identity_report.append({"versionId": vid, "code": code,
            "identityStatus": version["identityStatus"], "evidenceSourceIds": source_ids,
            "reason": "来源代码和合同版本确认" if version["identityStatus"] == "confirmed" else "代码或合同版本未全部确认，保留临时身份"})
        if version["identityStatus"] == "provisional":
            self.gaps.append({"versionId": vid, "type": "identity", "message": "代码或合同版本待核，版本以来源哈希锁定"})
        self.gaps.append({"versionId": vid, "type": "saleStatus", "message": "当前可售待核"})
        return version

    def convert_facts(self):
        oto = self.data["oto"]
        sources = {x["id"]: x for x in oto["sources"]}
        for p in oto["products"]:
            refs = [sources[sid] for sid in p["evidence"]]
            original_shape = p.get("responsibility_and_mechanism", "")
            v = self._version(name=p["product"], code=None, channel="OTO", stage="formal", refs=refs,
                review_date=oto["review_date"], responsibility=self._responsibility(p["product"]),
                mechanism=self._mechanism(original_shape), limitations=p.get("limitations"))
            for key, dimension, label in [
                ("responsibility_and_mechanism", "保障责任", "责任形态与利益机制原始核对记录"),
                ("eligibility_and_term", "客户需求", "投保范围、期限与缴费"),
                ("core_benefits", "保障责任", "核心责任与分支"),
                ("guarantee_and_non_guarantee", "利益水平", "保证与非保证机制"),
                ("key_boundary", "退出与灵活性", "适用边界与限制")]:
                self.add_fact(v, dimension, label, p.get(key), v["sourceIds"], "原件核对指定物理页，见来源页码")
            self._missing_parameters(v)

        zb = self.data["zhengbao"]
        for p in zb["products"]:
            refs = p["sources"]
            names = {_formal_name(Path(x["path"]).name) for x in refs}
            names.discard(None)
            if len(names) != 1:
                raise ValueError(f"正式产品名称来源不唯一，代码 {p['code']}")
            name = names.pop()
            v = self._version(name=name, code=p["code"], channel="证保", stage="formal", refs=refs,
                review_date=zb["audit_date"], mechanism=self._mechanism(p.get("dividend_mechanism", "")),
                responsibility=self._responsibility(name), limitations=[zb["scope"]])
            for key, dimension, label in [
                ("guaranteed_responsibility", "保障责任", "保证责任与分支"),
                ("dividend_mechanism", "利益水平", "红利机制"),
                ("waiting_period", "保障责任", "等待期核对范围"),
                ("major_exclusion_count", "保障责任", "主要责任免除条数")]:
                self.add_fact(v, dimension, label, p.get(key), v["sourceIds"], "原件条款及产品说明书重点核对页，见来源页码")
            # Exact reviewed extracts are retained with physical page locators.
            # This preserves adult/minor and pay-period conditions that summaries
            # alone may omit, without copying the complete input JSON.
            for ref in refs:
                sid = self.add_source(ref, zb["audit_date"])
                for page in ref.get("evidence_pages", []):
                    text = page.get("text", "")
                    self.add_fact(v, "保障责任", "原件重点页全文", text, [sid], f"物理页{page['physical_page']}")
            self._missing_parameters(v)

        dev = self.data["development"]
        for p in dev["products"]:
            pf = p["product_facts"]
            name = pf.get("险种名称", pf.get("产品名称"))
            if not name:
                raise ValueError("开发材料缺正式产品名称")
            v = self._version(name=name, code=p["code"], channel="证保", stage="development",
                refs=[{"path": p["source"], "sha256": p["sha256"], "locator": p["source_locator"]}],
                review_date=dev["verified_on"], mechanism=self._mechanism(pf.get("红利分配方式", pf.get("分红/非分红", ""))),
                responsibility=self._responsibility(name),
                limitations=["开发稿，不代表已批准或在售", dev["boundary"], *p.get("unknowns", [])])
            for key, value in pf.items():
                dimension = "保障责任" if key in ("保险责任", "等待期") else "客户需求"
                if key in ("预定利率", "分红/非分红", "费率结构"):
                    dimension = "利益水平"
                if key == "其他权益":
                    dimension = "服务权益"
                self.add_fact(v, dimension, key + "（开发稿）", value, v["sourceIds"], p["source_locator"])
            for key in ("adult_single_or_post_payment_formula", "adult_during_installment_formula", "minor_formula", "age_limits_source", "age80_irr_terminal_basis", "duplicate_source_row"):
                self.add_fact(v, "保障责任", key, p.get(key), v["sourceIds"], p.get("benefit_source", p["source_locator"]))
            section = ""
            for block in p.get("blocks", []):
                if block.get("type") == "paragraph" and block.get("text", "").strip():
                    section = block["text"]
                elif block.get("type") == "table":
                    dimension = "公司经济性" if any(x in section for x in ("费用", "手续费")) else "保障责任" if "形态" in section else "利益水平"
                    label = "开发稿表格：" + section
                    self.add_fact(v, dimension, label, block.get("rows"), v["sourceIds"], f"word/document.xml B{block['block']}；R为行号")
            self._missing_parameters(v)

    @staticmethod
    def _responsibility(name):
        for term in ("养老年金", "终身寿险", "两全保险", "年金保险", "重大疾病", "医疗保险", "护理保险"):
            if term in name:
                return term
        return None

    @staticmethod
    def _mechanism(text):
        # Categories derive from explicit researched mechanism, not the apparent
        # yield, filename, or the absence of a dividend label.
        if not isinstance(text, str):
            return None
        if "万能" in text:
            return "万能"
        if "非分红" in text or "普通型" in text:
            return "普通（非分红）"
        if "增额红利" in text or "保额分红" in text:
            return "保额分红"
        if "现金分红" in text or "现金红利" in text:
            return "现金分红"
        if "分红" in text:
            return "分红（方式待核）"
        return None

    def _missing_parameters(self, version):
        self.gaps.append({"versionId": version["id"], "type": "parameters",
            "message": "正式预定利率、实际演示投资利率、NBV、CSM与费用批准口径未确认；不反推、不补零"})
        self.add_fact(version, "公司经济性", "正式公司价值资料", "NBV、CSM、资本及资负资料待提供", version["sourceIds"], "研究范围限制", status="待核")

    def _scenario_identity(self, row, source_ids, partition):
        channel = "证保" if partition == "development" else row.get("channel")
        stage = "development" if partition == "development" else "formal"
        code = str(row["product_code"]) if row.get("product_code") is not None else None
        evidence_codes = set()
        evidence_names = set()
        for sid in source_ids:
            for rel in self.by_hash[sid[4:]]:
                ref = self.baseline[rel]
                if len(ref.get("products", [])) == 1:
                    evidence_codes.add(str(ref["products"][0]))
                name = _formal_name(Path(rel).name)
                if name:
                    evidence_names.add(name)
        candidates = []
        for v in self.versions:
            if v["channel"] != channel or v["stage"] != stage:
                continue
            source_match = bool(set(source_ids) & set(v["sourceIds"])) or (v["code"] is not None and v["code"] in evidence_codes) or v["name"] in evidence_names
            if not source_match:
                continue
            if code and v["code"] == code:
                candidates.append(v)
            elif not code and v["code"] is not None and v["code"] in evidence_codes:
                candidates.append(v)
            elif not code and row.get("product_name") == v["name"]:
                candidates.append(v)
        if len(candidates) == 1:
            return candidates[0]["id"], None
        overrides = [x for x in self.overrides.get("scenarioMappings", []) if x.get("resultId") == row["result_id"]]
        if len(overrides) > 1:
            raise ValueError("身份覆盖记录重复")
        if overrides:
            override = overrides[0]
            target = next((v for v in self.versions if v["id"] == override.get("versionId")), None)
            evidence = "src_" + override.get("sourceSha256", "").lower()
            review_date = override.get("reviewDate", self.overrides.get("reviewDate"))
            try:
                if not isinstance(review_date, str) or date.fromisoformat(review_date).isoformat() != review_date:
                    raise ValueError("身份覆盖核验日期必须为有效ISO日期")
            except (ValueError, TypeError) as exc:
                raise ValueError("身份覆盖核验日期必须为有效ISO日期") from exc
            if not target or target["channel"] != channel or target["stage"] != stage or evidence not in source_ids or evidence not in target["sourceIds"] or not override.get("locator") or not override.get("reason"):
                raise ValueError("身份覆盖缺少有效来源哈希、定位或说明")
            self.identity_report.append({"scenarioId": row["result_id"], "versionId": target["id"],
                "sourceId": evidence, "locator": _safe_text(override["locator"]),
                "reason": _safe_text(override["reason"]), "reviewDate": review_date, "override": True})
            return target["id"], None
        return None, "未取得唯一产品代码/正式名称、来源和渠道一致的身份，保留待核；未使用简称模糊匹配"

    def convert_scenarios(self, arithmetic):
        results = {x["id"]: x for x in arithmetic["rows"]}
        scenarios = []
        for key, partition in (("records", "guarantee"), ("example_records", "example"), ("development_maturity", "development")):
            for row in self.data["combined"].get(key, []):
                refs = row.get("sources", [])
                source_ids = sorted({self.add_source(ref, self.source_date) for ref in refs})
                vid, reason = self._scenario_identity(row, source_ids, partition)
                if vid:
                    self._link(source_ids, vid)
                else:
                    self.gaps.append({"scenarioId": row["result_id"], "type": "identity", "message": reason})
                audit = results.get(row["result_id"], {})
                timing_pending = row.get("verification_status") == "timing_pending" or row.get("comparison_eligible") is False
                label = row.get("scenario", "")
                nature = "guaranteed" if partition == "guarantee" else "development" if partition == "development" else "assumed" if any(x in label for x in ("假设", "万能")) else "illustrated"
                original_irr = row.get("irr")
                scenario = {"id": row["result_id"], "versionId": vid,
                    "productName": row["product_name"], "channel": "证保" if partition == "development" else row["channel"],
                    "partition": partition, "benefitNature": nature,
                    "age": row.get("age"), "sex": row.get("sex"),
                    "payYears": row.get("pay_years"), "payLabel": row.get("pay_label"),
                    "annualPremium": row.get("annual_premium"), "totalPremium": row.get("total_premium"),
                    "paidPremiumAtExit": row.get("paid_premium_at_exit"),
                    "horizonYear": row.get("horizon_year"),
                    "irr": None if timing_pending or not audit.get("passed") or vid is None else original_irr,
                    "originalIrr": original_irr, "computedIrr": audit.get("computedIrr"),
                    "arithmeticStatus": "passed" if audit.get("passed") else "pending" if original_irr is None else "failed",
                    "contractStatus": "timing_pending" if timing_pending else "development" if partition == "development" else "source_reviewed",
                    "terminalValue": row.get("terminal_value"), "incomeTotal": row.get("income_total"),
                    "variant": _safe_text(row.get("variant", "")),
                    "status": "待核" if timing_pending or original_irr is None or vid is None else "假设下复算" if nature in ("assumed", "development") else "已确认",
                    "limitations": _strings(row.get("limitations")) + ([reason] if reason else []),
                    "sourceIds": source_ids,
                    "cashflows": [{"timeYear": x["time_year"], "amount": x["amount"], "kind": x.get("kind", "source_unspecified")} for x in row.get("cashflows", [])]}
                # Keep all source locators and denominator/timing context.
                scenario["sourceEvidence"] = [{"sourceId": self.add_source(ref, self.source_date),
                    "locator": _safe_text(ref.get("page", ref.get("locator", ""))),
                    "unit": _safe_text(ref.get("unit", "")), "notes": _safe_text(ref.get("notes", ""))} for ref in refs]
                scenario["scenarioLabel"] = _safe_text(label)
                scenarios.append(scenario)
        return scenarios

    def coverage_report(self):
        index = {}
        for row in self.data["index"]:
            relative = row.get("相对路径", row.get("path"))
            if not relative:
                raise ValueError("资料索引缺相对路径")
            normalized = relative.replace("\\", "/")
            if normalized in index:
                raise ValueError("资料索引来源重复")
            index[normalized] = row
        errors = []
        for relative, row in index.items():
            baseline = self.baseline.get(relative)
            expected = row.get("SHA256", row.get("sha256", "")).lower()
            if baseline is None or expected != baseline["sha256"]:
                errors.append({"filename": Path(relative).name, "reason": "资料索引与分类基线不一致"})
        baseline_only = [{"filename": Path(p).name, "sha256": x["sha256"],
                          "reason": "开发阶段材料，未纳入正式产品资料索引" if p.startswith("产品开发阶段材料/") else "范围差异待核"}
                         for p, x in self.baseline.items() if p not in index]
        return {"baselineCount": len(self.baseline), "indexCount": len(index),
                "baselineHashVerifiedCount": len(self.baseline), "baselineOnly": baseline_only,
                "indexOnly": [{"filename": Path(x).name} for x in index if x not in self.baseline],
                "errors": errors, "passed": not errors and not any(x["reason"] == "范围差异待核" for x in baseline_only)}

    def convert(self):
        coverage = self.coverage_report()
        arithmetic = verify_calculations(self.data["combined"])
        self.convert_facts()
        scenarios = self.convert_scenarios(arithmetic)
        # Do not promote development reported age-80 IRR into independently
        # calculated scenarios. Preserve it only as a sourced research fact.
        development = self.data["combined"].get("development", [])
        for group in ([development] if isinstance(development, dict) else development):
            for item in group.get("reported_age80", []):
                candidates = [v for v in self.versions if v["stage"] == "development" and v["code"] == item.get("product_code")]
                if len(candidates) == 1:
                    v = candidates[0]
                    for label, key in (("开发稿80岁保证IRR载值", "guaranteed_irr_age80"), ("开发稿80岁演示IRR载值", "illustrated_irr_age80")):
                        self.add_fact(v, "利益水平", label + "；" + str(item.get("pay_label", "")), item.get(key), v["sourceIds"], _safe_text(item.get("locator", "")), "开发稿载")
                    self.gaps.append({"versionId": v["id"], "type": "developmentIrr", "message": _safe_text(item.get("limitations", "无逐年利益表，未独立复算"))})
        manifest = {"formatVersion": 1, "sourceDate": self.source_date, "converterVersion": "1",
            "versions": self.versions, "facts": self.facts, "scenarios": scenarios,
            "sources": sorted(self.sources.values(), key=lambda x: x["id"]), "gaps": self.gaps,
            "report": {"coverage": coverage, "arithmetic": arithmetic,
                "identityMappings": self.identity_report,
                "quarantinedScenarioCount": sum(x["versionId"] is None for x in scenarios),
                "timingPendingCount": sum(x["contractStatus"] == "timing_pending" for x in scenarios),
                "sourceInputNames": [Path(p).name for p in INPUTS.values()],
                "sourceInputs": [{"filename": Path(p).name,
                    "sha256": digest_bytes(source_path(self.root, p).read_bytes())}
                    for p in INPUTS.values()],
                "limitations": ["007原件只读；本地转换不确认当前可售", "原件核对范围以来源页码和研究限制为准", "不包含新XIRR、费用实绩或NBV/CSM推算"]}}
        return manifest, self.files


def convert_archive(source_root: str | Path, overrides: dict | None = None):
    return Converter(source_root, overrides).convert()


def build_package(source_root: str | Path, output_zip: str | Path,
                  overrides_path: str | Path | None = None) -> dict:
    output = Path(output_zip).resolve()
    root = Path(source_root).resolve(strict=True)
    if output.is_relative_to(root):
        raise ValueError("输出不能写入只读来源项目")
    overrides = read_json(Path(overrides_path)) if overrides_path else None
    manifest, files = convert_archive(root, overrides)
    if not manifest["report"]["coverage"]["passed"]:
        raise ValueError("来源覆盖不一致，不能生成导入包")
    if not manifest["report"]["arithmetic"]["passed"]:
        raise ValueError("数值回归失败，不能生成导入包；请先运行独立验收工具")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects an earlier valid artifact from overwrite.
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False))
                for entry, path in sorted(files.items()):
                    data = path.read_bytes()
                    if digest_bytes(data) != Path(entry).stem:
                        raise ValueError("转换期间来源发生变更，导入包未通过校验")
                    archive.writestr(entry, data)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return manifest
