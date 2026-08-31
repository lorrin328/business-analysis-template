"""Exercise organization zero-streak rendering and period selection with Node.js."""
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_org_zero_streak_frontend_behavior():
    node = shutil.which("node")
    assert node, "Organization zero-streak tests require Node.js 18+ (no npm dependencies)."
    completed = subprocess.run(
        [node, "--test", str(ROOT / "tests" / "org_zero_streak.test.cjs")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
