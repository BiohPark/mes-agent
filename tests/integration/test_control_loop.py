"""백로그 O — Vault 명령함 폴러 통합 테스트.

_process_inbox_once()가 inbox 명령을 픽업→마킹→실행→status 기록하는지,
auto_confirm='deny'로 위험작업을 무인 거부하는지 검증한다.
"""

import asyncio
import pytest


# ── 스크립트 LLM (자기완결) ───────────────────────────────────────

class _Fn:
    def __init__(self, name="", arguments=""):
        self.name, self.arguments = name, arguments


class _TC:
    def __init__(self, index=0, id="tc1", name="read_file", arguments='{"path":"a.txt"}'):
        self.index, self.id = index, id
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
        self.choices = [_Choice(content, tool_calls, finish_reason)]


class _ScriptedStream:
    script: list = []
    _i = 0

    @classmethod
    def reset(cls, script):
        cls.script, cls._i = list(script), 0

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
            tools = kw.get("tools")
            if tools is not None and len(tools) > 128:
                raise ValueError("tools too long")
            return _ScriptedStream()

    class _Chat:
        def __init__(self):
            self.completions = _ScriptedLLM._Comp()

    def __init__(self):
        self.chat = _ScriptedLLM._Chat()


@pytest.fixture
def control_env(vault, monkeypatch):
    """스크립트 LLM + run_tool 기록기 + 격리 큐. 폴러 직접 호출용."""
    import agent.server as srv
    srv._session_allowlists.clear()
    srv._pending_messages.clear()
    monkeypatch.setattr("agent.server.get_client", lambda: _ScriptedLLM())
    monkeypatch.setattr("agent.server.get_model", lambda: "gpt-test")

    calls = []

    def _rec(name, args):
        calls.append((name, args))
        return '{"ok": true}'

    monkeypatch.setattr("agent.server.run_tool", _rec)
    return srv, calls


def _sm():
    from agent.obsidian_session import get_session_manager
    return get_session_manager()


class TestProcessInboxOnce:
    async def test_picks_up_marks_and_records(self, control_env):
        srv, calls = control_env
        _ScriptedStream.reset([("tool", "read_file", '{"path":"a.txt"}'), ("text", "결과입니다")])
        _sm()._write(srv._CONTROL_INBOX, "# 명령함\n- [ ] 파일 읽어줘\n")

        await srv._process_inbox_once()

        inbox = _sm()._read(srv._CONTROL_INBOX)
        assert "- [x] 파일 읽어줘" in inbox, "명령이 처리 표시(- [x])로 안 바뀜"
        status = _sm()._read(srv._CONTROL_STATUS)
        assert "파일 읽어줘" in status
        assert "결과입니다" in status
        assert calls and calls[0][0] == "read_file"

    async def test_already_checked_not_reprocessed(self, control_env):
        srv, calls = control_env
        _ScriptedStream.reset([("text", "무시")])
        _sm()._write(srv._CONTROL_INBOX, "# 명령함\n- [x] 이미 끝남\n")

        await srv._process_inbox_once()

        assert calls == [], "이미 체크된 명령이 재실행됨"
        assert _sm()._read(srv._CONTROL_STATUS) == ""

    async def test_active_request_injects_instead(self, control_env):
        srv, calls = control_env
        srv._pending_messages["rid-live"] = []
        try:
            _sm()._write(srv._CONTROL_INBOX, "# 명령함\n- [ ] 합류 명령\n")
            await srv._process_inbox_once()
            assert "합류 명령" in srv._pending_messages["rid-live"], "활성 요청 큐에 주입 안 됨"
            assert calls == [], "주입 경로인데 헤드리스 실행됨"
            status = _sm()._read(srv._CONTROL_STATUS)
            assert "주입됨" in status
        finally:
            srv._pending_messages.pop("rid-live", None)

    async def test_no_pending_no_status(self, control_env):
        srv, calls = control_env
        _sm()._write(srv._CONTROL_INBOX, "# 명령함\n그냥 메모\n")
        await srv._process_inbox_once()
        assert calls == []
        assert _sm()._read(srv._CONTROL_STATUS) == ""


class TestRemoteAutoDeny:
    async def test_risky_tool_denied_without_hang(self, control_env):
        """위험 명령은 auto_confirm='deny'로 즉시 거부 — run_tool 미호출, 행 없음."""
        srv, calls = control_env
        _ScriptedStream.reset([
            ("tool", "run_command", '{"command":"Remove-Item C:/x -Recurse"}'),
            ("text", "거부되어 중단했습니다"),
        ])
        result = await asyncio.wait_for(srv._run_remote_command("폴더 삭제해줘"), timeout=5)
        assert calls == [], "위험 도구가 무인 환경에서 실행됨"
        assert "중단" in result

    async def test_safe_tool_runs(self, control_env):
        """읽기형은 auto_confirm와 무관하게 실행된다."""
        srv, calls = control_env
        _ScriptedStream.reset([("tool", "read_file", '{"path":"a.txt"}'), ("text", "읽었음")])
        result = await asyncio.wait_for(srv._run_remote_command("읽어줘"), timeout=5)
        assert calls and calls[0][0] == "read_file"
        assert "읽었음" in result


class TestStartupGate:
    async def test_disabled_does_not_schedule_poller(self, vault, monkeypatch):
        import agent.server as srv
        monkeypatch.setenv("CONTROL_ENABLED", "false")
        created = []
        monkeypatch.setattr("agent.server.asyncio.create_task", lambda c: created.append(c))
        await srv.startup_control()
        assert created == []
