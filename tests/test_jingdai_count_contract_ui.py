"""Run the count-contract rendering and XSS regression in the real JS engine."""
from pathlib import Path
import shutil
import subprocess


def test_jingdai_count_contract_ui():
    node = shutil.which('node')
    assert node, 'Node.js is required for count-contract frontend verification'
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, '--test', str(root / 'tests' / 'jingdai_count_contract_ui.test.cjs')],
                            cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
