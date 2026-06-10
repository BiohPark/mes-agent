"""장기기억 관리 엔드포인트 + 스레드 close 일괄추출 통합 테스트."""

import pytest
from agent.memory import MemoryStore
from agent.obsidian_session import get_session_manager


class TestMemoryEndpoints:
    """POST/DELETE /memory — 기억 관리 UI 백엔드."""

    async def test_add_and_list(self, client, vault):
        r = await client.post("/memory", json={"text": "사용자는 다크 테마를 선호한다", "category": "preference"})
        assert r.json()["saved"] is True
        lst = await client.get("/memory")
        texts = [m["text"] for m in lst.json()["memories"]]
        assert any("다크 테마" in t for t in texts)

    async def test_add_dedup_returns_saved_false(self, client, vault):
        await client.post("/memory", json={"text": "회사 도메인은 사내 전용", "category": "fact"})
        r2 = await client.post("/memory", json={"text": "회사 도메인은 사내 전용", "category": "fact"})
        assert r2.json()["saved"] is False

    async def test_delete_by_id(self, client, vault):
        r = await client.post("/memory", json={"text": "지울 기억"})
        mem_id = r.json()["memory"]["id"]
        d = await client.delete(f"/memory/{mem_id}")
        assert d.json()["ok"] is True
        lst = await client.get("/memory")
        assert all(m["id"] != mem_id for m in lst.json()["memories"])

    async def test_delete_unknown_id_is_false(self, client, vault):
        d = await client.delete("/memory/nonexistent-xyz")
        assert d.json()["ok"] is False


class TestCloseExtraction:
    """close 모드(기본): 스레드 종료 시 1회 일괄 추출, 매 턴 추출 안 함."""

    async def _seed(self, client, msgs):
        create = await client.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        get_session_manager().save_thread_messages("general", tid, msgs)
        return tid

    async def test_batch_extract_on_close(self, client, vault, monkeypatch):
        monkeypatch.setattr("agent.server._extract_memories",
                            lambda history: [{"text": "스레드 종료시 추출된 사실", "category": "fact"}])
        tid = await self._seed(client, [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "작업 내용 정리"},
            {"role": "assistant", "content": "완료했습니다"},
        ])
        await client.post(f"/threads/general/{tid}/close")
        texts = [m.text for m in MemoryStore(vault).all()]
        assert any("스레드 종료시 추출" in t for t in texts)

    async def test_no_turn_extraction_for_thread_in_close_mode(self, client, vault, monkeypatch):
        """close 모드(기본)에서 스레드 대화는 매 턴 추출하지 않는다(비용 최적화)."""
        calls = {"n": 0}
        monkeypatch.setattr("agent.server._extract_memories",
                            lambda history: calls.__setitem__("n", calls["n"] + 1) or [])
        create = await client.post("/threads/general", json={})
        tid = create.json()["thread_id"]
        async with client.stream("POST", "/chat", json={
            "message": "한국어로 길게 작업을 지시한다", "thread_id": tid, "task_type": "general",
        }) as resp:
            await resp.aread()
        assert calls["n"] == 0, "close 모드인데 스레드 턴마다 추출이 호출됨"

    async def test_close_extracts_only_in_close_mode(self, client, vault, monkeypatch):
        """off 모드면 close에서도 추출하지 않는다."""
        monkeypatch.setattr("agent.server.MEMORY_EXTRACT_MODE", "off")
        monkeypatch.setattr("agent.server._extract_memories",
                            lambda history: [{"text": "추출되면 안 됨", "category": "fact"}])
        tid = await self._seed(client, [{"role": "user", "content": "x"}])
        await client.post(f"/threads/general/{tid}/close")
        assert MemoryStore(vault).all() == []
