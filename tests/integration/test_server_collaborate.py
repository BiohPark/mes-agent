"""협업모드 엔드포인트 통합 테스트 (백로그 H).

실제 화면 캡처/LLM은 monkeypatch로 차단한다.
"""

import pytest


@pytest.fixture(autouse=True)
def _clear_sessions():
    from agent import collaborate
    collaborate._sessions.clear()
    yield
    collaborate._sessions.clear()


class TestCollaborateEndpoints:
    async def test_start_then_tick_returns_hint(self, client, monkeypatch):
        from agent import collaborate
        monkeypatch.setattr(collaborate, "screenshot_and_diff", lambda tid: (b"img", 0.9))
        monkeypatch.setattr(collaborate, "make_hint", lambda *a: "정렬을 맞추세요")

        r = await client.post("/collaborate/start", json={"thread_id": "c1", "goal": "표 정리"})
        assert r.json()["ok"] is True

        t = await client.post("/collaborate/tick", json={"thread_id": "c1"})
        assert t.json()["hint"] == "정렬을 맞추세요"

    async def test_tick_inactive_without_start(self, client):
        t = await client.post("/collaborate/tick", json={"thread_id": "never-started"})
        assert t.json() == {"active": False, "hint": None}

    async def test_tick_skips_when_no_change(self, client, monkeypatch):
        from agent import collaborate
        called = {"n": 0}
        monkeypatch.setattr(collaborate, "screenshot_and_diff", lambda tid: (b"img", 0.0))
        monkeypatch.setattr(collaborate, "make_hint",
                            lambda *a: called.__setitem__("n", called["n"] + 1) or "x")

        await client.post("/collaborate/start", json={"thread_id": "c2", "goal": "g"})
        t = await client.post("/collaborate/tick", json={"thread_id": "c2"})
        assert t.json()["hint"] is None and t.json().get("skipped") is True
        assert called["n"] == 0

    async def test_stop(self, client):
        from agent import collaborate
        await client.post("/collaborate/start", json={"thread_id": "c3", "goal": "g"})
        assert "c3" in collaborate._sessions
        await client.post("/collaborate/stop", json={"thread_id": "c3"})
        assert "c3" not in collaborate._sessions
