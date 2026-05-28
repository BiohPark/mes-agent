# Agent 개발 가이드

## ⚡ 툴 구현 후 필수 업데이트 체크리스트

새 툴을 추가하거나 기존 기능을 수정할 때마다 아래를 확인한다.

```
□ agent/tools/<name>.py        — 툴 함수 작성 + MANIFEST 정의 (이것만으로 자동 등록)
□ CLAUDE.md                    — 현재 상태 표의 해당 항목 ✅ 변경
□ README.md                    — 기능 현황 표 상태 업데이트
□ electron/renderer/index.html — (워크플로우인 경우) 사이드바 버튼 추가
□ docs/agent-guide.md          — 아래 "구현된 툴 목록" 업데이트
```

> **__init__.py는 수정하지 않아도 된다.** MANIFEST가 있는 파일을 tools/ 폴더에 넣으면 서버 시작 시 자동 등록된다.

---

## 구현된 툴 목록 (70종)

### 화면 인식 (10종)

| 툴 이름 | 파일 | 기능 |
|---------|------|------|
| `capture_screen_ocr` | `ocr.py` | 전체 화면 OCR |
| `capture_region_ocr` | `screen.py` | 지정 영역 OCR (더 정확) |
| `find_image_on_screen` | `screen.py` | OpenCV 템플릿 매칭 → 좌표 반환 |
| `find_text_location` | `screen.py` | OCR로 텍스트 위치(좌표) 탐색 |
| `wait_for_image` | `screen.py` | 이미지 나타날 때까지 대기 |
| `wait_for_text` | `screen.py` | 텍스트 나타날 때까지 대기 |
| `compare_screenshots` | `screen.py` | 두 스크린샷 비교 → 변화율 |
| `save_screenshot` | `screen.py` | 전체 화면 파일 저장 |
| `get_pixel_color` | `screen.py` | 픽셀 RGB/HEX 색상 반환 |
| `capture_window_screenshot` | `screen.py` | 특정 창만 캡처 |

### 마우스/키보드 제어 (18종)

| 툴 이름 | 파일 | 기능 |
|---------|------|------|
| `mouse_click` | `desktop.py` | 좌표 클릭 (`use_sendinput=true`로 UAC 앱 대응) |
| `mouse_move` | `desktop.py` | 마우스 이동 |
| `mouse_scroll` | `desktop.py` | 휠 스크롤 (up/down, amount 지정) |
| `mouse_drag` | `desktop.py` | 드래그 앤 드롭 |
| `mouse_down` | `desktop.py` | 버튼 누름 유지 |
| `mouse_up` | `desktop.py` | 버튼 해제 |
| `get_mouse_position` | `desktop.py` | 현재 좌표 반환 |
| `key_press` | `desktop.py` | 키/단축키 (`use_sendinput=true`로 UAC 앱 대응) |
| `key_down` | `desktop.py` | 키 누름 유지 (pynput) |
| `key_up` | `desktop.py` | 키 해제 (pynput) |
| `type_text` | `desktop.py` | 영문/숫자 입력 |
| `type_text_clipboard` | `desktop.py` | 클립보드 경유 입력 (한글·특수문자) |
| `clipboard_get` | `desktop.py` | 클립보드 읽기 |
| `clipboard_set` | `desktop.py` | 클립보드에 복사 |
| `focus_window` | `desktop.py` | 창 제목으로 포커스 |
| `list_windows` | `desktop.py` | 열린 창 목록 + 위치/크기 |
| `resize_window` | `desktop.py` | 창 크기 변경 |
| `move_window` | `desktop.py` | 창 위치 변경 |

### 브라우저 자동화 (20종, Playwright)

> **사전 조건**: `python -m playwright install chromium` 실행 필요 (최초 1회)

