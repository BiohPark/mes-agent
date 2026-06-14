"""run_command liveness spike — timeout 시 진행 신호를 구조화한다."""

import json

from agent.tools.process import run_command


def test_run_command_timeout_with_stdout_progress_is_slow():
    res = json.loads(run_command("echo tick & ping -n 3 127.0.0.1 > nul",
                                 timeout=1, shell="cmd"))

    assert res["success"] is False
    assert res["error"].startswith("툴 실행 오류")
    assert res["timeout"]["failureClass"] == "slow"
    assert res["timeout"]["liveness"]["stdout_bytes"] > 0


def test_run_command_timeout_without_progress_is_stuck():
    res = json.loads(run_command("ping -n 3 127.0.0.1 > nul",
                                 timeout=1, shell="cmd"))

    assert res["success"] is False
    assert res["timeout"]["failureClass"] == "stuck"
    assert res["timeout"]["liveness"]["stdout_bytes"] == 0


def test_run_command_normal_completion_keeps_existing_shape():
    res = json.loads(run_command("echo done", timeout=5, shell="cmd"))

    assert res["success"] is True
    assert res["returncode"] == 0
    assert "done" in res["stdout"]
    assert "timeout" not in res
