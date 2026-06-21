"""_run_tool_watched가 effective_cap()을 사용해 디스패치 캡을 계산하는지 검증 (V-2 Phase 2 보완)."""
import asyncio

import agent.core.timeouts as timeouts_module
import agent.server as server


async def test_run_tool_watched_uses_effective_cap(monkeypatch):
    seen = {}

    def fake_effective_cap(name, arguments):
        seen["name"] = name
        seen["arguments"] = arguments
        return 1.0  # 매우 작은 캡 → 테스트 빠르게 종료

    monkeypatch.setattr(timeouts_module, "effective_cap", fake_effective_cap)
    monkeypatch.setattr(server, "run_tool", lambda name, arguments: "ok")

    loop = asyncio.get_running_loop()
    results = []
    # generate() 루프가 실제로 넘기는 형태 — LLM 스트리밍 누적 JSON 문자열(파싱 전)
    raw_arguments = '{"timeout": 120}'
    async for kind, payload in server._run_tool_watched(loop, "run_command", raw_arguments, "테스트"):
        results.append((kind, payload))

    assert seen["name"] == "run_command"
    assert seen["arguments"] == raw_arguments
    assert results[-1][0] == "result"
    assert results[-1][1] == "ok"
