"""office_com 무한 행 방지 — _on_com_thread 타임아웃 + PID 스코프 복구 (긴급수정 A2).

실제 MS Office/win32com 없이 검증한다(느린 가짜 핸들러 + monkeypatch psutil).
"""
import time
import pytest

from agent.tools import office_com as oc


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    oc._tracked_pids.clear()
    yield
    oc._tracked_pids.clear()


def test_timeout_returns_structured_error(monkeypatch):
    monkeypatch.setenv("OFFICE_COM_TIMEOUT", "0.2")

    def slow(a, b):
        time.sleep(2.0)
        return "정상결과"

    wrapped = oc._on_com_thread(slow, "excel_set_cells")
    out = wrapped(1, 2)
    # 무한 대기 대신 구조화 오류('툴 실행 오류' 접두 → 기존 UI/서버 에러 분기 재사용)
    assert out.startswith("툴 실행 오류")
    assert "excel_set_cells" in out


def test_recovers_for_next_call(monkeypatch):
    monkeypatch.setenv("OFFICE_COM_TIMEOUT", "0.2")

    def slow():
        time.sleep(2.0)
        return "slow"

    def fast():
        return "fast-ok"

    assert oc._on_com_thread(slow, "word_edit_text")().startswith("툴 실행 오류")
    # 멈춘 워커를 버리고 executor를 재생성했으므로 다음 호출은 정상 동작해야 한다
    assert oc._on_com_thread(fast, "excel_get_range")() == "fast-ok"


def test_recover_kills_only_tracked_pids(monkeypatch):
    killed = []

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def kill(self):
            killed.append(self.pid)

    monkeypatch.setattr(oc.psutil, "Process", FakeProc)
    oc._tracked_pids.update({4321, 8765})

    oc._recover_stuck_com()

    assert sorted(killed) == [4321, 8765]   # 추적된 우리 인스턴스만 종료
    assert oc._tracked_pids == set()        # 추적 목록 비움
