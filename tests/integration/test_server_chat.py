"""채팅 SSE 스트림 통합 테스트.

LLM 클라이언트는 conftest의 FakeLLMClient로 교체되어 실제 API를 호출하지 않는다.
SSE 이벤트 타입의 순서와 존재 여부를 검증한다.
"""

import json
import pytest
from agent.core import events as ev


# ── 툴 실패 시나리오용 LLM 목 ─────────────────────────────────────

class _Fn:
    def __init__(self, name="", arguments=""):
        self.name = name
        self.arguments = arguments


class _TC:
    def __init__(self, index=0, id="tc1", name="run_command", arguments='{"command":"x"}'):
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


class _TwoPhaseStream:
    """LLM 호출 1회차: tool_call 반환 / 2회차 이후: 텍스트 반환."""
    _call_count = 0

    @classmethod
    def reset(cls):
        cls._call_count = 0

    def __iter__(self):
        type(self)._call_count += 1
        if type(self)._call_count == 1:
            yield _Chunk(tool_calls=[_TC()])
            yield _Chunk(finish_reason="tool_calls")
        else:
            yield _Chunk(content="오류 확인됨")
            yield _Chunk(finish_reason="stop")


class _TwoPhaseLLM:
    class _Comp:
        def create(self, **kw):
            return _TwoPhaseStream()

    class _Chat:
        def __init__(self):
            self.completions = _TwoPhaseLLM._Comp()

    def __init__(self):
        self.chat = _TwoPhaseLLM._Chat()


@pytest.fixture
async def client_fail(vault, monkeypatch):
    """LLM이 tool_call을 반환하고, run_tool이 항상 예외를 던지는 테스트 클라이언트."""
    _TwoPhaseStream.reset()
    monkeypatch.setattr("agent.server.get_client", lambda: _TwoPhaseLLM())
    monkeypatch.setattr("agent.server.get_model", lambda: "gpt-test")

    def _always_fail(name, args):
        raise RuntimeError("의도된 테스트 실패")

    monkeypatch.setattr("agent.server.run_tool", _always_fail)

    from httpx import AsyncClient, ASGITransport
    from agent.server import app
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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


class TestToolFailureAutoError:
    """Phase 2: 툴 실패 시 running 단계 자동 error 전환 검증."""

    async def _setup_running_workflow(self, client_fail, vault, step_id="s1", step_title="실행 단계"):
        """스레드 생성 + running 단계 워크플로우 설정 헬퍼."""
        from agent.workflow import storage as wf_storage
        from agent.workflow.model import Workflow, WorkflowStep

        create = await client_fail.post("/threads/general", json={})
        tid = create.json()["thread_id"]

        wf = Workflow(
            thread_id=tid, task_type="general", title="테스트",
            steps=[WorkflowStep(id=step_id, title=step_title, status="running")],
        )
        wf_storage.save_workflow(wf)
        return tid

    async def test_workflow_update_event_emitted_on_failure(self, client_fail, vault):
        """툴 실패 시 WORKFLOW_UPDATE SSE 이벤트가 발생해야 한다."""
        tid = await self._setup_running_workflow(client_fail, vault)

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            text = await resp.aread()

        events = _parse_sse(text.decode())
        wf_updates = [e for e in events if e.get("type") == ev.WORKFLOW_UPDATE]
        assert wf_updates, "WORKFLOW_UPDATE 이벤트 없음"

    async def test_running_step_becomes_error_in_event(self, client_fail, vault):
        """WORKFLOW_UPDATE 이벤트의 단계 status가 error여야 한다."""
        tid = await self._setup_running_workflow(client_fail, vault, step_id="s_err")

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            text = await resp.aread()

        events = _parse_sse(text.decode())
        error_steps = [
            step
            for e in events if e.get("type") == ev.WORKFLOW_UPDATE
            for step in e.get("workflow", {}).get("steps", [])
            if step.get("status") == "error"
        ]
        assert error_steps, "error 상태 단계가 이벤트에 없음"
        assert error_steps[0]["id"] == "s_err"

    async def test_error_step_persisted_to_file(self, client_fail, vault):
        """툴 실패 후 파일에도 error 상태가 저장되어야 한다."""
        from agent.workflow import storage as wf_storage

        tid = await self._setup_running_workflow(client_fail, vault, step_id="s_file")

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()

        saved = wf_storage.load_workflow("general", tid)
        assert saved.steps[0].status == "error"

    async def test_error_step_notes_contain_error_message(self, client_fail, vault):
        """error 단계의 notes에 오류 내용이 포함되어야 한다."""
        from agent.workflow import storage as wf_storage

        tid = await self._setup_running_workflow(client_fail, vault, step_id="s_note")

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()

        saved = wf_storage.load_workflow("general", tid)
        assert saved.steps[0].notes, "notes가 비어있음"

    async def test_no_error_transition_without_running_step(self, client_fail, vault):
        """pending 상태 단계만 있을 때 자동 error 전환이 없어야 한다."""
        from agent.workflow import storage as wf_storage
        from agent.workflow.model import Workflow, WorkflowStep

        create = await client_fail.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        wf = Workflow(
            thread_id=tid, task_type="general", title="테스트",
            steps=[WorkflowStep(id="p1", title="대기 단계", status="pending")],
        )
        wf_storage.save_workflow(wf)

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()

        saved = wf_storage.load_workflow("general", tid)
        assert saved.steps[0].status == "pending", "pending 단계가 자동으로 error로 바뀌면 안 됨"


