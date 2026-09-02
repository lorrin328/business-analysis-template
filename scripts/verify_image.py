"""Run inside the built image; verify packaged files, local assets and account."""
from html.parser import HTMLParser
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

PAGES = {
    "经营分析模板.html", "branch-analysis.html", "customer-analysis.html", "honor.html",
    "market-analysis.html", "personnel-management.html", "scheme-calculator.html",
    "tax-calculator.html", "zhituo-analysis.html",
}
FORBIDDEN_PARTS = {".venv", "venv", "__pycache__", "node_modules", "excel", "backups", "market_analysis_data", "logs"}


class LocalAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "img", "source"} and attrs.get("src"):
            self.urls.append(attrs["src"])
        if tag == "link" and attrs.get("href") and set(attrs.get("rel", "").split()) & {"stylesheet", "icon", "modulepreload"}:
            self.urls.append(attrs["href"])


def content_issues(root: Path) -> list[str]:
    root = root.resolve()
    issues = []
    required = PAGES | {"VERSION", "backend/main.py", "backend/requirements.txt", "js/api-client.js"}
    for rel in sorted(required):
        if not (root / rel).is_file():
            issues.append("Required runtime file missing: " + rel)
    for path in root.rglob("*"):
        if path.is_symlink():
            issues.append("Unexpected image symlink: " + path.relative_to(root).as_posix())
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        lower_parts = tuple(part.lower() for part in rel.parts)
        allowed = (
            (len(rel.parts) == 1 and (path.name in PAGES or path.name == "VERSION"))
            or (rel.parts[0] == "js" and len(rel.parts) == 2 and path.suffix == ".js")
            or (rel.parts[0] == "backend" and (path.suffix == ".py" or rel.as_posix() == "backend/requirements.txt"))
        )
        forbidden = (
            bool(set(lower_parts) & FORBIDDEN_PARTS)
            or any(part.startswith(("venv.", ".venv.", ".env")) or part.endswith("_env") for part in lower_parts)
            or "sync-conflict" in rel.as_posix().lower()
        )
        if not allowed or forbidden:
            issues.append("Unexpected image file: " + rel.as_posix())
        if path.parent == root and path.name in PAGES:
            parser = LocalAssets()
            parser.feed(path.read_text(encoding="utf-8"))
            for url in parser.urls:
                parsed = urlsplit(url)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                asset = (root / unquote(parsed.path).lstrip("/")).resolve()
                if not asset.is_relative_to(root) or not asset.is_file():
                    issues.append(f"Missing or invalid local asset in {path.name}: {parsed.path}")
    return issues


def main():
    root = Path("/app")
    if os.getuid() == 0:
        raise SystemExit("Container must run as an unprivileged account")
    issues = content_issues(root)
    for rel in (".", "backend", "js", "backend/main.py"):
        if os.access(root / rel, os.W_OK):
            issues.append("Runtime account can modify source: " + rel)
    if issues:
        raise SystemExit("\n".join(issues))
    print("Image content, local assets, account and source permissions: ok")


if __name__ == "__main__":
    main()
