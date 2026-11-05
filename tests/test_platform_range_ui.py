from pathlib import Path
import shutil
import subprocess


def test_platform_range_browser_behavior():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([shutil.which('node'), '--test', str(root / 'tests/platform_range_ui.test.cjs')],
                            cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
