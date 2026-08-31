"""Tax calculator delivery checks; browser arithmetic is exercised by Node's test runner."""
from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_tax_calculator_arithmetic():
    node = shutil.which("node")
    assert node, "Tax calculator tests require Node.js 18+ (no npm dependencies)."
    completed = subprocess.run(
        [node, "--test", str(ROOT / "tests" / "tax_calculator.test.cjs")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_tax_calculator_pages_and_scripts_served():
    from main import app

    client = TestClient(app)
    for path in ("/tax-calculator", "/tax-calculator.html"):
        response = client.get(path)
        assert response.status_code == 200
        assert "税优产品测算" in response.text
        assert 'id="annualIncome"' in response.text
    for name in ("tax-calculator-core.js", "tax-calculator.js"):
        response = client.get(f"/js/{name}?v=20260831")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]


def test_calculator_is_local_and_does_not_collect_income():
    html = (ROOT / "tax-calculator.html").read_text(encoding="utf-8")
    scripts = "\n".join((ROOT / "js" / name).read_text(encoding="utf-8") for name in (
        "tax-calculator-core.js", "tax-calculator.js"
    ))
    for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "localStorage", "sessionStorage", "console.log", "location.search"):
        assert forbidden not in scripts
    assert '<script src="http' not in html
    assert 'autocomplete="off"' in html
    assert 'action=' not in html
    assert 'name="annualIncome"' not in html
    assert 'rel="noopener noreferrer"' in html


def test_calculator_navigation_and_nginx_whitelist():
    dashboard = (ROOT / "经营分析模板.html").read_text(encoding="utf-8")
    nginx = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")
    assert 'data-dashboard-href="/tax-calculator"' in dashboard
    assert 'location = /tax-calculator {' in nginx
    assert 'location = /tax-calculator.html {' in nginx
