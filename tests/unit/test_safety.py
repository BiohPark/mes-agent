"""파괴적 작업 가드(S2/S4/S5) 단위 테스트."""

import json
import os

from agent.tools._safety import (
    is_dangerous_command,
    is_protected_path,
    backup_file,
    classify_risk,
)
from agent.tools.process import run_command, start_process
from agent.tools.document import write_file


# ── 위험 명령 탐지 ───────────────────────────────────────────
def test_dangerous_command_detection():
    assert is_dangerous_command("Remove-Item C:\\data -Recurse -Force")
    assert is_dangerous_command("del /s /q C:\\temp")
    assert is_dangerous_command("format C:")
    assert is_dangerous_command("shutdown /s /t 0")
    assert is_dangerous_command("vssadmin delete shadows /all")
    # 안전한 명령은 False
    assert not is_dangerous_command("echo hello")
    assert not is_dangerous_command("Get-Process")
    assert not is_dangerous_command("dir C:\\")


def test_run_command_blocks_dangerous_without_force():
    res = json.loads(run_command("Remove-Item C:\\ -Recurse -Force"))
    assert res.get("blocked") is True
    assert res["success"] is False


def test_run_command_allows_safe():
    res = json.loads(run_command("echo hi", shell="cmd"))
    assert res.get("blocked") is not True
    assert "hi" in res.get("stdout", "")


def test_start_process_blocks_dangerous():
    res = json.loads(start_process("shutdown /s /t 0"))
    assert res.get("blocked") is True


# ── 보호 경로 ────────────────────────────────────────────────
def test_protected_path_detection():
    sysroot = os.environ.get("SystemRoot", "C:\\Windows")
    assert is_protected_path(os.path.join(sysroot, "System32", "evil.dll"))
    # 사용자 임시 폴더는 보호 대상 아님
    assert not is_protected_path(os.path.join(os.environ.get("TEMP", "C:\\Temp"), "ok.txt"))


def test_write_file_blocks_protected(tmp_path):
    sysroot = os.environ.get("SystemRoot", "C:\\Windows")
    res = json.loads(write_file(os.path.join(sysroot, "System32", "x.txt"), "x"))
    assert res.get("blocked") is True


def test_write_file_backs_up_on_overwrite(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("original", encoding="utf-8")
    res = json.loads(write_file(str(p), "new content"))
    assert res.get("backup")  # 백업 경로 존재
    assert p.read_text(encoding="utf-8") == "new content"
    assert list(tmp_path.glob("doc.*.txt.bak"))


def test_backup_file_none_when_missing(tmp_path):
    assert backup_file(str(tmp_path / "nope.txt")) is None


# ── G3: 중앙 위험도 분류 classify_risk ────────────────────────────
def test_classify_safe_read_observe_input():
    assert classify_risk("read_file", {"path": "C:\\Users\\me\\a.txt"}) == "safe"
    assert classify_risk("mouse_click", {"x": 10, "y": 20}) == "safe"
    assert classify_risk("workflow_set_step", {"step_id": "s1"}) == "safe"
    assert classify_risk("ask_user", {"question": "ok?"}) == "safe"
    assert classify_risk("screen_ocr_region", {}) == "safe"
    assert classify_risk("obsidian_search", {"query": "메모"}) == "safe"


def test_classify_run_command_content_based():
    assert classify_risk("run_command", {"command": "Get-Process"}) == "safe"
    assert classify_risk("run_command", {"command": "dir C:\\"}) == "safe"
    assert classify_risk("run_command", {"command": "pip install x"}) == "mutate"
    # 복합 명령은 읽기전용으로 단정하지 않음(뒤에 변형 명령 가능) → 최소 mutate
    assert classify_risk("run_command", {"command": "Get-Process; Set-Content a.txt b"}) == "mutate"
    # 복합 명령 안에 위험 명령이 섞이면 destructive
    assert classify_risk("run_command", {"command": "Get-Process; del /s C:\\x"}) == "destructive"
    assert classify_risk("run_command", {"command": "Remove-Item C:\\ -Recurse"}) == "destructive"


def test_classify_mutate_by_verb():
    assert classify_risk("write_file", {"path": "C:\\tmp\\a.txt"}) == "mutate"
    assert classify_risk("word_edit_text", {"path": "a.docx"}) == "mutate"
    assert classify_risk("excel_set_cells", {"path": "a.xlsx"}) == "mutate"
    assert classify_risk("obsidian_write_note", {"path": "n.md"}) == "mutate"
    assert classify_risk("foo_delete_bar", {}) == "mutate"


def test_classify_destructive_protected_path():
    sysroot = os.environ.get("SystemRoot", "C:\\Windows")
    target = os.path.join(sysroot, "System32", "x.txt")
    assert classify_risk("write_file", {"path": target}) == "destructive"


def test_classify_allowlist_makes_safe():
    assert classify_risk("run_command", {"command": "pip install x"}) == "mutate"
    assert classify_risk("run_command", {"command": "pip install x"}, allowlist={"run_command"}) == "safe"


def test_classify_accepts_json_string_args():
    assert classify_risk("run_command", '{"command": "Get-Process"}') == "safe"
    assert classify_risk("write_file", '{"path": "a.txt"}') == "mutate"
