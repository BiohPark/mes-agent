"""작업 중 개입(끼어들기) — 백로그 Q.

실행 중 /inject 로 들어온 메시지를 generate() 루프가 단계 경계에서
user 메시지로 주입(I1 도구 짝 보존)하고 INJECTED SSE를 발행하는지 검증한다.
"""

import asyncio
import json
import pytest
from agent.core import events as ev


# ── 스크립트 LLM (test_server_chat 패턴 재현, 자기완결) ──────────────

class _Fn:
    def __init__(self, name="", arguments=""):
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, index=0, id="tc1", name="read_file", arguments='{"path":"a.txt"}'):
        self.index = index
        self.id = id
        self.function = _Fn(name, arguments)


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _Choice:
    def __init__(self, content=None, tool_calls=None, finish_reason=None):
        self.delta = _Delta(content, tool_calls)
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, content=None, tool_calls=None, finish_reason=None):
        self.choices = [_Choice(content=content, tool_calls=tool_calls, finish_reason=finish_reason)]


def _guard_tools(kw):
    tools = kw.get("tools")
    if tools is not None and len(tools) > 128:
        raise ValueError(f"Invalid 'tools': array too long ({len(tools)} > 128)")


class _ScriptedStream:
    script: list = []
    _i = 0

    @classmethod
    def reset(cls, script):
        cls.script = list(script)
        cls._i = 0

    def __iter__(self):
        i = type(self)._i
        type(self)._i += 1
        phase = type(self).script[i] if i < len(type(self).script) else ("text", "완료")
        if phase[0] == "tool":
            yield _Chunk(tool_calls=[_TC(id=f"tc{i}", name=phase[1], arguments=phase[2])])
            yield _Chunk(finish_reason="tool_calls")
        else:
            yield _Chunk(content=phase[1])
            yield _Chunk(finish_reason="stop")


class _ScriptedLLM:
    class _Comp:
        def create(self, **kw):
            _guard_tools(kw)
            return _ScriptedStream()

    class _Chat:
        def __init__(self):
            self.completions = _ScriptedLLM._Comp()

    def __init__(self):
        self.chat = _ScriptedLLM._Chat()


@pytest.fixture
async def client_inj(vault, monkeypatch):
    """스크립트 LLM + run_tool 기록기. 끼어들기 큐 드레인 검증용."""
    import agent.server as srv
    srv._session_allowlists.clear()
    srv._pending_messages.clear()
    monkeypatch.setattr("agent.server.get_client", lambda: _ScriptedLLM())
    monkeypatch.setattr("agent.server.get_model", lambda: "gpt-test")

    def _rec(name, args):
        return '{"ok": true}'

    monkeypatch.setattr("agent.server.run_tool", _rec)

    from httpx import AsyncClient, ASGITransport
    from agent.server import app
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


async def _stream_injecting(client, payload, inject_texts):
    """채팅 SSE를 받으며, 활성 request_id가 나타나면 /inject 로 메시지를 큐에 넣는다."""
    import agent.server as srv

    async def _injector():
        done = set()
        while True:
            await asyncio.sleep(0.01)
            for rid in list(srv._pending_messages.keys()):
                if rid in done:
                    continue
                done.add(rid)
                for t in inject_texts:
                    await client.post(f"/inject/{rid}", json={"message": t})

    task = asyncio.create_task(_injector())
    try:
        async with client.stream("POST", "/chat", json=payload) as resp:
            text = await resp.aread()
    finally:
        task.cancel()
    return _parse_sse(text.decode())


def _saved(tid):
    from agent.obsidian_session import get_session_manager
    return get_session_manager().get_thread_messages("general", tid)


class TestInjectEndpoint:
    async def test_inject_unknown_request_returns_not_ok(self, client):
        """활성 요청이 아닌 id로 주입하면 ok=False 를 반환한다."""
        resp = await client.post("/inject/no-such-request", json={"message": "안녕"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False

    async def test_inject_active_request_queues(self, client):
        """활성 request_id면 메시지가 큐에 적재되고 ok=True."""
        import agent.server as srv
        srv._pending_messages["rid-active"] = []
        try:
            resp = await client.post("/inject/rid-active", json={"message": "추가 지시"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["queued"] == 1
            assert srv._pending_messages["rid-active"] == ["추가 지시"]
        finally:
            srv._pending_messages.pop("rid-active", None)


class TestInjectionDrain:
    async def test_injected_message_not_persisted_as_user(self, client_inj):
        """실행 중 주입한 메시지는 런타임에만 쓰고 영속 대화에는 저장하지 않는다."""
        create = await client_inj.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        # 여러 도구 단계 → 루프가 여러 번 돌며 드레인 기회 제공
        _ScriptedStream.reset(
            [("tool", "read_file", '{"path":"a.txt"}')] * 4 + [("text", "끝")])
        await _stream_injecting(
            client_inj,
            {"message": "긴 작업", "thread_id": tid, "task_type": "general"},
            ["방향을 바꿔줘"],
        )
        saved = _saved(tid)
        injected = [
            m for m in saved
            if m.get("role") == "user" and isinstance(m.get("content"), str)
            and "[사용자 끼어들기]" in m["content"] and "방향을 바꿔줘" in m["content"]
        ]
        assert not injected, "끼어들기 제어 메시지가 영속 대화에 저장되면 안 됨"

    async def test_injected_event_emitted(self, client_inj):
        """주입이 반영되면 INJECTED SSE 이벤트를 발행한다."""
        create = await client_inj.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        _ScriptedStream.reset(
            [("tool", "read_file", '{"path":"a.txt"}')] * 4 + [("text", "끝")])
        events = await _stream_injecting(
            client_inj,
            {"message": "긴 작업", "thread_id": tid, "task_type": "general"},
            ["끼어든다"],
        )
        injected_evts = [e for e in events if e.get("type") == ev.INJECTED]
        assert injected_evts, "INJECTED 이벤트 없음"
        assert any("끼어든다" in (e.get("content") or "") for e in injected_evts)
        assert ev.DONE in [e.get("type") for e in events]

    async def test_injection_preserves_tool_pairs(self, client_inj):
        """드레인은 도구 묶음 사이에서만 일어나 orphan tool 을 만들지 않는다(I1)."""
        from agent.core.compaction import has_orphan_tool
        create = await client_inj.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        _ScriptedStream.reset(
            [("tool", "read_file", '{"path":"a.txt"}')] * 4 + [("text", "끝")])
        await _stream_injecting(
            client_inj,
            {"message": "긴 작업", "thread_id": tid, "task_type": "general"},
            ["중간 지시"],
        )
        saved = _saved(tid)
        assert not has_orphan_tool(saved), "끼어들기 주입으로 tool 짝이 깨짐"

    async def test_no_injection_no_phantom_message(self, client_inj):
        """주입이 없으면 [사용자 끼어들기] 메시지도 INJECTED 이벤트도 없다."""
        create = await client_inj.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        _ScriptedStream.reset([("tool", "read_file", '{"path":"a.txt"}'), ("text", "끝")])
        events = await _stream_injecting(
            client_inj,
            {"message": "작업", "thread_id": tid, "task_type": "general"},
            [],
        )
        saved = _saved(tid)
        assert not any(
            isinstance(m.get("content"), str) and "[사용자 끼어들기]" in m["content"]
            for m in saved
        )
        assert ev.INJECTED not in [e.get("type") for e in events]
