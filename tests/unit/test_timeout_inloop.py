"""V-2 Phase 2 인루프 판단 — 도구별 회복 대안 + 번호 매긴 오류 텍스트 테스트."""

import pytest
from agent.core.timeouts import (
    _lookup_alternatives,
    _DEFAULT_ALTERNATIVES,
    classify_timeout,
    timeout_error_text,
)


# ── TestAlternativesLookup ───────────────────────────────────

class TestAlternativesLookup:
    def test_exact_match_returns_tool_specific_alts(self):
        alts = _lookup_alternatives("run_command")
        assert isinstance(alts, list)
        assert len(alts) >= 2
        assert any("timeout" in a for a in alts)

    def test_prefix_match_browser(self):
        """browser_click → browser_ 카테고리 대안."""
        alts = _lookup_alternatives("browser_click")
        assert isinstance(alts, list)
        assert any("browser" in a.lower() or "screenshot" in a.lower() for a in alts)

    def test_prefix_match_excel(self):
        """excel_get_range → excel_ 카테고리 (office_ 아님)."""
        alts = _lookup_alternatives("excel_get_range")
        assert isinstance(alts, list)
        assert any("read_excel" in a or "openpyxl" in a or "CSV" in a for a in alts)

    def test_prefix_match_office(self):
        """office_open → office_ 카테고리."""
        alts = _lookup_alternatives("office_open")
        assert isinstance(alts, list)
        assert any("read_word" in a or "read_excel" in a or "openpyxl" in a for a in alts)

    def test_unknown_tool_returns_defaults(self):
        alts = _lookup_alternatives("xyz_completely_unknown_tool")
        assert alts == _DEFAULT_ALTERNATIVES

    def test_default_alternatives_non_empty(self):
        assert len(_DEFAULT_ALTERNATIVES) >= 2
        assert any("ask_user" in a for a in _DEFAULT_ALTERNATIVES)

    def test_read_excel_specific(self):
        """read_excel은 정확히 일치하는 개별 대안을 반환해야 한다."""
        alts = _lookup_alternatives("read_excel")
        # excel_ 접두보다 정확한 일치가 우선
        assert any("범위" in a or "행" in a or "CSV" in a for a in alts)


# ── TestClassifyTimeoutAlternatives ─────────────────────────

class TestClassifyTimeoutAlternatives:
    def test_classify_includes_alternatives_field(self):
        result = classify_timeout("run_command", 90.0)
        assert "alternatives" in result

    def test_alternatives_is_list_of_strings(self):
        result = classify_timeout("browser_click", 30.0)
        alts = result["alternatives"]
        assert isinstance(alts, list)
        assert all(isinstance(a, str) for a in alts)
        assert len(alts) >= 1

    def test_slow_hint_differs_from_stuck(self):
        slow = classify_timeout("run_command", 90.0, progressed=True)
        stuck = classify_timeout("run_command", 90.0, progressed=False)
        assert slow["failureClass"] == "slow"
        assert stuck["failureClass"] == "stuck"
        assert slow["hint"] != stuck["hint"]

    def test_existing_fields_preserved(self):
        """기존 필드(failureClass/provenance/tool/waited_seconds/hint)가 그대로 있어야 한다."""
        result = classify_timeout("run_command", 45.0)
        for key in ("failureClass", "provenance", "tool", "waited_seconds", "hint"):
            assert key in result


# ── TestTimeoutErrorText ─────────────────────────────────────

class TestTimeoutErrorText:
    def test_maintains_error_prefix(self):
        """기존 UI/서버 에러 분기 호환 — '툴 실행 오류' 접두 유지."""
        text = timeout_error_text("run_command", 90.0)
        assert text.startswith("툴 실행 오류")

    def test_includes_numbered_options(self):
        text = timeout_error_text("run_command", 90.0)
        assert "1." in text
        assert "2." in text

    def test_includes_recovery_section_header(self):
        text = timeout_error_text("run_command", 90.0)
        assert "회복 옵션" in text

    def test_includes_ask_user_guidance(self):
        text = timeout_error_text("run_command", 90.0)
        assert "ask_user" in text

    def test_browser_tool_shows_browser_alts(self):
        text = timeout_error_text("browser_navigate", 30.0)
        assert "browser" in text.lower() or "screenshot" in text.lower()

    def test_unknown_tool_shows_defaults(self):
        text = timeout_error_text("xyz_mystery_tool", 90.0)
        assert "ask_user" in text
