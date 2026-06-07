"""
문서 처리 도구
- Excel: openpyxl (읽기/쓰기/행 추가/셀 메모)
- Word: python-docx (읽기/내용 추가) + OpenXML (검토 메모/수정 추적)
- PDF: pdfplumber (텍스트 추출, 읽기 전용)
- PowerPoint: OpenXML (슬라이드 텍스트/발표자 노트)
- 텍스트 파일: 내장 (읽기/쓰기/추가)
"""

import json
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


# ── Excel ─────────────────────────────────────────────────────

def read_excel(path: str, sheet: int = 0, max_rows: int = 200) -> str:
    """Excel 파일을 읽어 JSON 배열로 반환합니다.
    sheet는 시트 번호(0부터) 또는 시트 이름입니다.
    첫 행이 헤더로 사용됩니다."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if isinstance(sheet, int):
            ws = wb.worksheets[sheet]
        else:
            ws = wb[sheet]

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return json.dumps({"sheet": ws.title, "rows": [], "count": 0})

        headers = [str(c) if c is not None else f"col{i}" for i, c in enumerate(rows[0])]
        data = []
        for row in rows[1:max_rows + 1]:
            record = {headers[i]: (str(v) if v is not None else "") for i, v in enumerate(row)}
            data.append(record)
        return json.dumps({"sheet": ws.title, "rows": data, "count": len(data),
                           "headers": headers}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def write_excel(path: str, data: list, sheet_name: str = "Sheet1") -> str:
    """데이터를 Excel 파일로 저장합니다.
    data는 딕셔너리 리스트이며, 키가 헤더가 됩니다."""
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        if not data:
            wb.save(path)
            return json.dumps({"path": path, "rows": 0})

        headers = list(data[0].keys())
        ws.append(headers)
        for row in data:
            ws.append([row.get(h, "") for h in headers])

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        return json.dumps({"path": path, "rows": len(data), "headers": headers})
    except Exception as e:
        return json.dumps({"error": str(e)})


def append_excel_row(path: str, row_data: dict, sheet: int = 0) -> str:
    """Excel 파일의 마지막 행에 데이터를 추가합니다.
    파일이 없으면 새로 생성합니다."""
    try:
        import openpyxl
        if Path(path).exists():
            wb = openpyxl.load_workbook(path)
            ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
            max_row = ws.max_row
            if max_row == 1:
                # 헤더만 있거나 빈 경우
                headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
                ws.append([row_data.get(str(h), "") for h in headers])
            else:
                headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
                ws.append([row_data.get(str(h), "") for h in headers])
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(list(row_data.keys()))
            ws.append(list(row_data.values()))

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        return json.dumps({"path": path, "added_row": row_data,
                           "total_rows": ws.max_row - 1})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_excel_sheet_names(path: str) -> str:
    """Excel 파일의 시트 목록을 반환합니다."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        return json.dumps({"sheets": wb.sheetnames})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Word ──────────────────────────────────────────────────────

def read_word(path: str) -> str:
    """Word(.docx) 파일의 텍스트를 읽어 반환합니다."""
    try:
        import docx
        doc = docx.Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # 표 내용도 추출
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    paragraphs.append(" | ".join(row_texts))
        return "\n".join(paragraphs) or "(내용 없음)"
    except Exception as e:
        return f"Word 읽기 실패: {e}"


def append_word(path: str, text: str, heading: str = "") -> str:
    """Word 파일에 내용을 추가합니다.
    heading이 있으면 제목 단락을 먼저 추가합니다. 파일이 없으면 새로 생성합니다."""
    try:
        import docx
        if Path(path).exists():
            doc = docx.Document(path)
        else:
            doc = docx.Document()
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        if heading:
            doc.add_heading(heading, level=2)
        doc.add_paragraph(text)
        doc.save(path)
        return json.dumps({"path": path, "appended": text[:80]})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── PDF ───────────────────────────────────────────────────────

