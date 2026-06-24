import subprocess
from pathlib import Path

from tests.node_runner import node_command


ROOT = Path(__file__).resolve().parents[2]


def test_busy_mode_body_class_fixtures():
    result = subprocess.run(
        [node_command(), "tests/renderer/busy-mode.test.js"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "busy-mode fixtures passed" in result.stdout
