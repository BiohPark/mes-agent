"""agent/core/timeouts.py — 도구 타임아웃 순수 로직 테스트 (긴급수정 A1)."""
import importlib
import pytest

from agent.core import timeouts as T


# ── tool_baseline ────────────────────────────────────────────────
def test_baseline_known_tool():
    assert T.tool_baseline("file_exists") < 1.0  # 즉시성 조회는 짧게
    assert T.tool_baseline("list_directory") <= 1.0


def test_baseline_prefix_category():
    # 개별 미등록이지만 접두 카테고리로 잡힘
    assert T.tool_baseline("browser_click") == T.tool_baseline("browser_navigate")
    # office는 즉시성 조회보다 길게(열기+편집)지만, 너무 늦지 않게 내레이션
    assert T.tool_baseline("excel_set_cells") > T.tool_baseline("file_exists")
    assert T.tool_baseline("excel_set_cells") >= 8.0


def test_baseline_unknown_uses_default():
    assert T.tool_baseline("some_unknown_tool_xyz") == T.DEFAULT_BASELINE


def test_baseline_env_override(monkeypatch):
    monkeypatch.setenv("TOOL_BASELINE_OVERRIDES", '{"file_exists": 9.5}')
    assert T.tool_baseline("file_exists") == 9.5


# ── escalation_schedule ─────────────────────────────────────────
def test_schedule_grows_and_caps():
    s = T.escalation_schedule(1.0, 90.0, factor=4.0)
    assert s[0] == 1.0
    assert s[-1] == 90.0
    assert s == sorted(s)            # 단조 증가
    assert len(set(s)) == len(s)     # 중복 없음
    assert s == [1.0, 4.0, 16.0, 64.0, 90.0]


def test_schedule_baseline_ge_cap():
    s = T.escalation_schedule(120.0, 90.0)
    assert s == [90.0]


def test_schedule_handles_zero_baseline():
    s = T.escalation_schedule(0.0, 10.0)
    assert s[0] > 0 and s[-1] == 10.0


# ── classify_timeout / 에러 텍스트 ───────────────────────────────
def test_classify_stuck_vs_slow():
    stuck = T.classify_timeout("excel_set_cells", 45.0, progressed=False)
    slow = T.classify_timeout("excel_set_cells", 45.0, progressed=True)
    assert stuck["failureClass"] == "stuck"
    assert slow["failureClass"] == "slow"
    assert stuck["provenance"] == "dispatch.timeout"
    assert "hint" in stuck and stuck["tool"] == "excel_set_cells"


def test_liveness_observation_progress_signal_classifies_slow():
    obs = T.LivenessObservation(
        elapsed_seconds=10.0,
        process_alive=True,
        stdout_bytes=12,
        stderr_bytes=0,
        no_progress_count=3,
    )

    info = T.classify_liveness("run_command", 10.0, obs)

    assert info["failureClass"] == "slow"
    assert info["provenance"] == "dispatch.timeout.liveness"
    assert info["liveness"]["stdout_bytes"] == 12


def test_liveness_observation_repeated_no_progress_classifies_stuck():
    obs = T.LivenessObservation(
        elapsed_seconds=10.0,
        process_alive=True,
        stdout_bytes=0,
        stderr_bytes=0,
        no_progress_count=2,
    )

    info = T.classify_liveness("run_command", 10.0, obs)

    assert info["failureClass"] == "stuck"
    assert "no_progress_count" in info["liveness"]


def test_liveness_observation_process_exited_race_is_stuck_not_alive_slow():
    obs = T.LivenessObservation(
        elapsed_seconds=10.0,
        process_alive=False,
        stdout_bytes=0,
        stderr_bytes=0,
        no_progress_count=1,
    )

    info = T.classify_liveness("run_command", 10.0, obs)

    assert info["failureClass"] == "stuck"
    assert info["liveness"]["process_alive"] is False


def test_timeout_error_text_prefix_for_ui_reuse():
    txt = T.timeout_error_text("excel_set_cells", 45.0, progressed=False)
    # 기존 UI/서버 에러 분기(‘툴 실행 오류’ 접두) 재사용을 위해 반드시 이 접두여야 함
    assert txt.startswith("툴 실행 오류")
    assert "excel_set_cells" in txt


def test_timeout_error_text_accepts_liveness_observation():
    obs = T.LivenessObservation(
        elapsed_seconds=3.0,
        process_alive=True,
        stdout_bytes=5,
        stderr_bytes=0,
        no_progress_count=0,
    )

    txt = T.timeout_error_text("run_command", 3.0, observation=obs)

    assert txt.startswith("툴 실행 오류")
    assert "run_command" in txt
    assert "slow" in txt
