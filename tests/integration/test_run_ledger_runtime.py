"""RunLedger runtime instrumentation regression tests."""

import pytest

from agent.core import events as ev
from tests.integration.test_server_chat import _ScriptedStream, _stream_answering, client_gate


TASK = "general"


async def _new_thread(client):
    resp = await client.post(f"/threads/{TASK}", json={"title": "run ledger"})
    assert resp.status_code == 200
    return resp.json()["thread_id"]


async def _ledger(client, thread_id):
    resp = await client.get(f"/threads/{TASK}/{thread_id}/ledger")
    assert resp.status_code == 200
    return resp.json()["entries"]


def _types(entries):
    return [e.get("event_type") or e.get("event") for e in entries]


class TestRunLedgerRuntime:
    async def test_chat_records_run_started_and_finished(self, client_gate):
        tid = await _new_thread(client_gate)
        _ScriptedStream.reset([("text", "done")])

        await _stream_answering(client_gate, {
            "message": "hello", "thread_id": tid, "task_type": TASK,
        }, [])
        entries = await _ledger(client_gate, tid)

        assert "run_started" in _types(entries)
        assert "run_finished" in _types(entries)
        finished = next(e for e in entries if e.get("event_type") == "run_finished")
        assert finished["phase"] == "done"
        assert finished["role"] == "orchestrator"

    async def test_tool_execution_records_tool_started_and_finished(self, client_gate):
        tid = await _new_thread(client_gate)
        _ScriptedStream.reset([
            ("tool", "read_file", '{"path":"a.txt"}'),
            ("text", "done"),
        ])

        await _stream_answering(client_gate, {
            "message": "read", "thread_id": tid, "task_type": TASK,
        }, [])
        entries = await _ledger(client_gate, tid)
        started = next(e for e in entries if e.get("event_type") == "tool_started")
        finished = next(e for e in entries if e.get("event_type") == "tool_finished")

        assert started["phase"] == "executing"
        assert started["role"] == "executor"
        assert started["details"]["tool"] == "read_file"
        assert finished["details"]["tool"] == "read_file"
        assert "ok" in finished["summary"]

    async def test_approval_records_requested_and_resolved_with_confirm_id(self, client_gate):
        tid = await _new_thread(client_gate)
        _ScriptedStream.reset([
            ("tool", "write_file", '{"path":"a.txt","content":"x"}'),
            ("text", "done"),
        ])

        events = await _stream_answering(client_gate, {
            "message": "write", "thread_id": tid, "task_type": TASK,
        }, ["예 (이번만)"])
        confirm = next(e for e in events if e.get("type") == ev.CONFIRM)
        entries = await _ledger(client_gate, tid)
        requested = next(e for e in entries if e.get("event_type") == "approval_requested")
        resolved = next(e for e in entries if e.get("event_type") == "approval_resolved")

        assert requested["details"]["confirm_id"] == confirm["confirm_id"]
        assert resolved["details"]["confirm_id"] == confirm["confirm_id"]
        assert resolved["details"]["choice"] == "예 (이번만)"

    async def test_endpoint_includes_legacy_ledger_entries(self, client_gate):
        from agent.workflow import storage as wf_storage
        from agent.workflow.model import LedgerEntry

        tid = await _new_thread(client_gate)
        wf_storage.append_ledger(TASK, tid, LedgerEntry(ts="t", event="legacy_done", phase="done"))
        _ScriptedStream.reset([("text", "done")])

        await _stream_answering(client_gate, {
            "message": "hello", "thread_id": tid, "task_type": TASK,
        }, [])
        entries = await _ledger(client_gate, tid)

        assert entries[0].get("event_type") == "run_started"
        assert any(e.get("event") == "legacy_done" for e in entries)
