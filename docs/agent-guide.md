# Agent 개발 가이드

## ⚡ 툴 구현 후 필수 업데이트 체크리스트

새 툴을 추가하거나 기존 기능을 수정할 때마다 아래를 확인한다.

```
□ agent/tools/<name>.py       — 툴 함수 작성
□ agent/tools/__init__.py     — TOOLS 스키마, TOOL_LABELS, _TOOL_MAP 등록
□ CLAUDE.md                   — 현재 상태 표의 해당 항목 ✅ 변경
□ README.md                   — 기능 현황 표 상태 업데이트
□ electron/renderer/index.html — (워크플로우인 경우) 사이드바 버튼 추가
□ docs/agent-guide.md         — 아래 "구현된 툴 목록" 업데이트
```

---

## 구현된 툴 목록 (현재)

| 툴 이름 | 파일 | 기능 | 상태 |
|---------|------|------|------|
| `capture_screen_ocr` | `ocr.py` | 전체 화면 캡처 + OCR 텍스트 추출 | ✅ |
| `mouse_click` | `desktop.py` | 좌표 클릭 (left/right/double) | ✅ |
| `mouse_move` | `desktop.py` | 마우스 이동 | ✅ |
| `type_text` | `desktop.py` | 텍스트 입력 | ✅ |
| `key_press` | `desktop.py` | 키/단축키 입력 (예: `ctrl+c`) | ✅ |
| `focus_window` | `desktop.py` | 창 제목으로 포커스 | ✅ |
| `get_mouse_position` | `desktop.py` | 현재 마우스 좌표 반환 | ✅ |
| `add_dev_note` | `obsidian_session.py` | Obsidian에 개발 노트 저장 | ✅ |
| `add_plan_item` | `obsidian_session.py` | Obsidian 백로그에 할 일 추가 | ✅ |
| `list_recent_sessions` | `obsidian_session.py` | 최근 업무 세션 목록 조회 | ✅ |
| `search_sessions` | `obsidian_session.py` | 세션 내용 키워드 검색 | ✅ |
| `read_excel` | `excel.py` | Excel 파일 읽기 | 🚧 개발 예정 |
| `write_excel` | `excel.py` | Excel 셀 쓰기 | 🚧 개발 예정 |
| `read_word` | `word.py` | Word 문서 읽기 | 🚧 개발 예정 |
| `extract_pdf` | `pdf.py` | PDF 표/텍스트 추출 | 🚧 개발 예정 |
| `open_browser` | `web_action.py` | Playwright 브라우저 열기 | 🚧 개발 예정 |
| `click_selector` | `web_action.py` | CSS 셀렉터 클릭 | 🚧 개발 예정 |
| `fill_input` | `web_action.py` | 입력 필드 채우기 | 🚧 개발 예정 |
| `analyze_screen` | `vision.py` | 화면 이미지 → LLM 비전 분석 | 🚧 개발 예정 |

---

## 구조 개요

```
agent/
├── server.py            — FastAPI 라우터 (건드릴 일 거의 없음)
├── llm.py               — LLM 클라이언트 팩토리
├── config.py            — LLM 프로파일 (openai / internal)
├── obsidian_session.py  — Obsidian 세션·노트·계획 관리
└── tools/
    ├── __init__.py      — 툴 레지스트리 ← 새 툴 등록 여기
    ├── ocr.py           — 화면 OCR
    ├── desktop.py       — 마우스/키보드 제어
    ├── excel.py         — (예정) Excel 읽기·쓰기
    ├── web_action.py    — (예정) Playwright 웹 자동화
    └── ...              — 추가 툴 여기에
```

---

## 새 툴 추가하는 법

### 1. 툴 함수 작성

`agent/tools/` 아래에 파일을 만들고 함수를 작성합니다.

```python
# agent/tools/excel.py
import openpyxl

def read_excel(path: str, sheet: str = None) -> str:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[sheet] if sheet else wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append("\t".join(str(c) if c is not None else "" for c in row))
    return "\n".join(rows)
```

**규칙:**
- 반환값은 항상 `str` (LLM과 UI에 그대로 노출됨)
- 예외는 caller에게 전파 — `__init__.py`에서 잡아 오류 문자열로 변환
- 긴 결과는 적절히 잘라서 반환 (LLM 컨텍스트 절약)

### 2. `__init__.py`에 등록

```python
# agent/tools/__init__.py

from agent.tools.excel import read_excel   # ← import 추가

# TOOLS 리스트에 스키마 추가
TOOLS = [
    ...
    {
        "type": "function",
        "function": {
            "name": "read_excel",
            "description": "엑셀 파일을 읽어 내용을 텍스트로 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "엑셀 파일 경로"},
                    "sheet": {"type": "string", "description": "시트 이름 (생략 시 첫 번째 시트)"}
                },
                "required": ["path"]
            }
        }
    },
]

# TOOL_LABELS에 표시명 추가 (채팅창 툴 진행 단계에 보임)
TOOL_LABELS = {
    ...
    "read_excel": "Excel 파일 읽기",
}

# _TOOL_MAP에 실행 함수 연결
_TOOL_MAP = {
    ...
    "read_excel": lambda args: read_excel(args["path"], args.get("sheet")),
}
```

이걸로 끝입니다. 서버 재시작 후 LLM이 자동으로 툴을 사용합니다.

---

## 업무 워크플로우 추가

여러 툴을 조합하는 복잡한 업무는 별도 모듈로 분리하는 것을 권장합니다.

```
agent/
└── workflows/
    ├── __init__.py
    ├── syncade_deploy.py   — Syncade 배포 워크플로우
    └── knox_collect.py     — Knox 자동 수집 워크플로우
```

워크플로우 함수도 툴로 등록하면 LLM이 한 번에 호출할 수 있습니다.

---

## LLM 프로파일

`agent/config.py`에서 OpenAI 호환 엔드포인트를 관리합니다.

```python
# 현재 프로파일 확인
from agent.config import get_active, active_llm
print(get_active())      # 'openai' 또는 'internal'
print(active_llm())      # {'base_url': ..., 'model': ..., 'api_key': ...}
```

사내 LLM은 `.env`에서:
```ini
LLM_INTERNAL_BASE_URL=http://192.168.x.x:8000/v1
LLM_INTERNAL_MODEL=your-model-name
INTERNAL_API_KEY=your-key
```

UI 우측 상단 버튼으로 런타임 전환 가능합니다.

---

## 스트리밍 이벤트 형식

`agent/server.py`의 `generate()` 함수가 SSE로 아래 이벤트를 전송합니다.

```
data: {"type": "text", "content": "..."}           — LLM 텍스트 토큰
data: {"type": "tool_start", "tool": "...", "label": "..."}  — 툴 실행 시작
data: {"type": "tool_done",  "tool": "...", "result": "..."}  — 툴 실행 완료
data: {"type": "done"}                             — 전체 완료
data: {"type": "error", "message": "..."}          — 오류
```

프론트엔드 `chat.js`의 `handleEvent()`가 이를 받아 UI에 반영합니다.

---

## 도구 테스트

저수준 툴 동작 확인은 직접 Python 실행으로 빠르게 테스트할 수 있습니다:

```powershell
# conda 환경에서
conda activate mes-agent
cd D:\GithubRepositories\mes-agent

python -c "from agent.tools.desktop import get_mouse_position; print(get_mouse_position())"
python -c "from agent.tools.ocr import capture_screen_ocr; print(capture_screen_ocr()[:200])"
```

또는 채팅창에서 직접 "현재 마우스 위치 알려줘" 처럼 자연어로 테스트할 수 있습니다.
