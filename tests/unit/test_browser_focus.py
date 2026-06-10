"""포커스 비탈취(백로그 I) 단위 테스트.

실제 win32 포커스 동작은 CI에서 검증 불가 → 결정 로직과 캡처/복원 호출 흐름만 검증한다.
"""

import json

import pytest

from agent.tools import browser as b


# ── _focus_steal_allowed ──────────────────────────────────────
def test_steal_allowed_explicit():
    assert b._focus_steal_allowed(True) is True
    assert b._focus_steal_allowed(False) is False


def test_steal_allowed_env_default_false(monkeypatch):
    monkeypatch.delenv("BROWSER_FOCUS_STEAL", raising=False)
    assert b._focus_steal_allowed(None) is False


def test_steal_allowed_env_true(monkeypatch):
    monkeypatch.setenv("BROWSER_FOCUS_STEAL", "true")
    assert b._focus_steal_allowed(None) is True


# ── _preserve_focus ───────────────────────────────────────────
def test_preserve_restores_when_not_allowed(monkeypatch):
    calls = []
    monkeypatch.setattr(b, "_capture_foreground", lambda: calls.append("capture") or "HWND")
    monkeypatch.setattr(b, "_restore_foreground", lambda h: calls.append(f"restore:{h}"))
    monkeypatch.delenv("BROWSER_FOCUS_STEAL", raising=False)

    result = b._preserve_focus(None, lambda: calls.append("fn") or "RESULT")

    assert result == "RESULT"
    # capture 먼저, fn 실행, 그다음 복원(캡처한 핸들로)
    assert calls == ["capture", "fn", "restore:HWND"]


def test_preserve_skips_when_allowed(monkeypatch):
    calls = []
    monkeypatch.setattr(b, "_capture_foreground", lambda: calls.append("capture"))
    monkeypatch.setattr(b, "_restore_foreground", lambda h: calls.append("restore"))

    result = b._preserve_focus(True, lambda: calls.append("fn") or "R")

    assert result == "R"
    assert calls == ["fn"], "steal 허용 시 캡처/복원을 하지 않아야 함"


def test_preserve_restores_even_on_exception(monkeypatch):
    calls = []
    monkeypatch.setattr(b, "_capture_foreground", lambda: "H")
    monkeypatch.setattr(b, "_restore_foreground", lambda h: calls.append("restore"))
    monkeypatch.delenv("BROWSER_FOCUS_STEAL", raising=False)

    with pytest.raises(RuntimeError):
        b._preserve_focus(None, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert calls == ["restore"], "예외가 나도 포커스는 복원돼야 함"


# ── browser_open 배선 ─────────────────────────────────────────
class _FakePage:
    url = "https://example.test"

    def goto(self, *a, **k):
        return None

    def title(self):
        return "T"


def test_browser_open_preserves_focus_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(b, "_get_page", lambda headless=False: _FakePage())
    monkeypatch.setattr(b, "_capture_foreground", lambda: calls.append("capture") or "H")
    monkeypatch.setattr(b, "_restore_foreground", lambda h: calls.append("restore"))
    monkeypatch.delenv("BROWSER_FOCUS_STEAL", raising=False)

    out = json.loads(b.browser_open("https://example.test"))
    assert out["url"] == "https://example.test"
    assert calls == ["capture", "restore"]


def test_browser_open_bring_to_front_skips_restore(monkeypatch):
    calls = []
    monkeypatch.setattr(b, "_get_page", lambda headless=False: _FakePage())
    monkeypatch.setattr(b, "_capture_foreground", lambda: calls.append("capture"))
    monkeypatch.setattr(b, "_restore_foreground", lambda h: calls.append("restore"))

    b.browser_open("https://example.test", bring_to_front=True)
    assert calls == [], "bring_to_front=True면 포커스 복원을 하지 않아야 함"