| 툴 이름 | 기능 |
|---------|------|
| `browser_open(url)` | 브라우저 열기 (세션 재사용) |
| `browser_navigate(url)` | URL 이동 |
| `browser_get_url()` | 현재 URL |
| `browser_get_title()` | 페이지 제목 |
| `browser_click(selector)` | CSS/XPath 클릭 |
| `browser_fill(selector, text)` | 입력창 채우기 |
| `browser_type(selector, text)` | 한 글자씩 타이핑 (자동완성용) |
| `browser_select(selector, value)` | 드롭다운 선택 |
| `browser_get_text(selector)` | 요소 텍스트 추출 |
| `browser_get_page_text()` | 페이지 전체 텍스트 |
| `browser_get_attribute(selector, attr)` | 요소 속성값 |
| `browser_wait_for(selector, state)` | 요소 대기 (visible/hidden/...) |
| `browser_wait_for_url(pattern)` | URL 변경 대기 |
| `browser_wait_for_network_idle()` | 네트워크 완료 대기 |
| `browser_screenshot(path)` | 페이지 전체 스크린샷 |
| `browser_execute_js(script)` | JS 직접 실행 |
| `browser_handle_dialog(action)` | alert/confirm 자동 처리 |
| `browser_upload_file(selector, path)` | 파일 업로드 |
| `browser_get_cookies()` | 쿠키 조회 |
| `browser_close()` | 브라우저 종료 |

### 프로세스/시스템 (9종)

| 툴 이름 | 기능 |
|---------|------|
| `run_command(cmd, shell)` | PowerShell/CMD 실행 → stdout/stderr/returncode |
| `list_processes(filter)` | 실행 중 프로세스 목록 (psutil) |
| `kill_process(name_or_pid)` | 프로세스 종료 |
| `is_process_running(name)` | 실행 여부 확인 |
| `start_process(cmd, wait)` | 프로세스 시작 |
| `open_file(path)` | 연결 앱으로 파일 열기 |
| `list_directory(path)` | 폴더 내용 조회 |
| `file_exists(path)` | 파일 존재 여부 |
| `get_system_info()` | CPU·메모리·디스크 사용량 |

### 문서 처리 (9종)

| 툴 이름 | 기능 |
|---------|------|
| `read_excel(path, sheet)` | Excel → JSON (헤더 자동 추출) |
| `write_excel(path, data)` | JSON → Excel 파일 저장 |
| `append_excel_row(path, row)` | Excel 마지막 행 추가 |
| `get_excel_sheet_names(path)` | 시트 목록 |
| `read_word(path)` | Word 텍스트 추출 |
| `append_word(path, text)` | Word 내용 추가 |
| `read_pdf(path, pages)` | PDF 텍스트 추출 |
| `read_file(path)` | 텍스트 파일 읽기 |
| `write_file(path, content, append)` | 텍스트 파일 쓰기/추가 |

### Obsidian 세션 (4종)

| 툴 이름 | 기능 |
|---------|------|
| `add_dev_note` | Vault에 개발 노트 저장 |
| `add_plan_item` | 백로그에 할 일 추가 |
| `list_recent_sessions` | 최근 세션 목록 |
| `search_sessions` | 세션 키워드 검색 |

---

## 구조 개요

```
agent/
├── server.py            — FastAPI 라우터
├── llm.py               — LLM 클라이언트 팩토리
├── config.py            — LLM 프로파일 (openai / internal)
├── obsidian_session.py  — Obsidian 세션·노트·스레드 관리 + MANIFEST(4종)
└── tools/
    ├── __init__.py      — 자동 디스커버리 레지스트리 (수정 불필요)
    ├── ocr.py           — 전체화면 OCR + MANIFEST(1종)
    ├── desktop.py       — 마우스·키보드·클립보드·창 + MANIFEST(18종)
    ├── screen.py        — 화면 인텔리전스 (OpenCV + mss + pytesseract) + MANIFEST(9종)
    ├── browser.py       — 브라우저 자동화 (Playwright) + MANIFEST(20종)
    ├── process.py       — 프로세스·시스템 (psutil + subprocess) + MANIFEST(9종)
    └── document.py      — Excel·Word·PDF·텍스트 + MANIFEST(9종)
```

