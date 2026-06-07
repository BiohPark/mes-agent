"""office_com 단위 테스트.

- COM(설치된 Office) 가능 시: Word 찾아바꾸기·Excel 셀편집 라운드트립
- COM 불가 환경: 라이브러리 폴백(python-docx/openpyxl) 경로 검증 (monkeypatch로 강제)
- 안전 가드: 가짜 .docx(마크다운 텍스트)를 OOXML 검증으로 거부하는지
"""

import json
import zipfile

import pytest

from agent.tools import office_com as oc
from agent.tools.document import write_word, read_word, write_excel


# ── 안전 가드 ────────────────────────────────────────────────

def test_validate_rejects_fake_docx(tmp_path):
    """마크다운 텍스트를 .docx로 저장한 깨진 파일은 편집을 거부해야 한다(3.2 회귀 방지)."""
    fake = tmp_path / "fake.docx"
    fake.write_text("# 제목\n진짜 docx 아님", encoding="utf-8")
    res = json.loads(oc.word_edit_text(str(fake), "제목", "헤더"))
    assert "error" in res
    assert "OOXML" in res["error"]


def test_backup_created_on_edit(tmp_path):
    path = tmp_path / "doc.docx"
    write_word(str(path), "hello TARGET world", "T")
    res = json.loads(oc.word_edit_text(str(path), "TARGET", "REPLACED"))
    # COM이든 폴백이든 백업 경로가 있어야 한다
    assert res.get("backup")
    assert list(tmp_path.glob("doc.*.docx.bak"))


# ── 라이브러리 폴백 (COM 강제 비활성) ─────────────────────────

def test_word_edit_docx_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(oc, "_HAS_PYWIN32", False)
    path = tmp_path / "doc.docx"
    write_word(str(path), "매출 OLDVAL 달성", "보고서")
    res = json.loads(oc.word_edit_text(str(path), "OLDVAL", "1억원"))
    assert res["engine"] == "docx"
    txt = read_word(str(path))
    assert "1억원" in txt and "OLDVAL" not in txt


def test_excel_set_cells_openpyxl_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(oc, "_HAS_PYWIN32", False)
    path = tmp_path / "wb.xlsx"
    write_excel(str(path), [{"A": "1", "B": "2"}], "Sheet1")
    res = json.loads(oc.excel_set_cells(str(path), {"C1": "합계"}))
    assert res["engine"] == "openpyxl"
    got = json.loads(oc.excel_get_range(str(path), "C1:C1"))
    assert got["values"][0][0] == "합계"


def test_pdf_export_requires_com(tmp_path, monkeypatch):
    monkeypatch.setattr(oc, "_HAS_PYWIN32", False)
    path = tmp_path / "doc.docx"
    write_word(str(path), "내용", "T")
    res = json.loads(oc.word_export_pdf(str(path)))
    assert "error" in res and res["engine"] == "none"


# ── COM 라운드트립 (Office 설치 시에만) ───────────────────────

@pytest.mark.skipif(not oc._HAS_PYWIN32, reason="pywin32/Office COM 미사용 환경")
class TestComRoundtrip:
    def test_word_edit_com_preserves(self, tmp_path):
        path = tmp_path / "r.docx"
        write_word(str(path), "값 OLDVAL 그리고 OLDVAL 둘", "T")
        res = json.loads(oc.word_edit_text(str(path), "OLDVAL", "NEWVAL"))
        if res.get("engine") == "com":
            assert res["occurrences"] == 2
        txt = read_word(str(path))
        assert "NEWVAL" in txt and "OLDVAL" not in txt
        oc.office_close()

    def test_excel_formula_com(self, tmp_path):
        path = tmp_path / "r.xlsx"
        # row1=헤더(A,B), row2=데이터(10,4) → 수식은 데이터 행(A2/B2)을 참조
        write_excel(str(path), [{"A": "10", "B": "4"}], "Sheet1")
        oc.excel_set_cells(str(path), {"C2": "=A2-B2"})
        got = json.loads(oc.excel_get_range(str(path), "C2:C2"))
        oc.office_close()
        # COM이면 수식이 계산되어 6, openpyxl 폴백이면 '=A2-B2' 문자열
        assert got["values"][0][0] in (6, 6.0, "=A2-B2")

    def test_word_insert_text_com(self, tmp_path):
        path = tmp_path / "ins.docx"
        write_word(str(path), "# 제목\n\n결론 부분", "T")
        res = json.loads(oc.word_insert_text(str(path), "삽입된 문장입니다"))
        assert res.get("backup")
        assert "삽입된 문장입니다" in read_word(str(path))
        oc.office_close()


# ── PowerPoint (python-pptx — Office 설치 불필요) ─────────────

class TestPpt:
    def test_ppt_add_and_replace(self, tmp_path):
        path = tmp_path / "deck.pptx"
        r1 = json.loads(oc.ppt_add_slide(str(path), "제목", "본문 PLACEHOLDER 줄"))
        assert "error" not in r1
        assert zipfile.is_zipfile(path)
        r2 = json.loads(oc.ppt_replace_text(str(path), "PLACEHOLDER", "확정값"))
        assert r2["occurrences"] >= 1
        from agent.tools.document import read_ppt_content
        assert "확정값" in read_ppt_content(str(path))

    def test_ppt_validates_fake(self, tmp_path):
        fake = tmp_path / "fake.pptx"
        fake.write_text("not a real pptx", encoding="utf-8")
        res = json.loads(oc.ppt_replace_text(str(fake), "a", "b"))
        assert "error" in res
