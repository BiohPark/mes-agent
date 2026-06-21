import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_scroll_utils_reducer_fixtures():
    result = subprocess.run(
        ["node", "tests/renderer/scroll-utils.test.js"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scroll-utils fixtures passed" in result.stdout