---

## 새 툴 추가하는 법

### 1. 툴 함수 + MANIFEST 작성 (이것만으로 끝)

```python
# agent/tools/mymodule.py

def my_tool(param: str) -> str:
    # 반환값은 항상 str (LLM과 UI에 노출됨)
    return f"결과: {param}"


MANIFEST = [
    {
        "name": "my_tool",
        "label": "나의 툴",          # UI 표시명
        "schema": {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "무엇을 하는 툴인지 LLM이 이해할 수 있도록 설명.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "description": "파라미터 설명"}
                    },
                    "required": ["param"]
                }
            }
        },
        "handler": lambda a: my_tool(a["param"])
    }
]
```

파일을 `agent/tools/` 에 저장하면 서버 시작 시 자동 등록된다. `__init__.py`는 건드리지 않는다.

**코딩 규칙:**
- 반환값은 항상 `str`
- JSON 반환 시 `json.dumps(..., ensure_ascii=False)` 사용
- 예외는 caller에게 전파 — 레지스트리에서 잡아 오류 문자열로 변환
- 긴 결과는 적절히 잘라서 반환 (LLM 컨텍스트 절약)

---

## 핵심 자동화 패턴

### 화면에서 텍스트 찾아서 클릭
```
1. find_text_location("저장") → {"found": true, "x": 450, "y": 300}
2. mouse_click(450, 300)
```

### 작업 완료까지 대기
```
1. (배포 시작)
2. wait_for_text("배포 완료", timeout=60) → {"found": true, "elapsed_sec": 23}
3. save_screenshot("deploy_result.png")
```

### 브라우저 로그인 자동화
```
1. browser_open("http://intranet/login")
2. browser_fill("#username", "user01")
3. browser_fill("#password", "pass")
4. browser_click("#login-btn")
5. browser_wait_for_url("/dashboard", timeout=5000)
6. browser_get_page_text()  → 대시보드 내용 추출
```

### UAC/관리자 앱 제어
```
mouse_click(x, y, use_sendinput=True)
key_press("ctrl+s", use_sendinput=True)
```

---

## LLM 프로파일

`agent/config.py`에서 OpenAI 호환 엔드포인트를 관리합니다.

```python
from agent.config import get_active, active_llm
print(get_active())   # 'openai' 또는 'internal'
print(active_llm())   # {'base_url': ..., 'model': ..., 'api_key': ...}
```

사내 LLM `.env` 설정:
```ini
LLM_INTERNAL_BASE_URL=http://192.168.x.x:8000/v1
LLM_INTERNAL_MODEL=your-model-name
INTERNAL_API_KEY=your-key
```

---

## 스트리밍 이벤트 형식

```
data: {"type": "text",       "content": "..."}
data: {"type": "tool_start", "tool": "...", "label": "..."}
data: {"type": "tool_done",  "tool": "...", "result": "..."}
data: {"type": "done"}
data: {"type": "error",      "message": "..."}
```

---

## 빠른 테스트

```powershell
conda activate mes-agent
cd D:\GithubRepositories\mes-agent

# 개별 툴 직접 테스트
python -c "from agent.tools.desktop import get_mouse_position; print(get_mouse_position())"
python -c "from agent.tools.screen import get_pixel_color; print(get_pixel_color(100,100))"
python -c "from agent.tools.process import get_system_info; print(get_system_info())"

# 브라우저 툴 (Chromium 창 뜸)
python -c "from agent.tools.browser import browser_open, browser_close; print(browser_open('https://google.com')); browser_close()"

# 툴 레지스트리 카운트 확인
python -c "from agent.tools import TOOLS, TOOL_LABELS; print(f'TOOLS:{len(TOOLS)} LABELS:{len(TOOL_LABELS)}')"
```
