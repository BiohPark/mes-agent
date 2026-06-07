"""MS Office 편집 엔진 (COM 자동화 + 라이브러리 폴백)

요구사항: 기존 Office 문서를 **열고·편집·저장**하는 고품질 기능.
- 1순위: 설치된 Word/Excel을 COM(win32com)으로 구동 → Office 자체 엔진으로 완전 충실도
  (서식 보존, 수식, 수정추적 수락, 메모 작성, PDF 내보내기)
- 2순위(COM 불가 시): python-docx / openpyxl 로 자동 폴백

핵심 제약: COM은 STA(단일 스레드 아파트)다. 모든 COM 호출은 CoInitialize 한 **하나의 스레드**에서
이뤄져야 한다. 브라우저(browser.py)의 greenlet 단일 스레드 패턴을 그대로 재사용한다.

안전 가드(품질 핵심):
- 편집 전 자동 백업(.bak) — 원본 손실 방지
- 입력이 진짜 OOXML(zip)인지 검증 후 편집
- 작업 결과에 사용된 엔진(com/docx/openpyxl)과 백업 경로를 명시
"""

import os
import json
import zipfile
import shutil
import atexit
import functools
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ── pywin32 가용성 탐지 ───────────────────────────────────────
try:
    import pythoncom  # noqa: F401
    import win32com.client  # noqa: F401
    _HAS_PYWIN32 = True
except Exception:
    _HAS_PYWIN32 = False


# ── 전용 STA 단일 스레드 ──────────────────────────────────────
def _com_thread_init():
    """워커 스레드에서 COM을 초기화한다(STA). pywin32 없으면 무시."""
    if _HAS_PYWIN32:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass


_com_executor = ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="office-com", initializer=_com_thread_init
)


def _on_com_thread(fn):
    """핸들러를 전용 COM 스레드에서 실행하고 결과를 동기 반환한다."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return _com_executor.submit(fn, *args, **kwargs).result()
    return wrapper


# ── COM 앱 싱글턴 (전용 스레드에서만 접근) ────────────────────
_word_app = None
_excel_app = None


def _get_word():
    global _word_app
    import win32com.client as win32
    if _word_app is None:
        _word_app = win32.dynamic.Dispatch("Word.Application")
        _word_app.Visible = False
        try:
            _word_app.DisplayAlerts = False
        except Exception:
            pass
    return _word_app


def _get_excel():
    global _excel_app
    import win32com.client as win32
    if _excel_app is None:
        _excel_app = win32.dynamic.Dispatch("Excel.Application")
        _excel_app.Visible = False
        _excel_app.DisplayAlerts = False
    return _excel_app


def _quit_apps():
    """프로세스 종료 시 좀비 WINWORD.EXE/EXCEL.EXE 방지."""
    global _word_app, _excel_app
    for app in (_word_app, _excel_app):
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
    _word_app = None
    _excel_app = None


def _close_apps_on_com_thread():
    if _HAS_PYWIN32:
        try:
            _com_executor.submit(_quit_apps).result(timeout=10)
        except Exception:
            pass


atexit.register(_close_apps_on_com_thread)


# ── 공통 안전 헬퍼 ────────────────────────────────────────────
def _abspath(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _validate_ooxml(path: str) -> str | None:
    """진짜 OOXML(zip)인지 검증. 문제 있으면 오류 메시지, 정상이면 None."""
    if not os.path.exists(path):
        return f"파일이 존재하지 않습니다: {path}"
    if not zipfile.is_zipfile(path):
        return (f"올바른 Office 파일이 아닙니다(OOXML zip 아님): {path}. "
                "마크다운/텍스트를 .docx로 잘못 저장한 파일일 수 있습니다.")
    return None


def _backup(path: str) -> str | None:
    """편집 전 타임스탬프 백업본을 만든다. 경로 반환."""
    p = Path(path)
    if not p.exists():
        return None
    bak = p.with_name(f"{p.stem}.{datetime.now():%Y%m%d_%H%M%S}{p.suffix}.bak")
    shutil.copy2(p, bak)
    return str(bak)


def _no_com_msg(op: str) -> str:
    return json.dumps({
        "error": f"이 작업({op})은 설치된 MS Office(COM)가 필요합니다. "
                 "이 PC에서 Word/Excel COM을 사용할 수 없습니다.",
        "engine": "none",
    }, ensure_ascii=False)


# ── Word 편집 ─────────────────────────────────────────────────

def word_edit_text(path: str, find: str, replace: str,
                   match_case: bool = False, whole_word: bool = False) -> str:
    """기존 Word 문서에서 텍스트를 찾아 바꾸고 저장합니다(서식 보존).
    COM 우선, 불가 시 python-docx 폴백. 편집 전 자동 백업."""
    path = _abspath(path)
    err = _validate_ooxml(path)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    backup = _backup(path)

    # 1) COM 경로
    if _HAS_PYWIN32:
        try:
            word = _get_word()
            doc = word.Documents.Open(path)
            try:
                count_before = doc.Content.Text.count(find)
                f = doc.Content.Find
                f.ClearFormatting()
                f.Replacement.ClearFormatting()
                # win32com 동적 디스패치는 Find.Execute의 키워드 인자(특히 Replace)를
                # 제대로 바인딩하지 못한다. 반드시 완전 위치 인자로 호출한다.
                # (FindText, MatchCase, MatchWholeWord, MatchWildcards, MatchSoundsLike,
                #  MatchAllWordForms, Forward, Wrap, Format, ReplaceWith, Replace)
                # Wrap=1(wdFindContinue), Replace=2(wdReplaceAll)
                f.Execute(find, match_case, whole_word, False, False, False,
                          True, 1, False, replace, 2)
                doc.Save()
            finally:
                doc.Close()
            return json.dumps({
                "path": path, "engine": "com", "backup": backup,
                "find": find[:50], "replace": replace[:50],
                "occurrences": count_before,
                "message": "Word 찾아바꾸기 완료(서식 보존)",
            }, ensure_ascii=False)
        except Exception as e:
            # COM 실패 → 폴백 시도
            com_err = str(e)
    else:
        com_err = "pywin32/COM 미사용"

    # 2) python-docx 폴백 (단락·표 셀 단위 치환)
    try:
        import docx
        doc = docx.Document(path)
        n = 0

        def _replace_in_paragraph(par):
            nonlocal n
            if find in par.text:
                # 단락 전체 텍스트를 첫 run에 합쳐 치환(런 분할로 인한 누락 방지)
                full = par.text.replace(find, replace)
                n += par.text.count(find)
                for r in par.runs:
                    r.text = ""
                if par.runs:
                    par.runs[0].text = full
                else:
                    par.add_run(full)

        for par in doc.paragraphs:
            _replace_in_paragraph(par)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for par in cell.paragraphs:
                        _replace_in_paragraph(par)
        doc.save(path)
        return json.dumps({
            "path": path, "engine": "docx", "backup": backup,
            "occurrences": n, "com_error": com_err,
            "message": "Word 찾아바꾸기 완료(python-docx 폴백 — 일부 서식은 단순화될 수 있음)",
        }, ensure_ascii=False)
    except Exception as e2:
        return json.dumps({"error": f"COM/라이브러리 모두 실패: {com_err} | {e2}",
                           "backup": backup}, ensure_ascii=False)


def word_export_pdf(path: str, pdf_path: str = "") -> str:
    """Word 문서를 PDF로 내보냅니다. (설치된 Word 필요)"""
    path = _abspath(path)
    err = _validate_ooxml(path)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    if not _HAS_PYWIN32:
        return _no_com_msg("PDF 내보내기")
    if not pdf_path:
        pdf_path = str(Path(path).with_suffix(".pdf"))
    pdf_path = _abspath(pdf_path)
    try:
        word = _get_word()
        doc = word.Documents.Open(path)
        try:
            doc.ExportAsFixedFormat(OutputFileName=pdf_path, ExportFormat=17)  # wdExportFormatPDF
        finally:
            doc.Close(SaveChanges=0)
        return json.dumps({"path": pdf_path, "engine": "com",
                           "message": "PDF 내보내기 완료"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "engine": "com"}, ensure_ascii=False)


def word_accept_all_changes(path: str) -> str:
    """Word 문서의 모든 수정추적(Track Changes)을 수락하고 저장합니다. (설치된 Word 필요)"""
    path = _abspath(path)
    err = _validate_ooxml(path)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    if not _HAS_PYWIN32:
        return _no_com_msg("수정추적 수락")
    backup = _backup(path)
    try:
        word = _get_word()
        doc = word.Documents.Open(path)
        try:
            doc.AcceptAllRevisions()
            doc.Save()
        finally:
            doc.Close()
        return json.dumps({"path": path, "engine": "com", "backup": backup,
                           "message": "모든 수정추적 수락 완료"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "backup": backup}, ensure_ascii=False)


def word_add_comment(path: str, anchor_text: str, comment: str) -> str:
    """Word 문서에서 특정 텍스트에 검토 메모(Comment)를 추가합니다. (설치된 Word 필요)"""
    path = _abspath(path)
    err = _validate_ooxml(path)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    if not _HAS_PYWIN32:
        return _no_com_msg("메모 작성")
    backup = _backup(path)
    try:
        word = _get_word()
        doc = word.Documents.Open(path)
        try:
            # Range를 변수로 잡고 그 Find를 실행하면, 일치 시 Range가 찾은 범위로 재정의된다.
            rng = doc.Content
            f = rng.Find
            f.ClearFormatting()
            found = f.Execute(anchor_text, False, False, False, False, False, True, 1)
            if not found:
                doc.Close(SaveChanges=0)
                return json.dumps({"error": f"앵커 텍스트를 찾지 못했습니다: {anchor_text[:50]}",
                                   "backup": backup}, ensure_ascii=False)
            doc.Comments.Add(Range=rng, Text=comment)
            doc.Save()
        finally:
            doc.Close()
        return json.dumps({"path": path, "engine": "com", "backup": backup,
                           "message": "검토 메모 추가 완료"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "backup": backup}, ensure_ascii=False)


# ── Excel 편집 ────────────────────────────────────────────────

def excel_set_cells(path: str, cells: dict, sheet: str = "") -> str:
    """기존 Excel 워크북의 특정 셀들에 값/수식을 설정하고 저장합니다.
    cells 예: {"B2": "=A1+A2", "C3": "합계"}. COM 우선, 불가 시 openpyxl 폴백."""
    path = _abspath(path)
    err = _validate_ooxml(path)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)
    if not isinstance(cells, dict) or not cells:
        return json.dumps({"error": "cells는 비어있지 않은 {셀주소: 값} 객체여야 합니다."},
                          ensure_ascii=False)
    backup = _backup(path)

    # 1) COM 경로
    if _HAS_PYWIN32:
        try:
            excel = _get_excel()
            wb = excel.Workbooks.Open(path)
            try:
                ws = wb.Worksheets(sheet) if sheet else wb.ActiveSheet
                for addr, val in cells.items():
                    ws.Range(addr).Value = val  # '='로 시작하면 수식으로 처리됨
                wb.Save()
            finally:
                wb.Close(SaveChanges=0)
            return json.dumps({"path": path, "engine": "com", "backup": backup,
                               "cells_set": len(cells),
                               "message": "Excel 셀 편집 완료(수식·서식 보존)"}, ensure_ascii=False)
        except Exception as e:
            com_err = str(e)
    else:
        com_err = "pywin32/COM 미사용"

    # 2) openpyxl 폴백
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path)
        ws = wb[sheet] if sheet else wb.active
        for addr, val in cells.items():
            ws[addr] = val
        wb.save(path)
        return json.dumps({"path": path, "engine": "openpyxl", "backup": backup,
                           "cells_set": len(cells), "com_error": com_err,
                           "message": "Excel 셀 편집 완료(openpyxl 폴백 — 차트 등 일부 객체는 유실될 수 있음)"},
                          ensure_ascii=False)
    except Exception as e2:
        return json.dumps({"error": f"COM/라이브러리 모두 실패: {com_err} | {e2}",
                           "backup": backup}, ensure_ascii=False)


def excel_get_range(path: str, cell_range: str, sheet: str = "") -> str:
    """Excel 워크북의 특정 범위 값을 읽습니다. 예: 'A1:C10'. COM 우선, openpyxl 폴백."""
    path = _abspath(path)
    err = _validate_ooxml(path)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)

    if _HAS_PYWIN32:
        try:
            excel = _get_excel()
            wb = excel.Workbooks.Open(path, ReadOnly=True)
            try:
                ws = wb.Worksheets(sheet) if sheet else wb.ActiveSheet
                val = ws.Range(cell_range).Value
                # COM은 2D 튜플 반환 → 리스트로 정규화
                if isinstance(val, tuple):
                    rows = [list(r) if isinstance(r, tuple) else [r] for r in val]
                else:
                    rows = [[val]]
            finally:
                wb.Close(SaveChanges=0)
            return json.dumps({"range": cell_range, "engine": "com", "values": rows},
                              ensure_ascii=False, default=str)
        except Exception:
            pass

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb[sheet] if sheet else wb.active
        rows = [[c.value for c in row] for row in ws[cell_range]]
        return json.dumps({"range": cell_range, "engine": "openpyxl", "values": rows},
                          ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def office_close() -> str:
    """열려있는 Word/Excel COM 세션을 종료합니다(좀비 프로세스 정리)."""
    if not _HAS_PYWIN32:
        return json.dumps({"message": "COM 세션 없음"}, ensure_ascii=False)
    _quit_apps()
    return json.dumps({"message": "Office COM 세션 종료 완료"}, ensure_ascii=False)


# ── MANIFEST ──────────────────────────────────────────────────

MANIFEST = [
    {
        "name": "word_edit_text",
        "label": "Word 찾아바꾸기",
        "schema": {
            "type": "function",
            "function": {
                "name": "word_edit_text",
                "description": (
                    "기존 Word(.docx) 문서에서 텍스트를 찾아 바꾸고 저장합니다(서식 보존). "
                    "설치된 Word(COM) 우선, 불가 시 python-docx 폴백. 편집 전 자동 백업(.bak). "
                    "기존 문서를 실제로 편집할 때 사용하세요(append_word/write_word는 추가/새작성용)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": ".docx 경로"},
                        "find": {"type": "string", "description": "찾을 텍스트"},
                        "replace": {"type": "string", "description": "바꿀 텍스트"},
                        "match_case": {"type": "boolean", "description": "대소문자 구분"},
                        "whole_word": {"type": "boolean", "description": "단어 단위 일치"},
                    },
                    "required": ["path", "find", "replace"],
                },
            },
        },
        "handler": lambda a: word_edit_text(a["path"], a["find"], a["replace"],
                                            a.get("match_case", False), a.get("whole_word", False)),
    },
    {
        "name": "word_export_pdf",
        "label": "Word→PDF 내보내기",
        "schema": {
            "type": "function",
            "function": {
                "name": "word_export_pdf",
                "description": "Word(.docx)를 PDF로 내보냅니다. 설치된 Word(COM) 필요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": ".docx 경로"},
                        "pdf_path": {"type": "string", "description": "출력 PDF 경로(생략 시 같은 이름)"},
                    },
                    "required": ["path"],
                },
            },
        },
        "handler": lambda a: word_export_pdf(a["path"], a.get("pdf_path", "")),
    },
    {
        "name": "word_accept_all_changes",
        "label": "Word 수정추적 수락",
        "schema": {
            "type": "function",
            "function": {
                "name": "word_accept_all_changes",
                "description": "Word 문서의 모든 수정추적(Track Changes)을 수락하고 저장합니다. 설치된 Word(COM) 필요.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": ".docx 경로"}},
                    "required": ["path"],
                },
            },
        },
        "handler": lambda a: word_accept_all_changes(a["path"]),
    },
    {
        "name": "word_add_comment",
        "label": "Word 메모 작성",
        "schema": {
            "type": "function",
            "function": {
                "name": "word_add_comment",
                "description": "Word 문서에서 특정 텍스트(anchor_text)에 검토 메모를 추가합니다. 설치된 Word(COM) 필요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": ".docx 경로"},
                        "anchor_text": {"type": "string", "description": "메모를 달 기준 텍스트"},
                        "comment": {"type": "string", "description": "메모 내용"},
                    },
                    "required": ["path", "anchor_text", "comment"],
                },
            },
        },
        "handler": lambda a: word_add_comment(a["path"], a["anchor_text"], a["comment"]),
    },
    {
        "name": "excel_set_cells",
        "label": "Excel 셀 편집",
        "schema": {
            "type": "function",
            "function": {
                "name": "excel_set_cells",
                "description": (
                    "기존 Excel(.xlsx) 워크북의 특정 셀들에 값/수식을 설정하고 저장합니다. "
                    "cells 예: {\"B2\": \"=A1+A2\", \"C3\": \"합계\"}. "
                    "설치된 Excel(COM) 우선(수식 재계산·서식 보존), 불가 시 openpyxl 폴백. 편집 전 자동 백업."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": ".xlsx 경로"},
                        "cells": {"type": "object", "description": "{셀주소: 값/수식} 객체"},
                        "sheet": {"type": "string", "description": "시트 이름(생략 시 활성 시트)"},
                    },
                    "required": ["path", "cells"],
                },
            },
        },
        "handler": lambda a: excel_set_cells(a["path"], a["cells"], a.get("sheet", "")),
    },
    {
        "name": "excel_get_range",
        "label": "Excel 범위 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "excel_get_range",
                "description": "Excel 워크북의 특정 범위(예 'A1:C10') 값을 읽습니다. COM 우선, openpyxl 폴백.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": ".xlsx 경로"},
                        "cell_range": {"type": "string", "description": "예: 'A1:C10'"},
                        "sheet": {"type": "string", "description": "시트 이름(생략 시 활성 시트)"},
                    },
                    "required": ["path", "cell_range"],
                },
            },
        },
        "handler": lambda a: excel_get_range(a["path"], a["cell_range"], a.get("sheet", "")),
    },
    {
        "name": "office_close",
        "label": "Office 세션 종료",
        "schema": {
            "type": "function",
            "function": {
                "name": "office_close",
                "description": "열려있는 Word/Excel COM 세션을 종료합니다(좀비 프로세스 정리). 편집 작업을 모두 마친 뒤 호출하세요.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        "handler": lambda a: office_close(),
    },
]

# 모든 Office 핸들러를 전용 COM(STA) 스레드로 위임 — 단일 스레드 직렬화로 COM 안정성 확보
for _tool in MANIFEST:
    _tool["handler"] = _on_com_thread(_tool["handler"])
