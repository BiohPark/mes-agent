"""Phase 7: Obsidian PKM 툴 단위 테스트.

obsidian_preview_note / obsidian_scan_vault / obsidian_get_backlinks /
obsidian_read_section / obsidian_search_advanced / obsidian_edit_note /
obsidian_replace_section / obsidian_update_frontmatter / obsidian_move_note
"""

import json
import pytest
from pathlib import Path


# ── 공통 픽스처 ───────────────────────────────────────────────

@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_HOST", "")
    monkeypatch.setenv("OBSIDIAN_API_KEY", "")
    return tmp_path


def _write(vault: Path, rel: str, content: str) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ── TestPreviewNote ───────────────────────────────────────────

class TestPreviewNote:
    def test_returns_first_n_lines(self, vault):
        _write(vault, "note.md", "\n".join(f"line{i}" for i in range(30)))
        from agent.tools.obsidian_rag import obsidian_preview_note
        result = json.loads(obsidian_preview_note("note.md", lines=10))
        assert "error" not in result
        assert result["preview"].count("\n") == 9  # 10줄 = 9 개의 \n

    def test_includes_size_info(self, vault):
        _write(vault, "note.md", "hello world")
        from agent.tools.obsidian_rag import obsidian_preview_note
        result = json.loads(obsidian_preview_note("note.md"))
        assert "size_kb" in result
        assert result["size_kb"] >= 0

    def test_includes_total_lines(self, vault):
        _write(vault, "note.md", "\n".join(["a"] * 50))
        from agent.tools.obsidian_rag import obsidian_preview_note
        result = json.loads(obsidian_preview_note("note.md"))
        assert result["total_lines"] == 50

    def test_parses_frontmatter(self, vault):
        _write(vault, "fm.md", "---\ntags: pkm\nauthor: test\n---\nbody")
        from agent.tools.obsidian_rag import obsidian_preview_note
        result = json.loads(obsidian_preview_note("fm.md"))
        assert result["frontmatter"].get("tags") == "pkm"

    def test_missing_note_returns_error(self, vault):
        from agent.tools.obsidian_rag import obsidian_preview_note
        result = json.loads(obsidian_preview_note("nonexistent.md"))
        assert "error" in result


# ── TestScanVault ─────────────────────────────────────────────

class TestScanVault:
    def test_scan_by_paths(self, vault):
        _write(vault, "a.md", "content a")
        _write(vault, "b.md", "content b")
        from agent.tools.obsidian_rag import obsidian_scan_vault
        result = json.loads(obsidian_scan_vault(paths=["a.md", "b.md"]))
        assert result["count"] == 2
        paths = [n["path"] for n in result["notes"]]
        assert "a.md" in paths and "b.md" in paths

    def test_scan_by_folder(self, vault):
        _write(vault, "sub/x.md", "x")
        _write(vault, "sub/y.md", "y")
        from agent.tools.obsidian_rag import obsidian_scan_vault
        result = json.loads(obsidian_scan_vault(folder="sub"))
        assert result["count"] >= 2

    def test_limit_respected(self, vault):
        for i in range(10):
            _write(vault, f"note{i}.md", f"content {i}")
        from agent.tools.obsidian_rag import obsidian_scan_vault
        result = json.loads(obsidian_scan_vault(folder="", limit=3))
        assert result["count"] <= 3


# ── TestGetBacklinks ──────────────────────────────────────────

class TestGetBacklinks:
    def test_finds_backlinks(self, vault):
        _write(vault, "target.md", "# Target")
        _write(vault, "ref1.md", "See also [[target]] for details.")
        _write(vault, "ref2.md", "As mentioned in [[target|Target Note]].")
        from agent.tools.obsidian_rag import obsidian_get_backlinks
        result = json.loads(obsidian_get_backlinks("target.md"))
        assert result["count"] == 2
        assert "ref1.md" in result["backlinks"]
        assert "ref2.md" in result["backlinks"]

    def test_empty_when_no_backlinks(self, vault):
        _write(vault, "isolated.md", "# No links here")
        _write(vault, "other.md", "No references.")
        from agent.tools.obsidian_rag import obsidian_get_backlinks
        result = json.loads(obsidian_get_backlinks("isolated.md"))
        assert result["count"] == 0

    def test_excludes_self(self, vault):
        _write(vault, "self.md", "This note [[self|links to itself]].")
        from agent.tools.obsidian_rag import obsidian_get_backlinks
        result = json.loads(obsidian_get_backlinks("self.md"))
        assert "self.md" not in result["backlinks"]

    def test_finds_heading_links(self, vault):
        _write(vault, "target.md", "# Target")
        _write(vault, "ref.md", "See [[target#Section]] for more.")
        from agent.tools.obsidian_rag import obsidian_get_backlinks
        result = json.loads(obsidian_get_backlinks("target.md"))
        assert "ref.md" in result["backlinks"]


# ── TestReadSection ───────────────────────────────────────────

class TestReadSection:
    NOTE = "\n".join([
        "# 전체 노트",
        "인트로 내용",
        "",
        "## 섹션 A",
        "A 내용 1",
        "A 내용 2",
        "",
        "## 섹션 B",
        "B 내용",
        "",
        "### 하위 섹션",
        "하위 내용",
    ])

    def test_reads_h2_section(self, vault):
        _write(vault, "note.md", self.NOTE)
        from agent.tools.obsidian_rag import obsidian_read_section
        result = json.loads(obsidian_read_section("note.md", "섹션 A"))
        assert "error" not in result
        assert "A 내용 1" in result["content"]
        assert "A 내용 2" in result["content"]
        assert "B 내용" not in result["content"]  # 다음 섹션은 포함 안 됨

    def test_stops_at_next_sibling(self, vault):
        _write(vault, "note.md", self.NOTE)
        from agent.tools.obsidian_rag import obsidian_read_section
        result = json.loads(obsidian_read_section("note.md", "섹션 B"))
        assert "B 내용" in result["content"]
        assert "하위 내용" in result["content"]  # 하위 섹션은 포함
        assert "A 내용" not in result["content"]

    def test_missing_heading_returns_error(self, vault):
        _write(vault, "note.md", self.NOTE)
        from agent.tools.obsidian_rag import obsidian_read_section
        result = json.loads(obsidian_read_section("note.md", "존재하지않는헤딩"))
        assert "error" in result

    def test_case_insensitive_heading(self, vault):
        _write(vault, "note.md", "## Hello World\ncontent")
        from agent.tools.obsidian_rag import obsidian_read_section
        result = json.loads(obsidian_read_section("note.md", "hello world"))
        assert "error" not in result
        assert "content" in result["content"]


# ── TestSearchAdvanced ────────────────────────────────────────

class TestSearchAdvanced:
    def test_filter_by_folder(self, vault):
        _write(vault, "docs/a.md", "문서 A")
        _write(vault, "docs/b.md", "문서 B")
        _write(vault, "other/c.md", "기타 C")
        from agent.tools.obsidian_rag import obsidian_search_advanced
        result = json.loads(obsidian_search_advanced(folder="docs"))
        paths = result["results"]
        assert all(p.startswith("docs/") for p in paths)
        assert result["count"] >= 2

    def test_filter_by_tag(self, vault):
        _write(vault, "tagged.md", "---\ntags: pkm\n---\n내용")
        _write(vault, "no_tag.md", "태그 없음")
        from agent.tools.obsidian_rag import obsidian_search_advanced
        result = json.loads(obsidian_search_advanced(tags=["pkm"]))
        assert "tagged.md" in result["results"]
        assert "no_tag.md" not in result["results"]

    def test_empty_query_returns_vault_files(self, vault):
        _write(vault, "a.md", "a")
        _write(vault, "b.md", "b")
        from agent.tools.obsidian_rag import obsidian_search_advanced
        result = json.loads(obsidian_search_advanced())
        assert result["count"] >= 2


# ── TestEditNote ──────────────────────────────────────────────

class TestEditNote:
    def test_replaces_text(self, vault):
        _write(vault, "note.md", "Hello World! This is a test.")
        from agent.tools.obsidian_rag import obsidian_edit_note
        result = json.loads(obsidian_edit_note("note.md", "World", "Universe"))
        assert "error" not in result
        # 실제로 바뀌었는지 확인
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "Universe" in content
        assert "World" not in content

    def test_error_when_not_found(self, vault):
        _write(vault, "note.md", "Hello World")
        from agent.tools.obsidian_rag import obsidian_edit_note
        result = json.loads(obsidian_edit_note("note.md", "없는텍스트", "대체텍스트"))
        assert "error" in result

    def test_error_when_ambiguous(self, vault):
        _write(vault, "note.md", "foo bar foo baz foo")
        from agent.tools.obsidian_rag import obsidian_edit_note
        result = json.loads(obsidian_edit_note("note.md", "foo", "qux"))
        assert "error" in result
        assert "3" in result["error"]  # 3곳 발견

    def test_replaces_only_first_if_unique(self, vault):
        _write(vault, "note.md", "unique target here")
        from agent.tools.obsidian_rag import obsidian_edit_note
        result = json.loads(obsidian_edit_note("note.md", "unique target", "replaced"))
        assert "error" not in result


# ── TestReplaceSection ────────────────────────────────────────

