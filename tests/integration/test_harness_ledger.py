"""하네스 라운드 RunLedger 영속화 통합 테스트 (Phase 1 — G3 실측 계측).

_harness_generate가 매 Reviewer 판결을 RunLedger에 harness_round 엔트리로
기록하고, summarize_harness_runs가 이를 집계하는지 검증한다. 네트워크 없음:
generate()와 _reviewer_call을 가짜로 대체한다.
"""

import pytest

import agent.server as server
from agent.core import events as ev
from agent.harness.metrics import summarize_harness_runs
from agent.harness.orchestrator import ReviewVerdict
from agent.workflow import storage as wf_storage


def _fake_generate(*verdict_unused):
    """generate() 대체 — 짧은 TEXT 1개 + DONE을 yield하는 async generator."""
    async def _gen(message, thread_id="", task_type="", agent_mode="auto", auto_confirm=""):
        yield server.sse({"type": ev.TEXT, "content": "실행함"})
        yield server.sse({"type": ev.DONE})
    return _gen


async def _drain(agen):
    out = []
    async for raw in agen:
        out.append(raw)
    return out


@pytest.fixture
def thread(vault):
    from agent.obsidian_session import get_session_manager
    mgr = get_session_manager()
    tid = mgr.new_thread("syncade", "테스트 배포")
    return tid


async def test_passed_round_recorded(thread, monkeypatch):
    """첫 라운드 통과 시 harness_round 엔트리 1개가 ledger에 기록된다."""
    monkeypatch.setattr(server, "generate", _fake_generate())
    monkeypatch.setattr(server, "_HARNESS_MAX_ROUNDS", 2)

    async def _ok(history, verify_prompt=""):
        return ReviewVerdict(passed=True)
    monkeypatch.setattr(server, "_reviewer_call", _ok)

    events = await _drain(server._harness_generate("배포해", thread, "syncade", "auto"))
    assert any('"type": "done"' in e or '"done"' in e for e in events)

    entries = wf_storage.load_ledger("syncade", thread)
    summary = summarize_harness_runs(entries)
    assert summary["total_reviews"] == 1
    assert summary["final_passed"] is True
    assert summary["self_corrected"] is False


async def test_fail_then_pass_records_self_correction(thread, monkeypatch):
    """라운드1 실패→라운드2 통과면 self_corrected=True로 집계된다."""
    monkeypatch.setattr(server, "generate", _fake_generate())
    monkeypatch.setattr(server, "_HARNESS_MAX_ROUNDS", 2)

    calls = {"n": 0}

    async def _fail_then_pass(history, verify_prompt=""):
        calls["n"] += 1
        if calls["n"] == 1:
            return ReviewVerdict(passed=False, feedback="서비스 미기동")
        return ReviewVerdict(passed=True)
    monkeypatch.setattr(server, "_reviewer_call", _fail_then_pass)

    await _drain(server._harness_generate("배포해", thread, "syncade", "auto"))

    summary = summarize_harness_runs(wf_storage.load_ledger("syncade", thread))
    assert summary["total_reviews"] == 2
    assert summary["retries"] == 1
    assert summary["final_passed"] is True
    assert summary["self_corrected"] is True


async def test_metrics_endpoint_returns_summary(client, thread, monkeypatch):
    """GET /harness/metrics가 집계 요약을 반환한다."""
    from datetime import datetime, timezone
    from agent.workflow.model import LedgerEntry
    import json
    # ledger에 라운드 1개 직접 적재
    wf_storage.append_ledger("syncade", thread, LedgerEntry(
        ts=datetime.now(timezone.utc).isoformat(), event="harness_round",
        detail=json.dumps({"round": 1, "passed": True, "feedback_len": 0, "history_tokens": 500}),
        phase="verifying"))

    resp = await client.get(f"/threads/syncade/{thread}/harness/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 1
    assert data["final_passed"] is True
