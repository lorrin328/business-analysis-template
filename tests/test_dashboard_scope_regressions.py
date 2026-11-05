from pathlib import Path
import shutil
import subprocess


def test_dashboard_scope_regressions():
    node = shutil.which('node')
    assert node, 'Node.js is required for dashboard scope behavior checks'
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, '--test', str(root / 'tests' / 'dashboard_scope_regressions.test.cjs')],
        cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
