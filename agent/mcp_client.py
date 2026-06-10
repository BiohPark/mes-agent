"""MCP(Model Context Protocol) 클라이언트 — 외부 MCP 서버 도구를 에이전트 도구로 노출 (백로그 J).

- 설정 `mcp_servers.json`(레포 루트, Claude Desktop과 동일 shape)을 읽어 stdio 서버에 연결.
- 각 MCP 도구를 MANIFEST로 변환해 `tools.register_tool`로 런타임 등록.
- run_tool이 동기라, 비동기 MCP 호출은 전용 asyncio 루프 스레드 + run_coroutine_threadsafe로 sync 브릿지.
- `mcp` SDK는 연결 시점에만 import(지연) → 미설치·무설정이어도 앱이 정상 동작.

폐쇄망: MCP 서버는 로컬 stdio 프로세스 권장. 실제 Oracle 접속정보는 회사 환경에서 mcp_servers.json에 기입.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from pathlib import Path

from agent.tools import register_tool

_log = logging.getLogger("mcp")


# ── 순수 헬퍼 (테스트 대상) ───────────────────────────────────

def _attr(obj, key, default=None):
    """dict/객체 모두에서 속성을 읽는다(MCP SDK는 pydantic 객체를 반환)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _ensure_object_schema(schema) -> dict:
    """OpenAI function 파라미터는 type:object + properties가 필요 — 보정한다."""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    out = dict(schema)
    out.setdefault("type", "object")
    out.setdefault("properties", {})
    return out


def mcp_tool_to_manifest(server: str, tool, call_fn) -> dict:
    """MCP 도구 descriptor를 에이전트 MANIFEST 엔트리로 변환한다(순수).

    tool: name/description/inputSchema/annotations(readOnlyHint)를 가진 dict 또는 객체.
    call_fn(server, tool_name, args) -> str: 실제 호출 sync 브릿지.
    """
    name = _attr(tool, "name")
    desc = _attr(tool, "description") or ""
    schema = _ensure_object_schema(_attr(tool, "inputSchema") or _attr(tool, "input_schema"))
    ann = _attr(tool, "annotations") or {}
    read_only = bool(_attr(ann, "readOnlyHint", False))
    full = f"mcp_{server}_{name}"
    return {
        "name": full,
        "label": f"MCP:{server}/{name}",
        "schema": {
            "type": "function",
            "function": {
                "name": full,
                "description": f"[MCP {server}] {desc}".strip(),
                "parameters": schema,
            },
        },
        "handler": (lambda a, _s=server, _n=name: call_fn(_s, _n, a)),
        "_module": "mcp",
        # readOnlyHint면 읽기전용 → safe, 아니면 보수적으로 mutate(확인 게이트)
        "_risk": "safe" if read_only else "mutate",
    }


def _serialize(result) -> str:
    """MCP call_tool 결과(content 블록 리스트)를 문자열로 직렬화한다."""
    try:
        content = _attr(result, "content", None)
        if content is None:
            return json.dumps(result, ensure_ascii=False, default=str)
        parts = []
        for block in content:
            text = _attr(block, "text", None)
            parts.append(text if text is not None else json.dumps(block, ensure_ascii=False, default=str))
        return "\n".join(p for p in parts if p) or ""
    except Exception as e:
        return f"[MCP 결과 직렬화 실패: {e}]"


def _load_config() -> dict:
    """MCP_CONFIG(기본 레포 루트 mcp_servers.json)에서 servers 맵을 읽는다. 없으면 {}."""
    raw = os.environ.get("MCP_CONFIG", "mcp_servers.json")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / raw
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        servers = data.get("servers", {})
        return servers if isinstance(servers, dict) else {}
    except Exception as e:
        _log.warning("mcp_servers.json 파싱 실패: %s", e)
        return {}


# ── 매니저 (전용 asyncio 루프 스레드) ─────────────────────────

class MCPManager:
    def __init__(self):
        self._loop = None
        self._thread = None
        self._sessions: dict = {}
        self._stacks: dict = {}

    def _ensure_loop(self):
        if self._loop and self._thread and self._thread.is_alive():
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="mcp-loop", daemon=True)
        self._thread.start()

    def _run(self, coro, timeout=None):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def connect_all(self) -> int:
        """설정된 모든 MCP 서버에 연결하고 도구를 등록한다. 등록 도구 수 반환.

        서버가 없으면 루프 스레드를 만들지 않는다(테스트 누수 방지).
        """
        servers = _load_config()
        if not servers:
            return 0
        self._ensure_loop()
        timeout = float(os.environ.get("MCP_CONNECT_TIMEOUT", "30"))
        count = 0
        for name, cfg in servers.items():
            try:
                tools = self._run(self._async_connect(name, cfg), timeout=timeout)
                for t in tools:
                    register_tool(mcp_tool_to_manifest(name, t, self.call))
                    count += 1
                _log.info("MCP 서버 '%s' 연결: 도구 %d개", name, len(tools))
            except Exception as e:
                _log.warning("MCP 서버 '%s' 연결 실패: %s", name, e)
        return count

    async def _async_connect(self, name: str, cfg: dict):
        from contextlib import AsyncExitStack
        from mcp import ClientSession, StdioServerParameters  # 지연 import
        from mcp.client.stdio import stdio_client

        stack = AsyncExitStack()
        env = {**os.environ, **(cfg.get("env") or {})}
        params = StdioServerParameters(command=cfg["command"], args=cfg.get("args", []), env=env)
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[name] = session
        self._stacks[name] = stack
        resp = await session.list_tools()
        return list(_attr(resp, "tools", []) or [])

    def call(self, server: str, tool: str, args: dict) -> str:
        """동기 핸들러 → 전용 루프에서 비동기 call_tool 실행(sync 브릿지)."""
        try:
            timeout = float(os.environ.get("MCP_CALL_TIMEOUT", "60"))
            result = self._run(self._async_call(server, tool, args), timeout=timeout)
            return _serialize(result)
        except Exception as e:
            return json.dumps({"error": f"MCP 호출 실패({server}/{tool}): {e}"}, ensure_ascii=False)

    async def _async_call(self, server: str, tool: str, args: dict):
        session = self._sessions.get(server)
        if session is None:
            raise RuntimeError(f"MCP 세션 없음: {server}")
        return await session.call_tool(tool, args or {})

    def shutdown(self):
        for stack in list(self._stacks.values()):
            try:
                self._run(stack.aclose(), timeout=5)
            except Exception:
                pass
        self._stacks.clear()
        self._sessions.clear()
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass


_manager: MCPManager | None = None


def get_manager() -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager
