"""Validate the actual page asset references and reject runtime artifacts."""
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_release_files import disallowed
from scripts.verify_image import PAGES, content_issues


@pytest.mark.parametrize("path", [
    "excel/source.csv", "backend/market_analysis_data/run/analysis.py",
    "backend/.venv/lib/module.py", "backend/venv.next/lib/module.py",
    "backend/.venv.previous/lib/module.py", "deploy/.ai_env", "deploy/.market_analysis_env",
    "data/reference/CUSTOMERS.CSV", "backend/cache.sqlite-wal", "backend/cache.sqlite3-shm",
    "backend\\venv\\lib\\module.py", "backup/production.XLSM", "js/upload.sync-conflict.js",
])
def test_release_guard_rejects_data_and_runtime_paths(path):
    assert disallowed(path)


@pytest.mark.parametrize("path", ["backend/main.py", "backend/requirements.txt", "js/api-client.js", "docs/DOCKER.md", ".env.example"])
def test_release_guard_preserves_application_sources(path):
    assert not disallowed(path)


@pytest.fixture
def image_tree(tmp_path):
    for page in PAGES:
        shutil.copyfile(ROOT / page, tmp_path / page)
    (tmp_path / "js").mkdir()
    for script in (ROOT / "js").glob("*.js"):
        if "sync-conflict" not in script.name:
            shutil.copyfile(script, tmp_path / "js" / script.name)
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/main.py").write_text("# synthetic module", encoding="utf-8")
    (tmp_path / "backend/requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "VERSION").write_text("synthetic", encoding="utf-8")
    return tmp_path


def test_all_current_page_resources_fit_image_whitelist(image_tree):
    assert content_issues(image_tree) == []


@pytest.mark.parametrize("rel", [
    "backend/.venv/lib/unexpected.py", "backend/venv.next/unexpected.py",
    "backend/market_analysis_data/run/unexpected.py", "backend/unexpected.csv",
    "backend/.secret_env", "backend/helper.sync-conflict.py",
])
def test_image_inspection_rejects_forbidden_actual_files(image_tree, rel):
    path = image_tree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic", encoding="utf-8")
    assert any(rel in issue for issue in content_issues(image_tree))


def test_image_inspection_rejects_missing_linked_script(image_tree):
    (image_tree / "js/api-client.js").unlink()
    issues = content_issues(image_tree)
    assert any("Missing or invalid local asset" in issue and "api-client.js" in issue for issue in issues)


def test_image_inspection_rejects_asset_outside_app(image_tree):
    with (image_tree / "honor.html").open("a", encoding="utf-8") as handle:
        handle.write('<script src="/../outside.js"></script>')
    assert any("outside.js" in issue for issue in content_issues(image_tree))


def test_image_inspection_requires_every_page(image_tree):
    (image_tree / "scheme-calculator.html").unlink()
    assert any("Required runtime file missing: scheme-calculator.html" == issue for issue in content_issues(image_tree))
