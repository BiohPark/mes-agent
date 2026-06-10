"""협업모드(백로그 H) 단위 테스트 — 변화 게이트·toolless 힌트 호출."""

import pytest

from agent import collaborate as co


@pytest.fixture(autouse=True)
def _clear_sessions():
    co._sessions.clear()
    yield
    co._sessions.clear()


# ── start ─────────────────────────────────────────────────────
def test_start_sets_goal():
    co.start("t1", "보고서 작성 끝내기")
    assert co._sessions["t1"]["goal"] == "보고서 작성 끝내기"
    assert co._sessions["t1"]["last_shot"] is None


# ── _change_ratio ─────────────────────────────────────────────
def test_change_ratio_none_prev_is_full():
    assert co._change_ratio(None, b"whatever") == 1.0


def test_change_ratio_identical_is_zero():
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (10, 20, 30)).save(buf, format="PNG")
    png = buf.getvalue()
    assert co._change_ratio(png, png) == 0.0


# ── tick: 변화 게이트 ─────────────────────────────────────────
def test_tick_inactive_without_start():
    assert co.tick("nope") == {"active": False, "hint": None}


def test_tick_skips_llm_when_no_change(monkeypatch):
    co.start("t", "목표")
    calls = {"n": 0}
    monkeypatch.setattr(co, "screenshot_and_diff", lambda tid: (b"img", 0.0))
    monkeypatch.setattr(co, "make_hint", lambda *a: calls.__setitem__("n", calls["n"] + 1) or "힌트")
    out = co.tick("t")
    assert out["hint"] is None and out["skipped"] is True
    assert calls["n"] == 0, "변화가 없으면 LLM(make_hint)을 호출하면 안 됨"


def test_tick_force_bypasses_gate(monkeypatch):
    co.start("t", "목표")
    calls = {"n": 0}
    monkeypatch.setattr(co, "screenshot_and_diff", lambda tid: (b"img", 0.0))
    monkeypatch.setattr(co, "make_hint", lambda *a: calls.__setitem__("n", calls["n"] + 1) or "지금 저장하세요")
    out = co.tick("t", force=True)
    assert calls["n"] == 1
    assert out["hint"] == "지금 저장하세요"


def test_tick_calls_llm_when_changed(monkeypatch):
    co.start("t", "목표")
    monkeypatch.setattr(co, "screenshot_and_diff", lambda tid: (b"img", 0.5))
    monkeypatch.setattr(co, "make_hint", lambda *a: "다음 칸으로 이동하세요")
    out = co.tick("t")
    assert out["hint"] == "다음 칸으로 이동하세요"
    # 힌트 이력에 누적
    assert co._sessions["t"]["hint_history"] == ["다음 칸으로 이동하세요"]


# ── make_hint: 프롬프트에 goal + 이미지 포함, NONE 처리 ────────
class _FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]


def _fake_client(capture, content):
    class _Comp:
        def create(self, **kw):
            capture["messages"] = kw["messages"]
            capture["tools"] = kw.get("tools")
            return _FakeResp(content)
    class _Chat:
        completions = _Comp()
    class _Client:
        chat = _Chat()
    return _Client()


def test_make_hint_includes_goal_and_image(monkeypatch):
    cap = {}
    monkeypatch.setattr(co, "get_client", lambda: _fake_client(cap, "셀 서식을 통일하세요"))
    monkeypatch.setattr(co, "get_model", lambda: "gpt-test")
    hint = co.make_hint("표 정리", "QUJD", [])
    assert hint == "셀 서식을 통일하세요"
    # toolless 호출이어야 함
    assert cap["tools"] is None
    user = cap["messages"][-1]["content"]
    assert any(b.get("type") == "image_url" for b in user)
    assert any("표 정리" in b.get("text", "") for b in user)


def test_make_hint_none_returns_none(monkeypatch):
    monkeypatch.setattr(co, "get_client", lambda: _fake_client({}, "NONE"))
    monkeypatch.setattr(co, "get_model", lambda: "gpt-test")
    assert co.make_hint("목표", "QUJD", []) is None
