from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from market_analysis.config import data_dir
from market_analysis.validator import ReportValidationError, validate_report


REPORT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,95}$")


class MarketAnalysisRepository:
    def __init__(self, root: str | os.PathLike | None = None):
        self.root = Path(root).resolve() if root else data_dir()
        self.reports_dir = self.root / "reports"

    def _read_json(self, path: Path):
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _atomic_write(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def publish(self, report: dict) -> dict:
        validate_report(report)
        report_id = str(report["reportId"])
        if not REPORT_ID_PATTERN.fullmatch(report_id):
            raise ValueError("reportId contains unsupported characters")
        self.validate_history_links(report)
        self._atomic_write(self.reports_dir / f"{report_id}.json", report)
        self._atomic_write(self.root / "latest.json", report)
        return report

    def validate_history_links(self, report: dict) -> None:
        errors: list[str] = []
        current_id = str(report.get("reportId") or "")
        current_at = str(report.get("generatedAt") or "")
        cache: dict[str, dict | None] = {}
        for module in report.get("modules") or []:
            topic_key = str(module.get("topicKey") or "")
            history = module.get("history") or {}
            state = str(history.get("state") or "")
            previous_id = str(history.get("previousReportId") or "")
            label = f"module {module.get('id')}"
            timeline = self.topic_timeline(topic_key, limit=36)
            if state == "new":
                if timeline:
                    errors.append(f"{label}: existing topicKey cannot be classified as new")
                continue
            if not previous_id or previous_id == current_id:
                errors.append(f"{label}: invalid previousReportId")
                continue
            if not timeline or str(timeline[-1].get("reportId") or "") != previous_id:
                errors.append(f"{label}: previousReportId must be the latest report for this topic")
            if previous_id not in cache:
                cache[previous_id] = self.get(previous_id)
            previous = cache[previous_id]
            if not previous:
                errors.append(f"{label}: previous report does not exist")
                continue
            previous_module = next(
                (item for item in previous.get("modules") or [] if str(item.get("topicKey") or "") == topic_key),
                None,
            )
            if not previous_module:
                errors.append(f"{label}: topicKey does not exist in previous report")
            elif str((previous_module.get("history") or {}).get("since") or "") != str(history.get("since") or ""):
                errors.append(f"{label}: history.since must be carried forward from the previous topic")
            try:
                if datetime.fromisoformat(str(previous.get("generatedAt")).replace("Z", "+00:00")) >= datetime.fromisoformat(current_at.replace("Z", "+00:00")):
                    errors.append(f"{label}: previous report is not older than current report")
            except (TypeError, ValueError):
                errors.append(f"{label}: report timestamps cannot be compared")
        if errors:
            raise ReportValidationError(errors)

    def latest(self) -> dict | None:
        return self._read_json(self.root / "latest.json")

    def get(self, report_id: str) -> dict | None:
        if not REPORT_ID_PATTERN.fullmatch(str(report_id or "")):
            return None
        return self._read_json(self.reports_dir / f"{report_id}.json")

    def history(self, limit: int = 24) -> list[dict]:
        rows: list[dict] = []
        if not self.reports_dir.is_dir():
            return rows
        for path in self.reports_dir.glob("*.json"):
            try:
                report = self._read_json(path) or {}
            except (OSError, json.JSONDecodeError):
                continue
            rows.append({
                "reportId": report.get("reportId"),
                "title": report.get("title"),
                "generatedAt": report.get("generatedAt"),
                "period": report.get("period"),
                "headline": (report.get("executiveSummary") or {}).get("headline"),
                "reviewStatus": report.get("reviewStatus"),
                "moduleCount": len(report.get("modules") or []),
                "sourceCount": len(report.get("sources") or []),
            })
        rows.sort(key=lambda item: str(item.get("generatedAt") or ""), reverse=True)
        return rows[: max(1, min(int(limit), 100))]

    def topic_timeline(self, topic_key: str, limit: int = 12) -> list[dict]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", str(topic_key or "")):
            return []
        timeline: list[dict] = []
        for item in reversed(self.history(limit=100)):
            report = self.get(str(item.get("reportId") or "")) or {}
            for module in report.get("modules") or []:
                if module.get("topicKey") != topic_key:
                    continue
                timeline.append({
                    "reportId": report.get("reportId"),
                    "generatedAt": report.get("generatedAt"),
                    "title": module.get("title"),
                    "state": (module.get("history") or {}).get("state"),
                    "fact": module.get("fact"),
                    "judgment": module.get("judgment"),
                    "confidence": module.get("confidence"),
                    "evidenceIds": module.get("evidenceIds") or [],
                })
        return timeline[-max(1, min(int(limit), 36)):]

    def status(self) -> dict:
        return self._read_json(self.root / "status.json") or {
            "state": "never_run",
            "message": "尚未生成市场研判报告",
            "updatedAt": None,
        }

    def write_status(self, status: dict) -> None:
        self._atomic_write(self.root / "status.json", status)