def read_pdf(path: str, pages: str = "") -> str:
    """PDF 파일에서 텍스트를 추출합니다.
    pages 예시: '1', '1-3', '2,4,6' (1부터 시작). 생략하면 전체."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            # 페이지 파싱
            if pages:
                page_nums = _parse_page_range(pages, total)
            else:
                page_nums = list(range(total))

            texts = []
            for i in page_nums:
                if 0 <= i < total:
                    page_text = pdf.pages[i].extract_text() or ""
                    texts.append(f"=== 페이지 {i+1} ===\n{page_text}")

            return "\n\n".join(texts) or "(추출된 텍스트 없음)"
    except Exception as e:
        return f"PDF 읽기 실패: {e}"


def _parse_page_range(pages: str, total: int) -> list:
    result = []
    for part in pages.replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            result.extend(range(int(a) - 1, min(int(b), total)))
        else:
            result.append(int(part) - 1)
    return result


# ── Office 검토/메모 (OpenXML) ────────────────────────────────

def read_word_comments(path: str) -> str:
    """Word(.docx) 파일의 검토 메모(Comments)를 읽어 반환합니다.
    작성자·날짜·내용을 포함합니다."""
    try:
        with zipfile.ZipFile(path) as z:
            if 'word/comments.xml' not in z.namelist():
                return json.dumps({'comments': [], 'count': 0})
            ns = {'w': _W}
            root = ET.parse(z.open('word/comments.xml')).getroot()
            comments = []
            for c in root.findall('w:comment', ns):
                texts = [t.text for t in c.findall('.//w:t', ns) if t.text]
                comments.append({
                    'id': c.get(f'{{{_W}}}id'),
                    'author': c.get(f'{{{_W}}}author', ''),
                    'date': (c.get(f'{{{_W}}}date', '') or '')[:10],
                    'text': ''.join(texts)
                })
            return json.dumps({'comments': comments, 'count': len(comments)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)})


def read_word_track_changes(path: str) -> str:
    """Word(.docx) 파일의 수정 추적(Track Changes) 삽입·삭제 내역을 반환합니다."""
    try:
        with zipfile.ZipFile(path) as z:
            if 'word/document.xml' not in z.namelist():
                return json.dumps({'error': '문서 파일 없음'})
            ns = {'w': _W}
            root = ET.parse(z.open('word/document.xml')).getroot()
            changes = []
            for ins in root.findall('.//w:ins', ns):
                texts = [t.text for t in ins.findall('.//w:t', ns) if t.text]
                changes.append({
                    'type': '삽입',
                    'author': ins.get(f'{{{_W}}}author', ''),
                    'date': (ins.get(f'{{{_W}}}date', '') or '')[:10],
                    'text': ''.join(texts)
                })
            for d in root.findall('.//w:del', ns):
                texts = [t.text for t in d.findall('.//w:delText', ns) if t.text]
                changes.append({
                    'type': '삭제',
                    'author': d.get(f'{{{_W}}}author', ''),
                    'date': (d.get(f'{{{_W}}}date', '') or '')[:10],
                    'text': ''.join(texts)
                })
            return json.dumps({'track_changes': changes, 'count': len(changes)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)})


def read_excel_comments(path: str, sheet: str = '') -> str:
    """Excel(.xlsx) 파일의 셀 메모(Comments)를 읽어 반환합니다."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path)
        sheets_to_check = [wb[sheet]] if sheet and sheet in wb.sheetnames else wb.worksheets
        results = {}
        for ws in sheets_to_check:
            comments = []
            for row in ws.iter_rows():
                for cell in row:
                    if cell.comment:
                        comments.append({
                            'cell': cell.coordinate,
                            'author': cell.comment.author or '',
                            'text': cell.comment.text or ''
                        })
            if comments:
                results[ws.title] = comments
        total = sum(len(v) for v in results.values())
        return json.dumps({'sheets': results, 'total_comments': total}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)})


def read_ppt_content(path: str) -> str:
    """PowerPoint(.pptx) 파일의 슬라이드 텍스트와 발표자 노트를 읽어 반환합니다."""
    try:
        ns = {'a': _A}
        with zipfile.ZipFile(path) as z:
            namelist = z.namelist()
            slide_files = sorted(
                [f for f in namelist if f.startswith('ppt/slides/slide') and f.endswith('.xml')]
            )
            slides = []
            for i, sf in enumerate(slide_files):
                root = ET.parse(z.open(sf)).getroot()
                texts = [t.text.strip() for t in root.findall('.//a:t', ns)
                         if t.text and t.text.strip()]
                num = os.path.basename(sf).replace('slide', '').replace('.xml', '')
                nf = f'ppt/notesSlides/notesSlide{num}.xml'
                notes_text = ''
                if nf in namelist:
                    nr = ET.parse(z.open(nf)).getroot()
                    notes_text = ' '.join(
                        t.text.strip() for t in nr.findall('.//a:t', ns)
                        if t.text and t.text.strip()
                    )
                slides.append({'slide': i + 1, 'content': texts, 'notes': notes_text})
            return json.dumps({'slides': slides, 'total_slides': len(slides)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e)})


# ── 텍스트 파일 ───────────────────────────────────────────────

def read_file(path: str, encoding: str = "utf-8") -> str:
    """텍스트 파일을 읽어 내용을 반환합니다.
    로그 파일, 설정 파일, CSV 등에 사용합니다."""
    try:
        content = Path(path).read_text(encoding=encoding, errors="replace")
        lines = content.splitlines()
        if len(lines) > 500:
            return "\n".join(lines[:500]) + f"\n... (이하 {len(lines)-500}줄 생략)"
        return content or "(빈 파일)"
    except Exception as e:
        return f"파일 읽기 실패: {e}"


