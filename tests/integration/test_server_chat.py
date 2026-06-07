"""채팅 SSE 스트림 통합 테스트.

LLM 클라이언트는 conftest의 FakeLLMClient로 교체되어 실제 API를 호출하지 않는다.
SSE 이벤트 타입의 순서와 존재 여부를 검증한다.
"""

import json
import pytest
from agent.core import events as ev


def _parse_sse(text: str) -> list[dict]:
    """SSE 응답 텍스트를 이벤트 딕셔너리 목록으로 파싱한다."""
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


class TestChatSSE:
    async def test_done_event_present(self, client):
        """채팅 응답에는 반드시 DONE 이벤트가 포함되어야 한다."""
        async with client.stream("POST", "/chat", json={"message": "안녕"}) as resp:
            assert resp.status_code == 200
            text = await resp.aread()
        events = _parse_sse(text.decode())
        types = [e.get("type") for e in events]
        assert ev.DONE in types

    async def test_request_id_is_first_event(self, client):
        """첫 번째 이벤트는 request_id여야 한다."""
        async with client.stream("POST", "/chat", json={"message": "hello"}) as resp:
            text = await resp.aread()
        events = _parse_sse(text.decode())
        assert events, "이벤트가 없음"
        assert ev.REQUEST_ID in events[0]

    async def test_text_event_contains_content(self, client):
        """LLM이 텍스트를 반환하면 TEXT 이벤트가 포함되어야 한다."""
        async with client.stream("POST", "/chat", json={"message": "테스트"}) as resp:
            text = await resp.aread()
        events = _parse_sse(text.decode())
        text_events = [e for e in events if e.get("type") == ev.TEXT]
        assert text_events, "TEXT 이벤트 없음"
        assert any(e.get("content") for e in text_events)

    async def test_agent_state_events_present(self, client):
        """thinking → idle 순서로 AGENT_STATE 이벤트가 있어야 한다."""
        async with client.stream("POST", "/chat", json={"message": "상태 확인"}) as resp:
            text = await resp.aread()
        events = _parse_sse(text.decode())
        state_events = [e["state"] for e in events if e.get("type") == ev.AGENT_STATE]
        assert "thinking" in state_events
        assert "idle" in state_events

    async def test_context_usage_event_present(self, client):
        """컨텍스트 사용량 이벤트가 포함되어야 한다."""
        async with client.stream("POST", "/chat", json={"message": "컨텍스트"}) as resp:
            text = await resp.aread()
        events = _parse_sse(text.decode())
        usage = [e for e in events if e.get("type") == ev.CONTEXT_USAGE]
        assert usage
        assert "tokens_used" in usage[0]
        assert "tokens_total" in usage[0]

    async def test_no_error_event_on_normal_response(self, client):
        """정상 응답에서는 ERROR 이벤트가 없어야 한다."""
        async with client.stream("POST", "/chat", json={"message": "오류 없음"}) as resp:
            text = await resp.aread()
        events = _parse_sse(text.decode())
        error_events = [e for e in events if e.get("type") == ev.ERROR]
        assert not error_events


class TestStopAgent:
    async def test_stop_known_request_id(self, client):
        """등록된 request_id에 대한 중단 요청은 ok를 반환해야 한다."""
        resp = await client.post("/stop/fake-request-id")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_stop_unknown_request_id_is_ok(self, client):
        """등록되지 않은 id도 오류 없이 처리되어야 한다."""
        resp = await client.post("/stop/nonexistent-id-xyz")
        assert resp.status_code == 200


class TestConfirm:
    async def test_confirm_unknown_id_returns_ok(self, client):
        """pending confirm 없이 응답해도 서버가 오류를 반환하지 않아야 한다."""
        payload = {"choice": "확인", "custom_text": ""}
        resp = await client.post("/confirm/no-such-confirm-id", json=payload)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
