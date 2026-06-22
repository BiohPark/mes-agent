import subprocess
from pathlib import Path

from tests.node_runner import node_command


ROOT = Path(__file__).resolve().parents[2]


def test_inject_mes_agent_env_fixtures():
    result = subprocess.run(
        [node_command(), "tests/hooks/inject-mes-agent-env.test.mjs"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "inject-mes-agent-env fixtures passed" in result.stdout