class TestReplaceSection:
    def test_replaces_section_content(self, vault):
        _write(vault, "note.md", "## 섹션\n기존 내용\n\n## 다음 섹션\n다음 내용")
        from agent.tools.obsidian_rag import obsidian_replace_section
        result = json.loads(obsidian_replace_section("note.md", "섹션", "새로운 내용"))
        assert "error" not in result
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "새로운 내용" in content
        assert "기존 내용" not in content
        assert "다음 내용" in content  # 다음 섹션 보존

    def test_preserves_heading_line(self, vault):
        _write(vault, "note.md", "## 섹션\n기존\n## 다음\n다음")
        from agent.tools.obsidian_rag import obsidian_replace_section
        obsidian_replace_section("note.md", "섹션", "교체")
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "## 섹션" in content  # 헤딩 줄 자체는 보존

    def test_missing_heading_returns_error(self, vault):
        _write(vault, "note.md", "## 다른 섹션\n내용")
        from agent.tools.obsidian_rag import obsidian_replace_section
        result = json.loads(obsidian_replace_section("note.md", "없는섹션", "내용"))
        assert "error" in result


# ── TestUpdateFrontmatter ─────────────────────────────────────

class TestUpdateFrontmatter:
    def test_adds_new_field(self, vault):
        _write(vault, "note.md", "---\ntags: pkm\n---\n본문")
        from agent.tools.obsidian_rag import obsidian_update_frontmatter
        result = json.loads(obsidian_update_frontmatter("note.md", {"status": "draft"}))
        assert "error" not in result
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "status" in content
        assert "draft" in content

    def test_updates_existing_field(self, vault):
        _write(vault, "note.md", "---\nstatus: draft\n---\n본문")
        from agent.tools.obsidian_rag import obsidian_update_frontmatter
        obsidian_update_frontmatter("note.md", {"status": "published"})
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "published" in content
        assert "draft" not in content

    def test_creates_frontmatter_if_none(self, vault):
        _write(vault, "note.md", "프론트매터 없는 본문")
        from agent.tools.obsidian_rag import obsidian_update_frontmatter
        result = json.loads(obsidian_update_frontmatter("note.md", {"tags": "new"}))
        assert "error" not in result
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "---" in content
        assert "tags" in content

    def test_preserves_body_content(self, vault):
        _write(vault, "note.md", "---\ntags: a\n---\n중요한 본문 내용")
        from agent.tools.obsidian_rag import obsidian_update_frontmatter
        obsidian_update_frontmatter("note.md", {"new_field": "value"})
        content = (vault / "note.md").read_text(encoding="utf-8")
        assert "중요한 본문 내용" in content


# ── TestMoveNote ──────────────────────────────────────────────

class TestMoveNote:
    def test_moves_file(self, vault):
        _write(vault, "old/note.md", "# 이동할 노트")
        from agent.tools.obsidian_rag import obsidian_move_note
        result = json.loads(obsidian_move_note("old/note.md", "new/note.md"))
        assert result.get("moved") is True
        assert (vault / "new/note.md").exists()

    def test_source_deleted_after_move(self, vault):
        _write(vault, "src.md", "내용")
        from agent.tools.obsidian_rag import obsidian_move_note
        obsidian_move_note("src.md", "dst.md")
        assert not (vault / "src.md").exists()

    def test_updates_wikilinks(self, vault):
        _write(vault, "original.md", "# Original")
        _write(vault, "ref.md", "참조: [[original]] 노트")
        from agent.tools.obsidian_rag import obsidian_move_note
        result = json.loads(obsidian_move_note("original.md", "renamed.md", update_links=True))
        assert result["links_updated"] >= 1
        ref_content = (vault / "ref.md").read_text(encoding="utf-8")
        assert "[[renamed]]" in ref_content
        assert "[[original]]" not in ref_content

    def test_no_link_update_when_false(self, vault):
        _write(vault, "original.md", "# Original")
        _write(vault, "ref.md", "참조: [[original]] 노트")
        from agent.tools.obsidian_rag import obsidian_move_note
        result = json.loads(obsidian_move_note("original.md", "renamed.md", update_links=False))
        ref_content = (vault / "ref.md").read_text(encoding="utf-8")
        assert "[[original]]" in ref_content  # 업데이트 안 됨

    def test_missing_source_returns_error(self, vault):
        from agent.tools.obsidian_rag import obsidian_move_note
        result = json.loads(obsidian_move_note("nonexistent.md", "dst.md"))
        assert "error" in result

    def test_same_stem_no_link_scan(self, vault):
        """이름이 같고 폴더만 다를 때는 링크 내용 변경 불필요."""
        _write(vault, "old/note.md", "# Note")
        _write(vault, "ref.md", "참조: [[note]]")
        from agent.tools.obsidian_rag import obsidian_move_note
        result = json.loads(obsidian_move_note("old/note.md", "new/note.md", update_links=True))
        assert result.get("moved") is True
        ref_content = (vault / "ref.md").read_text(encoding="utf-8")
        assert "[[note]]" in ref_content  # stem 동일 → 링크 그대로
