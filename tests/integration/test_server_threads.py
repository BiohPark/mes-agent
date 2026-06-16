"""스레드 CRUD 통합 테스트: 생성·조회·보관·복원·영구삭제."""

import pytest


TASK = "general"


class TestCreateThread:
    async def test_returns_thread_id(self, client):
        resp = await client.post(f"/threads/{TASK}", json={"title": "테스트 스레드"})
        assert resp.status_code == 200
        data = resp.json()
        assert "thread_id" in data
        assert data["thread_id"]

    async def test_empty_title_is_accepted(self, client):
        resp = await client.post(f"/threads/{TASK}", json={})
        assert resp.status_code == 200
        assert "thread_id" in resp.json()


class TestListThreads:
    async def test_empty_initially(self, client):
        resp = await client.get(f"/threads/{TASK}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_created_thread_appears_in_list(self, client):
        create_resp = await client.post(f"/threads/{TASK}", json={"title": "목록 테스트"})
        thread_id = create_resp.json()["thread_id"]

        list_resp = await client.get(f"/threads/{TASK}")
        ids = [t["thread_id"] for t in list_resp.json()]
        assert thread_id in ids

    async def test_list_all_threads(self, client):
        await client.post(f"/threads/{TASK}", json={})
        await client.post("/threads/syncade", json={})
        resp = await client.get("/threads")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))


class TestThreadMessages:
    async def test_new_thread_messages_empty(self, client):
        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]
        resp = await client.get(f"/threads/{TASK}/{tid}/messages")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_legacy_control_messages_hidden_from_display(self, client):
        from agent.obsidian_session import get_session_manager

        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]
        get_session_manager().save_thread_messages(TASK, tid, [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "[시스템] 계획이 승인되었다."},
            {"role": "user", "content": "[사용자 끼어들기] 내부 큐"},
            {"role": "user", "content": "실제 질문"},
            {"role": "assistant", "content": "실제 답"},
        ])

        resp = await client.get(f"/threads/{TASK}/{tid}/messages")
        assert resp.status_code == 200
        assert resp.json() == [
            {"role": "user", "content": "실제 질문"},
            {"role": "assistant", "content": "실제 답"},
        ]


class TestArchiveAndRestore:
    async def test_archive_thread(self, client):
        create = await client.post(f"/threads/{TASK}", json={"title": "보관 대상"})
        tid = create.json()["thread_id"]

        resp = await client.delete(f"/threads/{TASK}/{tid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    async def test_archived_thread_not_in_active_list(self, client):
        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]
        await client.delete(f"/threads/{TASK}/{tid}")

        active = [t["thread_id"] for t in (await client.get(f"/threads/{TASK}")).json()]
        assert tid not in active

    async def test_restore_thread(self, client):
        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]
        await client.delete(f"/threads/{TASK}/{tid}")

        resp = await client.post(f"/threads/{TASK}/{tid}/restore")
        assert resp.status_code == 200

    async def test_close_thread(self, client):
        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]
        resp = await client.post(f"/threads/{TASK}/{tid}/close")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


class TestSearch:
    async def test_empty_query_returns_empty(self, client):
        resp = await client.get("/search?q=")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_search_matches_title(self, client):
        title = "분기매출보고서특이검색어"
        await client.post(f"/threads/{TASK}", json={"title": title})

        resp = await client.get(f"/search?q={title}")
        assert resp.status_code == 200
        hits = resp.json()
        assert any(h["title"] == title for h in hits)
        assert all({"task_type", "thread_id", "status"} <= set(h) for h in hits)

    async def test_search_no_match(self, client):
        await client.post(f"/threads/{TASK}", json={"title": "평범한 제목"})
        resp = await client.get("/search?q=존재하지않는검색어zzz")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPermanentDelete:
    async def test_permanent_delete(self, client):
        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]

        resp = await client.delete(f"/threads/{TASK}/{tid}/permanent")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    async def test_deleted_thread_not_in_list(self, client):
        create = await client.post(f"/threads/{TASK}", json={})
        tid = create.json()["thread_id"]
        await client.delete(f"/threads/{TASK}/{tid}/permanent")

        active = [t["thread_id"] for t in (await client.get(f"/threads/{TASK}")).json()]
        assert tid not in active
