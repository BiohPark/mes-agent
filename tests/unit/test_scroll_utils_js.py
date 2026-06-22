import subprocess
from pathlib import Path

from tests.node_runner import node_command


ROOT = Path(__file__).resolve().parents[2]


def test_scroll_utils_reducer_fixtures():
    result = subprocess.run(
        [node_command(), "tests/renderer/scroll-utils.test.js"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scroll-utils fixtures passed" in result.stdout
