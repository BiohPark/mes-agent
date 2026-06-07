"""서버 기본 엔드포인트 통합 테스트: /health, /profile, /task-config."""

import pytest


class TestHealth:
    async def test_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestProfile:
    async def test_get_profile_shape(self, client):
        resp = await client.get("/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "active" in data
        assert "profiles" in data
        assert isinstance(data["profiles"], list)

    async def test_active_is_valid_profile(self, client):
        resp = await client.get("/profile")
        data = resp.json()
        assert data["active"] in data["profiles"]

    async def test_switch_profile(self, client):
        resp = await client.post("/profile/internal")
        assert resp.status_code == 200
        assert resp.json()["active"] == "internal"

        resp = await client.get("/profile")
        assert resp.json()["active"] == "internal"

    async def test_switch_invalid_profile_returns_error(self, client):
        resp = await client.post("/profile/nonexistent")
        assert resp.status_code in (400, 422, 500)


class TestTaskConfig:
    async def test_has_all_task_types(self, client):
        resp = await client.get("/task-config")
        assert resp.status_code == 200
        data = resp.json()
        for task_type in ("general", "syncade", "obsidian-rag", "unscript", "knox"):
            assert task_type in data, f"{task_type} 누락"

    async def test_each_task_has_required_fields(self, client):
        resp = await client.get("/task-config")
        data = resp.json()
        for task_type, info in data.items():
            assert "label" in info, f"{task_type}.label 누락"
            assert "icon" in info, f"{task_type}.icon 누락"
