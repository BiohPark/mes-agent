"""RunLedger 감사 추적 단위 테스트."""

import json
import pytest
from pathlib import Path
from agent.workflow.model import LedgerEntry, RunLedgerEvent
from agent.workflow.storage import (
    append_ledger,
    append_run_ledger,
    load_ledger,
    load_run_ledger,
    summarize_for_ledger,
    _ledger_path,
    _run_ledger_path,
)


# ── 픽스처 ──────────────────────────────────────────────────

@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


# ── LedgerEntry 모델 ─────────────────────────────────────────

class TestLedgerEntry:
    def test_to_dict_round_trip(self):
        entry = LedgerEntry(ts="2026-06-14T10:00:00", event="done", detail="완료", phase="done")
        d = entry.to_dict()
        assert d["event"] == "done"
        assert d["phase"] == "done"
        assert d["detail"] == "완료"
        assert "ts" in d

    def test_from_dict(self):
        d = {"ts": "2026-06-14T10:00:00", "event": "error", "detail": "실패", "phase": "error"}
        entry = LedgerEntry.from_dict(d)
        assert entry.event == "error"
        assert entry.phase == "error"

    def test_from_dict_defaults(self):
        entry = LedgerEntry.from_dict({"ts": "t", "event": "done"})
        assert entry.detail == ""
        assert entry.phase == ""


# ── append_ledger / load_ledger ──────────────────────────────

class TestLedger:
    def test_append_creates_file(self, vault):
        entry = LedgerEntry(ts="2026-06-14T10:00:00", event="done")
        append_ledger("general", "t1", entry)
        path = _ledger_path("general", "t1")
        assert path and path.exists()

    def test_append_multiple_entries(self, vault):
        e1 = LedgerEntry(ts="2026-06-14T10:00:00", event="start", phase="planning")
        e2 = LedgerEntry(ts="2026-06-14T10:01:00", event="done", phase="done")
        append_ledger("general", "t2", e1)
        append_ledger("general", "t2", e2)
        entries = load_ledger("general", "t2")
        assert len(entries) == 2
        assert entries[0]["event"] == "start"
        assert entries[1]["event"] == "done"

    def test_load_returns_empty_when_no_file(self, vault):
        entries = load_ledger("general", "nonexistent")
        assert entries == []

    def test_no_vault_is_noop(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        entry = LedgerEntry(ts="t", event="done")
        append_ledger("general", "x", entry)  # 오류 없이 종료

    def test_load_no_vault_returns_empty(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        assert load_ledger("general", "x") == []

    def test_entries_are_valid_jsonl(self, vault):
        """각 줄이 독립적인 유효한 JSON이어야 한다."""
        append_ledger("general", "t3", LedgerEntry(ts="t", event="a"))
        append_ledger("general", "t3", LedgerEntry(ts="t", event="b"))
        path = _ledger_path("general", "t3")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "event" in parsed

    def test_load_ignores_corrupted_lines(self, vault):
        """손상된 줄은 건너뛰고 나머지를 반환한다."""
        path = _ledger_path("general", "t4")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"ts":"t","event":"ok"}\nNOT_JSON\n{"ts":"t","event":"ok2"}\n', encoding="utf-8")
        entries = load_ledger("general", "t4")
        assert len(entries) == 2
        assert entries[0]["event"] == "ok"
        assert entries[1]["event"] == "ok2"


class TestRunLedgerEvent:
    def test_structured_event_round_trip_defaults(self):
        event = RunLedgerEvent(
            request_id="req1",
            thread_id="thread1",
            task_type="general",
            event_type="run_started",
            phase="planning",
            role="planner",
            summary="started",
        )

        data = event.to_dict()
        restored = RunLedgerEvent.from_dict(data)

        assert data["event_id"]
        assert data["timestamp"]
        assert restored.event_type == "run_started"
        assert restored.details == {}
        assert restored.provenance == {}

    def test_append_structured_events_request_path(self, vault):
        first = RunLedgerEvent(
            request_id="req2", thread_id="thread2", task_type="general",
            event_type="run_started", phase="planning", role="planner",
        )
        second = RunLedgerEvent(
            request_id="req2", thread_id="thread2", task_type="general",
            event_type="run_finished", phase="done", role="orchestrator",
        )

        append_run_ledger(first)
        append_run_ledger(second)

        path = _run_ledger_path("general", "thread2", "req2")
        assert path and path.exists()
        entries = load_run_ledger("general", "thread2", "req2")
        assert [e["event_type"] for e in entries] == ["run_started", "run_finished"]

    def test_load_thread_structured_events_skips_corrupt_lines(self, vault):
        path = _run_ledger_path("general", "thread3", "req3")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"event_type":"run_started","request_id":"req3"}\nBAD\n'
            '{"event_type":"run_finished","request_id":"req3"}\n',
            encoding="utf-8",
        )

        entries = load_run_ledger("general", "thread3")

        assert [e["event_type"] for e in entries] == ["run_started", "run_finished"]

    def test_structured_writer_no_vault_is_noop(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        append_run_ledger(RunLedgerEvent(
            request_id="req4", thread_id="thread4", task_type="general",
            event_type="run_started", phase="planning", role="planner",
        ))

    def test_summarize_for_ledger_redacts_sensitive_and_large_payloads(self):
        text = summarize_for_ledger({
            "token": "secret-token",
            "password": "secret-password",
            "image": "data:image/png;base64," + ("A" * 300),
            "nested": {"api_key": "secret-key"},
        }, limit=160)

        assert "secret-token" not in text
        assert "secret-password" not in text
        assert "secret-key" not in text
        assert "base64" not in text
        assert len(text) <= 160