class TestRunStateSync:
    """Phase 1-C: 툴 실패 → RunState 동기화 + Definition 불변성 검증."""

    async def _setup(self, client_fail, vault, step_id="rs1"):
        """그래프 포맷으로 Definition + running 상태의 RunState를 저장한다."""
        from agent.workflow import storage as wf_storage
        from agent.workflow.model import WorkflowDefinition, WorkflowNode, WorkflowRunState

        create = await client_fail.post("/threads/general", json={})
        tid = create.json()["thread_id"]

        # Definition 파일 (그래프 포맷, 불변)
        defn = WorkflowDefinition(
            id=tid, task_type="general", title="RunState 테스트",
            nodes=[WorkflowNode(id=step_id, title="실행 단계")],
            connections=[],
        )
        wf_storage.save_definition(defn)

        # RunState 파일 (가변, running 상태)
        rs = WorkflowRunState(definition_id=tid)
        rs.set_node_status(step_id, "running")
        wf_storage.save_run_state("general", tid, rs)
        return tid

    async def test_run_state_updated_on_tool_failure(self, client_fail, vault):
        """툴 실패 후 RunState 파일에 error 상태가 저장되어야 한다."""
        from agent.workflow import storage as wf_storage

        tid = await self._setup(client_fail, vault, step_id="sync1")

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()

        rs = wf_storage.load_run_state("general", tid)
        assert rs is not None, "RunState 파일이 생성되지 않음"
        assert rs.node_states.get("sync1") is not None
        assert rs.node_states["sync1"].status == "error"

    async def test_definition_unchanged_after_tool_failure(self, client_fail, vault):
        """툴 실패 후에도 WorkflowDefinition 파일이 변경되지 않아야 한다 (C3 불변성)."""
        from agent.workflow import storage as wf_storage

        tid = await self._setup(client_fail, vault, step_id="sync2")
        defn_before = wf_storage.load_definition("general", tid)
        original_node_count = len(defn_before.nodes)

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()

        defn_after = wf_storage.load_definition("general", tid)
        assert len(defn_after.nodes) == original_node_count
        assert defn_after.nodes[0].id == "sync2"
        # Definition의 노드 구조(title, type)가 변경되지 않아야 함
        assert defn_after.nodes[0].title == "실행 단계"

    async def test_run_state_reflects_error_notes(self, client_fail, vault):
        """RunState의 error notes에 오류 내용이 포함되어야 한다."""
        from agent.workflow import storage as wf_storage

        tid = await self._setup(client_fail, vault, step_id="sync3")

        async with client_fail.stream("POST", "/chat", json={
            "message": "작업", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()

        rs = wf_storage.load_run_state("general", tid)
        assert rs is not None
        assert rs.node_states["sync3"].notes, "RunState notes가 비어있음"
