"""Run real JavaScript request ordering and customer import regressions in CI."""
from pathlib import Path
import shutil
import subprocess


def test_frontend_request_safety():
    node = shutil.which("node")
    assert node, "Node.js is required for frontend request safety validation"
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, "--test", str(root / "tests" / "frontend_request_safety.test.cjs")],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
