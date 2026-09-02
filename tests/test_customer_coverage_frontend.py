from pathlib import Path
import shutil
import subprocess


def test_customer_alias_coverage_notice():
    node = shutil.which("node")
    assert node, "Node.js is required for customer coverage rendering validation"
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("customer_coverage.test.cjs"))],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
