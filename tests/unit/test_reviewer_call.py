"""Reviewer 단발 호출(_reviewer_call) 단위 테스트 (Phase 2 — G2 멀티모달 전달).

- I2: tools 배열을 전송하지 않는다(읽기전용·구조적 무실행).
- G2: 화면 캡처(image_url 블록)를 최신 N개까지 Reviewer 입력에 포함한다.
- 안전: LLM 호출 실패 시 passed=True 폴백.
네트워크 없음 — get_client를 레코더로 대체한다.
"""

import json

import pytest

import agent.server as server


class _RecorderLLM:
    """create()에 전달된 messages/tools를 기록하고 고정 판결을 반환한다."""

    def __init__(self, content='{"passed": true}'):
        self.captured = {}
        outer = self

        class _Msg:
            def __init__(self):
                self.content = content

        class _Choice:
            def __init__(self):
                self.message = _Msg()

        class _Resp:
            def __init__(self):
                self.choices = [_Choice()]

        class _Comp:
            def create(self, **kw):
                outer.captured = kw
                return _Resp()

        class _Chat:
            def __init__(self):
                self.completions = _Comp()

        self.chat = _Chat()


def _img_msg(b64="ZmFrZQ=="):
    return {"role": "user", "content": [
        {"type": "text", "text": "화면"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]}


@pytest.fixture
def recorder(monkeypatch):
    llm = _RecorderLLM()
    monkeypatch.setattr(server, "get_client", lambda: llm)
    monkeypatch.setattr(server, "get_model", lambda: "gpt-test")
    return llm


async def test_no_tools_sent_to_reviewer(recorder):
    """I2: Reviewer 호출에 tools 배열이 실리지 않는다."""
    await server._reviewer_call([{"role": "assistant", "content": "완료"}])
    assert "tools" not in recorder.captured or not recorder.captured.get("tools")


async def test_image_blocks_passed_when_kept(recorder, monkeypatch):
    """G2: keep_images>0이면 최신 화면 캡처 image_url 블록이 Reviewer에 전달된다."""
    monkeypatch.setattr(server, "_HARNESS_REVIEWER_IMAGES", 2)
    history = [{"role": "user", "content": "배포해"}, _img_msg()]
    await server._reviewer_call(history)
    sent = recorder.captured.get("messages", [])
    has_image = any(
        isinstance(m.get("content"), list)
        and any(isinstance(b, dict) and b.get("type") == "image_url" for b in m["content"])
        for m in sent
    )
    assert has_image, "Reviewer 입력에 image_url 블록이 없음"


async def test_images_demoted_when_keep_zero(recorder, monkeypatch):
    """멀티모달 미지원 폴백: keep=0이면 image_url 블록이 텍스트로 강등된다."""
    monkeypatch.setattr(server, "_HARNESS_REVIEWER_IMAGES", 0)
    history = [_img_msg(), _img_msg()]
    await server._reviewer_call(history)
    sent = recorder.captured.get("messages", [])
    has_image = any(
        isinstance(m.get("content"), list)
        and any(isinstance(b, dict) and b.get("type") == "image_url" for b in m["content"])
        for m in sent
    )
    assert not has_image, "keep=0인데 image_url 블록이 남아있음"


async def test_verify_prompt_injected(recorder):
    """도메인 verify_prompt가 Reviewer system에 주입된다."""
    await server._reviewer_call([{"role": "assistant", "content": "x"}],
                                verify_prompt="서비스 기동 확인")
    sys_msg = recorder.captured["messages"][0]
    assert sys_msg["role"] == "system"
    assert "서비스 기동 확인" in sys_msg["content"]


async def test_passed_true_fallback_on_error(monkeypatch):
    """LLM 호출이 실패하면 passed=True 안전 폴백(Reviewer 오작동이 실행을 막지 않음)."""
    class _BoomLLM:
        class _Chat:
            class _Comp:
                def create(self, **kw):
                    raise RuntimeError("LLM down")
            def __init__(self):
                self.completions = _BoomLLM._Chat._Comp()
        def __init__(self):
            self.chat = _BoomLLM._Chat()

    monkeypatch.setattr(server, "get_client", lambda: _BoomLLM())
    monkeypatch.setattr(server, "get_model", lambda: "gpt-test")
    verdict = await server._reviewer_call([{"role": "assistant", "content": "x"}])
    assert verdict.passed is True


async def test_harness_generate_records_executor_error_without_reviewer(monkeypatch):
    """Executor errors must be recorded as failed rounds, not reviewed into a pass."""
    captured = []

    async def fake_generate(*args, **kwargs):
        yield server.sse({"type": server.ev.ERROR, "message": "rate limit"})

    async def fail_reviewer(*args, **kwargs):
        raise AssertionError("reviewer must not run after executor error")

    async def fake_record(task_type, thread_id, round_n, verdict, history):
        captured.append({
            "task_type": task_type,
            "thread_id": thread_id,
            "round_n": round_n,
            "verdict": verdict,
            "history": history,
        })

    class FakeSessionManager:
        def get_thread_messages(self, task_type, thread_id):
            return [{"role": "assistant", "content": "partial"}]

    monkeypatch.setattr(server, "generate", fake_generate)
    monkeypatch.setattr(server, "_reviewer_call", fail_reviewer)
    monkeypatch.setattr(server, "_record_harness_round", fake_record)
    monkeypatch.setattr(server, "_HARNESS_MAX_ROUNDS", 1)
    monkeypatch.setattr(server, "get_session_manager", lambda: FakeSessionManager())

    raw_events = [
        raw async for raw in server._harness_generate(
            "do work",
            "thread-1",
            "gmp-validation",
            "auto",
        )
    ]
    events = [json.loads(raw.removeprefix("data: ").strip()) for raw in raw_events]

    assert [item["type"] for item in events] == [
        server.ev.ERROR,
        server.ev.HARNESS_ROUND,
        server.ev.DONE,
    ]
    assert len(captured) == 1
    assert captured[0]["verdict"].passed is False
    assert "rate limit" in captured[0]["verdict"].feedback
