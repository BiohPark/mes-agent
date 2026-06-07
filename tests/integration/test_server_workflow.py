"""워크플로우 API 통합 테스트: GET·POST·DELETE /threads/{type}/{id}/workflow."""

import pytest


TASK = "general"


@pytest.fixture
async def thread_id(client) -> str:
    """테스트용 스레드를 생성하고 thread_id를 반환한다."""
    resp = await client.post(f"/threads/{TASK}", json={"title": "워크플로우 테스트"})
    return resp.json()["thread_id"]


class TestGetWorkflow:
    async def test_returns_default_workflow(self, client, thread_id):
        resp = await client.get(f"/threads/{TASK}/{thread_id}/workflow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == thread_id
        assert data["task_type"] == TASK
        assert "title" in data
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) > 0

    async def test_default_steps_have_required_fields(self, client, thread_id):
        resp = await client.get(f"/threads/{TASK}/{thread_id}/workflow")
        for step in resp.json()["steps"]:
            assert "id" in step
            assert "title" in step
            assert "type" in step
            assert "status" in step

    async def test_default_step_ids_are_fixed(self, client, thread_id):
        """두 번 GET해도 step id가 달라지면 안 된다."""
        r1 = await client.get(f"/threads/{TASK}/{thread_id}/workflow")
        r2 = await client.get(f"/threads/{TASK}/{thread_id}/workflow")
        ids1 = [s["id"] for s in r1.json()["steps"]]
        ids2 = [s["id"] for s in r2.json()["steps"]]
        assert ids1 == ids2


class TestSaveWorkflow:
    async def test_save_and_get_roundtrip(self, client, thread_id):
        payload = {
            "title": "커스텀 워크플로우",
            "steps": [
                {"id": "s1", "title": "1단계", "type": "auto", "status": "pending"},
                {"id": "s2", "title": "2단계", "type": "manual", "status": "pending"},
            ],
        }
        save_resp = await client.post(
            f"/threads/{TASK}/{thread_id}/workflow", json=payload
        )
        assert save_resp.status_code == 200

        get_resp = await client.get(f"/threads/{TASK}/{thread_id}/workflow")
        data = get_resp.json()
        assert data["title"] == "커스텀 워크플로우"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["id"] == "s1"
        assert data["steps"][1]["type"] == "manual"

    async def test_save_auto_assigns_missing_step_id(self, client, thread_id):
        """id 없는 단계는 서버가 자동 할당해야 한다."""
        payload = {
            "title": "ID 자동 할당",
            "steps": [{"title": "id 없는 단계", "type": "auto", "status": "pending"}],
        }
        resp = await client.post(f"/threads/{TASK}/{thread_id}/workflow", json=payload)
        data = resp.json()
        assert data["steps"][0]["id"]  # 비어있지 않아야 함


class TestDeleteWorkflow:
    async def test_delete_returns_ok(self, client, thread_id):
        resp = await client.delete(f"/threads/{TASK}/{thread_id}/workflow")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_get_after_delete_returns_fresh_default(self, client, thread_id):
        """커스텀 저장 → 삭제 → GET 시 기본 템플릿으로 돌아와야 한다."""
        custom = {"title": "삭제 전 커스텀", "steps": [{"title": "임시", "type": "auto"}]}
        await client.post(f"/threads/{TASK}/{thread_id}/workflow", json=custom)
        await client.delete(f"/threads/{TASK}/{thread_id}/workflow")

        resp = await client.get(f"/threads/{TASK}/{thread_id}/workflow")
        data = resp.json()
        assert data["title"] != "삭제 전 커스텀"
        assert len(data["steps"]) > 0
