import subprocess
from pathlib import Path

from tests.node_runner import node_command


ROOT = Path(__file__).resolve().parents[2]


def test_supervisor_state_verifier_role():
    """evidence >= 2 일 때 verifying phase / verifier role 전이를 확인한다."""
    script = (
        "const S = require('./electron/renderer/supervisor-state.js');"
        "function apply(events) {"
        "  return events.reduce("
        "    (s,e,i) => S.reduce(s, e, {nowMs: 1000+i*100, now: new Date(2026,5,15,9,0,i)}),"
        "    S.initialState()"
        "  );"
        "}"
        "const s = apply(["
        "  {request_id:'rv'},"
        "  {type:'tool_start',tool:'ta'},"
        "  {type:'tool_done',tool:'ta',result:'a'},"
        "  {type:'tool_start',tool:'tb'},"
        "  {type:'tool_done',tool:'tb',result:'b'},"
        "]);"
        "if(s.phase!=='verifying')throw new Error('phase='+s.phase);"
        "if(s.role!=='verifier')throw new Error('role='+s.role);"
        "console.log('verifier role test passed');"
    )
    result = subprocess.run(
        [node_command(), "--eval", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verifier role test passed" in result.stdout


def test_supervisor_state_reducer_fixtures():
    result = subprocess.run(
        [node_command(), "tests/renderer/supervisor-state.test.js"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "supervisor-state fixtures passed" in result.stdout
