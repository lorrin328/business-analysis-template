import pathlib
import shutil
import subprocess


def test_upload_requires_preview_and_explicit_confirmation():
    node = shutil.which("node")
    assert node, "Node.js is required for frontend workflow validation"
    result = subprocess.run(
        [node, "--test", str(pathlib.Path(__file__).with_name("upload_workflow.test.cjs"))],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
