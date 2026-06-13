"""백로그 O — Vault 명령함 순수 로직 단위 테스트.

inbox 명령 파싱·멱등 마킹·status 누적 포맷은 I/O 없는 순수 함수다.
"""

from agent.control.inbox import (
    extract_pending,
    mark_processed,
    format_status_entry,
    prepend_status,
    STATUS_HEADER,
)


class TestExtractPending:
    def test_extracts_unchecked_commands(self):
        text = (
            "# 명령함\n"
            "- [ ] 화면 OCR 해줘\n"
            "- [x] 이미 처리됨\n"
            "- [ ] syncade 배포 확인\n"
        )
        assert extract_pending(text) == ["화면 OCR 해줘", "syncade 배포 확인"]

    def test_ignores_checked_and_plain_lines(self):
        text = "설명 문장\n- [x] 끝난거\n그냥 글머리\n- 보통 리스트\n"
        assert extract_pending(text) == []

    def test_empty_text(self):
        assert extract_pending("") == []

    def test_strips_whitespace(self):
        assert extract_pending("- [ ]   여백 명령  \n") == ["여백 명령"]


class TestMarkProcessed:
    def test_flips_matching_line(self):
        text = "- [ ] 명령 A\n- [ ] 명령 B\n"
        out = mark_processed(text, "명령 A")
        assert "- [x] 명령 A" in out
        assert "- [ ] 명령 B" in out

    def test_only_first_match(self):
        text = "- [ ] 중복\n- [ ] 중복\n"
        out = mark_processed(text, "중복")
        assert out.count("- [x] 중복") == 1
        assert out.count("- [ ] 중복") == 1

    def test_idempotent_when_already_checked(self):
        text = "- [x] 명령 A\n"
        assert mark_processed(text, "명령 A") == text

    def test_unknown_command_unchanged(self):
        text = "- [ ] 명령 A\n"
        assert mark_processed(text, "없는 명령") == text


class TestStatusFormatting:
    def test_format_entry_contains_fields(self):
        entry = format_status_entry("화면 OCR", "텍스트입니다", "완료", "2026-06-13 10:30")
        assert "화면 OCR" in entry
        assert "텍스트입니다" in entry
        assert "완료" in entry
        assert "2026-06-13 10:30" in entry

    def test_prepend_creates_scaffold_when_empty(self):
        out = prepend_status("", "## 항목\n")
        assert STATUS_HEADER in out
        assert "## 항목" in out

    def test_prepend_newest_on_top(self):
        first = prepend_status("", format_status_entry("A", "r", "완료", "t1"))
        second = prepend_status(first, format_status_entry("B", "r", "완료", "t2"))
        # 헤더는 한 번만, B(나중)가 A보다 위
        assert second.count(STATUS_HEADER) == 1
        assert second.index("B") < second.index("A")