def write_file(path: str, content: str, append: bool = False,
               encoding: str = "utf-8") -> str:
    """텍스트 파일에 내용을 씁니다.
    append=True 시 기존 내용 뒤에 추가합니다."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with p.open(mode, encoding=encoding) as f:
            f.write(content)
        return json.dumps({"path": path, "size_bytes": p.stat().st_size,
                           "mode": "append" if append else "write"})
    except Exception as e:
        return json.dumps({"error": str(e)})


MANIFEST = [
    {
        "name": "get_excel_sheet_names",
        "label": "Excel 시트 목록",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_excel_sheet_names",
                "description": "Excel 파일의 시트 이름 목록을 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: get_excel_sheet_names(a["path"])
    },
    {
        "name": "read_excel",
        "label": "Excel 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_excel",
                "description": "Excel 파일을 읽어 JSON 데이터로 반환합니다. 첫 행이 헤더입니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "sheet": {"description": "시트 번호(0부터) 또는 시트 이름"},
                        "max_rows": {"type": "integer", "description": "최대 행 수 (기본 200)"}
                    },
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_excel(a["path"], a.get("sheet", 0), a.get("max_rows", 200))
    },
    {
        "name": "write_excel",
        "label": "Excel 쓰기",
        "schema": {
            "type": "function",
            "function": {
                "name": "write_excel",
                "description": "딕셔너리 리스트를 Excel 파일로 저장합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "data": {"type": "array", "items": {"type": "object"}},
                        "sheet_name": {"type": "string"}
                    },
                    "required": ["path", "data"]
                }
            }
        },
        "handler": lambda a: write_excel(a["path"], a["data"], a.get("sheet_name", "Sheet1"))
    },
    {
        "name": "append_excel_row",
        "label": "Excel 행 추가",
        "schema": {
            "type": "function",
            "function": {
                "name": "append_excel_row",
                "description": "Excel 파일의 마지막에 행을 추가합니다. 파일이 없으면 새로 생성합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "row_data": {"type": "object", "description": "헤더: 값 딕셔너리"}
                    },
                    "required": ["path", "row_data"]
                }
            }
        },
        "handler": lambda a: append_excel_row(a["path"], a["row_data"], a.get("sheet", 0))
    },
    {
        "name": "read_word",
        "label": "Word 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_word",
                "description": "Word(.docx) 파일의 텍스트를 추출합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_word(a["path"])
    },
    {
        "name": "append_word",
        "label": "Word 내용 추가",
        "schema": {
            "type": "function",
            "function": {
                "name": "append_word",
                "description": "Word 파일에 내용을 추가합니다. 파일이 없으면 새로 생성합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "text": {"type": "string"},
                        "heading": {"type": "string", "description": "섹션 제목 (선택)"}
                    },
                    "required": ["path", "text"]
                }
            }
        },
        "handler": lambda a: append_word(a["path"], a["text"], a.get("heading", ""))
    },
    {
        "name": "read_pdf",
        "label": "PDF 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_pdf",
                "description": "PDF 파일에서 텍스트를 추출합니다. pages 예: '1', '1-3', '2,4'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "pages": {"type": "string", "description": "페이지 범위 (생략 시 전체)"}
                    },
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_pdf(a["path"], a.get("pages", ""))
    },
    {
        "name": "read_file",
        "label": "파일 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "텍스트 파일을 읽어 내용을 반환합니다. 로그, 설정 파일, CSV 등에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_file(a["path"])
    },
    {
        "name": "write_file",
        "label": "파일 쓰기",
        "schema": {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "텍스트 파일에 내용을 씁니다. append=true 시 기존 내용 뒤에 추가합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "append": {"type": "boolean"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        "handler": lambda a: write_file(a["path"], a["content"], a.get("append", False))
    },
    {
        "name": "read_word_comments",
        "label": "Word 검토 메모",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_word_comments",
                "description": "Word(.docx) 파일의 검토 메모(Comments)를 읽어 반환합니다. 작성자·날짜·내용 포함.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": ".docx 파일 경로"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_word_comments(a["path"])
    },
    {
        "name": "read_word_track_changes",
        "label": "Word 수정 추적",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_word_track_changes",
                "description": "Word(.docx) 파일의 수정 추적(Track Changes) 삽입·삭제 내역을 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": ".docx 파일 경로"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_word_track_changes(a["path"])
    },
    {
        "name": "read_excel_comments",
        "label": "Excel 셀 메모",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_excel_comments",
                "description": "Excel(.xlsx) 파일의 셀 메모(Comments)를 읽어 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": ".xlsx 파일 경로"},
                        "sheet": {"type": "string", "description": "시트 이름 (생략 시 전체)"}
                    },
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_excel_comments(a["path"], a.get("sheet", ""))
    },
    {
        "name": "read_ppt_content",
        "label": "PPT 슬라이드 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "read_ppt_content",
                "description": "PowerPoint(.pptx) 파일의 슬라이드 텍스트와 발표자 노트를 읽어 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": ".pptx 파일 경로"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: read_ppt_content(a["path"])
    },
]
