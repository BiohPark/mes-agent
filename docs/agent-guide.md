# Agent 개발 가이드

## ⚡ 툴 구현 후 필수 업데이트 체크리스트

새 툴을 추가하거나 기존 기능을 수정할 때마다 아래를 확인한다.

```
□ agent/tools/<name>.py        — 툴 함수 작성 + MANIFEST 정의 (이것만으로 자동 등록)
□ CLAUDE.md                    — 현재 상태 표의 해당 항목 ✅ 변경, 툴 수 업데이트
□ README.md                    — 기능 현황 표 상태 업데이트
□ docs/agent-guide.md          — 아래 "구현된 툴 목록" 업데이트
```

> **`__init__.py`는 수정하지 않아도 된다.** MANIFEST가 있는 파일을 `tools/` 폴더에 넣으면 서버 시작 시 자동 등록된다.

---

## 구현된 툴 목록 (98종)

### 화면 인식 (10종)

| 툴 이름 | 파일 | 기능 |
|---------|------|------|
| `capture_screen_ocr` | `ocr.py` | 전체 화면 OCR → 텍스트 반환 |
| `capture_region_ocr` | `screen.py` | 지정 영역 OCR (좌표·크기 지정, 더 정확) |
| `find_image_on_screen` | `screen.py` | OpenCV 템플릿 매칭 → 좌표 반환 |
| `find_text_location` | `screen.py` | OCR로 텍스트 위치(좌표) 탐색 |
| `wait_for_image` | `screen.py` | 이미지 나타날 때까지 대기 (`interval`로 폴링 간격 지정, 기본 0.5s) |
| `wait_for_text` | `screen.py` | 텍스트 나타날 때까지 대기 (`interval`로 폴링 간격 지정, 기본 0.5s) |
| `compare_screenshots` | `screen.py` | 두 스크린샷 픽셀 비교 → 변화율 |
| `save_screenshot` | `screen.py` | 전체 화면 파일 저장 |
| `get_pixel_color` | `screen.py` | 픽셀 RGB/HEX 색상 반환 |
| `capture_window_screenshot` | `screen.py` | 특정 창만 캡처 |

### 마우스/키보드 제어 (19종)

| 툴 이름 | 파일 | 기능 |
|---------|------|------|
| `mouse_click` | `desktop.py` | 좌표 클릭 (`use_sendinput=true`로 UAC 앱 대응, `after_delay_ms`로 클릭 후 안정화 대기) |
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
| `maximize_window` | `desktop.py` | 창 최대화 |

### 브라우저 자동화 (22종, Playwright)

> **사전 조건**: `python -m playwright install chromium` 실행 필요 (최초 1회)
>
> **선택자 전략**: CSS id/class보다 `aria-label`, `placeholder`, `:has-text()` 기반 선택자를 우선 사용한다.  
> 새 페이지 진입 시 `browser_get_interactive_elements`로 실제 선택자를 먼저 확인한 후 클릭·입력해라.

| 툴 이름 | 기능 |
|---------|------|
| `browser_open(url)` | 브라우저 열기 (Chromium 싱글턴, 세션 재사용) |
| `browser_navigate(url)` | URL 이동 |
| `browser_get_url()` | 현재 URL |
| `browser_get_title()` | 페이지 제목 |
| `browser_get_interactive_elements()` | 현재 페이지의 입력·버튼 요소 목록 (선택자 확인용) ★ |
| `browser_click(selector)` | CSS/XPath 클릭 |
| `browser_fill(selector, text)` | 입력창 채우기 (기존 내용 대체) |
| `browser_type(selector, text, timeout)` | 한 글자씩 타이핑 (자동완성용, 기본 5초 대기) |
| `browser_press_key(key, selector)` | 키 입력 (Enter·Tab 등, 폼 제출에 사용) ★ |
| `browser_select(selector, value)` | 드롭다운 선택 |
| `browser_get_text(selector)` | 요소 텍스트 추출 |
| `browser_get_page_text()` | 페이지 전체 텍스트 |
| `browser_get_attribute(selector, attr)` | 요소 속성값 |
| `browser_wait_for(selector, state)` | 요소 대기 (visible/hidden/attached) |
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

### Obsidian PKM — Vault 탐색·편집·정리 (16종)

**환경 설정 (`.env`):**
```ini
OBSIDIAN_VAULT_PATH=D:/archive/obsidian/brain   # Vault 루트 경로
OBSIDIAN_HOST=https://127.0.0.1:27124           # Local REST API 주소
OBSIDIAN_API_KEY=발급받은-API-키                 # Obsidian 플러그인에서 발급
```

**접근 우선순위:** REST API (`OBSIDIAN_HOST`) → 직접 파일 (`OBSIDIAN_VAULT_PATH`) fallback

#### Tier 1 — 얕은 탐색 (토큰 절약)

| 툴 이름 | 기능 |
|---------|------|
| `obsidian_preview_note` | 첫 N줄 + 파일크기·프론트매터만 반환. 관련성 판단용 |
| `obsidian_scan_vault` | 여러 노트 배치 미리보기. `paths` 목록 또는 `folder` 지정 |
| `obsidian_get_backlinks` | 이 노트를 `[[링크]]`하는 노트 목록 |
| `obsidian_read_section` | 특정 헤딩 섹션만 읽기. 큰 노트에서 필요한 부분만 추출 |

#### Tier 2 — 깊은 읽기

| 툴 이름 | 기능 |
|---------|------|
| `obsidian_read_note` | 노트 전문 읽기 |
| `obsidian_list_notes` | 폴더 내 노트 목록 |
| `obsidian_get_tags` | 프론트매터·인라인 태그 조회 |
| `obsidian_follow_links` | `[[wikilink]]` BFS 다중 뎁스 스캔. `max_chars_per_note`로 비루트 노트 글자 수 제한 가능 |

#### 검색

| 툴 이름 | 기능 |
|---------|------|
| `obsidian_search` | 키워드 전체 검색 |
| `obsidian_search_advanced` | 태그 필터·폴더 범위·최근 수정순 정렬 지원 |

#### 쓰기·편집

| 툴 이름 | 기능 |
|---------|------|
| `obsidian_write_note` | 노트 생성/전체 덮어쓰기 |
| `obsidian_append_note` | 노트 끝에 내용 추가 |
| `obsidian_edit_note` | 특정 텍스트 교체 (중복 발견 시 오류 반환 — 안전장치) |
| `obsidian_replace_section` | 헤딩 섹션 내용 전체 교체 (헤딩 줄 보존) |
| `obsidian_update_frontmatter` | YAML 프론트매터 필드 upsert |

#### 정리·이동

| 툴 이름 | 기능 |
|---------|------|
| `obsidian_move_note` | 이동/이름 변경 + `[[wikilink]]` 자동 업데이트 |

#### 2-tier 탐색 패턴 (권장)

```
1. obsidian_search("키워드")
   → 관련 노트 경로 목록 확보

2. obsidian_scan_vault(paths=[...])
   → 크기·태그·첫 줄로 관련성 판단

3. (관련 있는 노트만) obsidian_read_note / obsidian_read_section
   → 토큰 절약

4. [[링크]] 네트워크 필요 시
   → obsidian_follow_links(max_chars_per_note=500)
```

#### `obsidian_follow_links` 상세

**지원 문법:**
```
[[노트 제목]]              — 기본 링크
[[노트 제목|표시 텍스트]]  — 별칭 링크
[[노트 제목#섹션]]         — 헤딩 링크 (섹션 기호 무시, 노트만 탐색)
```

**사용 예:**
```json
{ "path": "projects/Syncade.md", "depth": 2, "max_notes": 20, "max_chars_per_note": 500 }
```

> `depth` 권장값: 1~2. `max_chars_per_note` 기본 2000, 토큰 절약 시 500으로 줄여라.

### Obsidian 세션 (4종)

> 에이전트 작업 이력 전용 — `agent/` 폴더만 접근

| 툴 이름 | 기능 |
|---------|------|
| `add_dev_note` | `agent/notes/`에 개발 노트 저장 |
| `add_plan_item` | `agent/plans/backlog.md`에 할 일 추가 |
| `list_recent_sessions` | `agent/sessions/` 최근 세션 목록 |
| `search_sessions` | `agent/sessions/` 키워드 검색 |

### 사용자 확인 (1종)

| 툴 이름 | 기능 |
|---------|------|
| `ask_user` | 팝업 대화상자로 사용자 입력 요청 |

`ask_user`는 반환값으로 JSON을 출력하지 않는다. 서버가 `__confirm__` 플래그를 감지해 SSE `confirm` 이벤트를 발생시키고, 사용자 응답을 기다린 뒤 결과를 tool 메시지로 돌려준다.

**기본 선택지:** 계속 진행 / 중단 / 방법 변경 제안 / 의견 전달  
**타임아웃:** 300초 (5분) — 초과 시 자동 중단  
**사용 시점:** 중요한 비가역적 작업 직전 (파일 삭제, 배포 실행, 대량 입력 등)

### 워크플로우 (8종)

| 툴 이름 | 기능 |
|---------|------|
| `workflow_init` | 스레드 워크플로우 초기화 (단계 전체 정의/교체, 우측 패널에 표시) |
| `workflow_set_step` | 특정 단계의 **진행 상태** 업데이트 (pending/running/waiting/done/error/skipped). `branch_output=1/2`로 분기 경로 선택 |
| `workflow_add_step` | 단계 **추가** (기존 단계 상태 유지, `after_step_id`로 삽입 위치 지정 가능) |
| `workflow_update_step` | 단계의 **구조 수정** (제목·유형). 상태는 `set_step`이 담당 |
| `workflow_remove_step` | 단계 **삭제** |
| `workflow_reorder` | 단계 **순서 재배치** (`ordered_step_ids`에 원하는 순서대로 id 나열) |
| `workflow_add_connection` | 노드 간 연결 추가 (`from_output`: 0=기본, 1=true 분기, 2=false 분기) |
| `workflow_remove_connection` | 노드 간 연결 삭제 |

**단계 타입:**
- `auto` 🤖 — 에이전트가 자동 실행
- `semi_auto` 👁️ — 사용자 확인 후 실행
- `manual` ✋ — 사용자가 직접 수행

**런타임 라우팅:**  
`workflow_set_step(status="done")` 호출 시 연결된 다음 노드를 자동으로 `running` 상태로 전환한다.  
분기 노드는 `branch_output=1`(true) 또는 `branch_output=2`(false)로 경로를 선택해야 자동 진행된다.  
생략 시 `from_output=0` 기본 경로를 따라가고, 다중 분기 노드에서 생략하면 자동 진행 없음(사용자가 노드 ⋮ 패널에서 선택).

**사용 패턴 (진행 추적):**
```
1. workflow_init(task_type, thread_id, title, steps=[...])
   → 우측 패널에 그래프 캔버스 표시, step_id 반환

2. (단계 시작 전)
   workflow_set_step(task_type, thread_id, step_id, status="running")

3. (실제 작업 실행 — 다른 툴들 호출)

4. (단계 완료 후 — 다음 노드 자동 running 전환)
   workflow_set_step(task_type, thread_id, step_id, status="done", notes="결과 요약")

5. (분기 노드 완료 시 — true 경로 선택)
   workflow_set_step(task_type, thread_id, step_id, status="done", branch_output=1)
```

**사용 패턴 (AI 코웍 편집):** 사용자가 "단계 추가/수정/삭제/순서변경 해줘" 라고 하면
`workflow_add_step`·`update_step`·`remove_step`·`reorder`로 **진행 상태를 보존한 채** 구조만 편집한다.
init은 전체 교체이므로 진행 중 워크플로우 수정에는 단위 툴을 쓴다.

> `task_type`·`thread_id`는 시스템 메시지의 `[현재 세션]` 섹션에서 자동 주입된다. LLM이 직접 알아낼 필요 없다.
> 우측 패널 ✏️ 편집모드에서 사용자가 수동으로 편집하면 `POST /workflow`로 전체 저장된다.

---

## 아키텍처

### 툴 자동 디스커버리

```
서버 시작
  └─ agent/tools/__init__.py
       ├─ pkgutil.iter_modules("agent/tools/") → 파일 목록 스캔
       ├─ 각 파일 import → MANIFEST 속성 확인
       ├─ obsidian_session.py (tools/ 밖) → 명시적 import
       └─ _registry 조립
            ├─ TOOLS      → LLM에 전달하는 function schema 목록
            ├─ TOOL_LABELS → UI 표시명 (채팅 체크리스트)
            └─ run_tool() → handler 호출
```

### 에이전트 루프

```
POST /chat
  └─ generate(message, thread_id, task_type)
       ├─ 시스템 프롬프트 구성 (task_type·thread_id 주입)
       ├─ for step in range(MAX_STEPS=20):
       │    ├─ [중단 플래그 확인]
       │    ├─ SSE: context_usage (토큰 추정)
       │    ├─ SSE: agent_state="thinking"
       │    ├─ LLM streaming (tools=TOOLS)
       │    ├─ finish_reason != "tool_calls" → break
       │    ├─ SSE: agent_state="running"
       │    └─ for tool_call in tool_calls:
       │         ├─ SSE: tool_start
       │         ├─ run_tool() → 결과
       │         ├─ __confirm__ 감지 → SSE: confirm → wait
       │         ├─ workflow_* 감지 → SSE: workflow_update
       │         └─ SSE: tool_done
       └─ 스레드 저장 (Obsidian)
```

### SSE 이벤트 형식

```jsonc
// 요청 ID (스트림 시작 즉시)
{"request_id": "abc123def456"}

// 텍스트 스트리밍
{"type": "text", "content": "..."}

// 툴 실행
{"type": "tool_start", "tool": "mouse_click", "label": "마우스 클릭"}
{"type": "tool_done",  "tool": "mouse_click", "result": "..."}

// 에이전트 상태
{"type": "agent_state", "state": "thinking"}   // LLM 응답 생성 중
{"type": "agent_state", "state": "running"}    // 툴 실행 중
{"type": "agent_state", "state": "waiting"}    // 사용자 입력 대기
{"type": "agent_state", "state": "idle"}       // 완료

// 컨텍스트 사용량
{"type": "context_usage", "tokens_used": 32000, "tokens_total": 128000}

// 사용자 확인 팝업
{"type": "confirm", "confirm_id": "a1b2", "question": "...", "options": [...]}

// 워크플로우 업데이트
{"type": "workflow_update", "workflow": {"title": "...", "steps": [...]}}

// 완료 / 오류
{"type": "done"}
{"type": "error", "message": "..."}
```

---

## 프로젝트 구조

```
agent/
├── server.py            — FastAPI 라우터 (모든 API 엔드포인트)
├── llm.py               — LLM 클라이언트 팩토리
├── config.py            — LLM 프로파일 (openai / internal)
├── obsidian_session.py  — Obsidian 세션·스레드 관리 + TASK_CONFIGS + MANIFEST(4종)
├── core/
│   └── events.py        — SSE 이벤트 타입 상수 (TEXT, TOOL_START, AGENT_STATE, ...)
├── workflow/
│   ├── model.py         — Workflow·WorkflowStep 데이터클래스
│   └── storage.py       — Obsidian JSON 저장 + 태스크별 기본 템플릿
└── tools/
    ├── __init__.py      — 자동 디스커버리 레지스트리 (수정 불필요)
    ├── ocr.py           — MANIFEST(1종)
    ├── screen.py        — MANIFEST(9종)
    ├── desktop.py       — MANIFEST(19종)
    ├── browser.py       — MANIFEST(22종)
    ├── process.py       — MANIFEST(9종)
    ├── document.py      — MANIFEST(9종)
    ├── obsidian_rag.py  — MANIFEST(16종) 탐색·편집·이동·고급검색
    ├── interaction.py   — MANIFEST(1종) ask_user
    └── workflow.py      — MANIFEST(8종) init·set_step·add_step·update_step·remove_step·reorder·add_connection·remove_connection
```

---

## MANIFEST 키 레퍼런스

| 키 | 타입 | 설명 |
|----|------|------|
| `name` | `str` | 툴 식별자. `run_tool()` 키, LLM function name과 반드시 일치 |
| `label` | `str` | UI 표시명. 채팅창 체크리스트에 표시되는 한글 이름 |
| `schema` | `dict` | LLM에 전달하는 OpenAI function calling 스키마 |
| `handler` | `callable` | 실행 함수. `lambda a: fn(a["param"])` 형태로 dict 인자 수신 |

```python
# 최소 예시 (파라미터 없는 툴)
{
    "name":    "get_mouse_position",
    "label":   "마우스 위치 확인",
    "schema":  {"type": "function", "function": {
                    "name": "get_mouse_position",
                    "description": "현재 마우스 커서의 좌표를 반환합니다.",
                    "parameters": {"type": "object", "properties": {}}
                }},
    "handler": lambda a: get_mouse_position()
}
```

---

## 새 툴 추가하는 법

```python
# agent/tools/mymodule.py

def my_tool(param: str) -> str:
    return f"결과: {param}"   # 반환값은 항상 str

MANIFEST = [
    {
        "name": "my_tool",
        "label": "나의 툴",
        "schema": {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "LLM이 이해할 수 있도록 무엇을 하는지 명확히 설명.",
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

**코딩 규칙:**
- 반환값은 항상 `str`
- JSON 반환 시 `json.dumps(..., ensure_ascii=False)`
- 예외는 caller에게 전파 → `server.py` try/except가 SSE error로 변환
- 긴 결과는 잘라서 반환 (LLM 컨텍스트 절약)

---

## 핵심 자동화 패턴

### 화면에서 텍스트 찾아 클릭
```
find_text_location("저장") → {"x": 450, "y": 300}
mouse_click(450, 300)
```

### 브라우저 로그인 (권장 패턴)
```
browser_open("http://intranet/login")
browser_get_interactive_elements()     ← 실제 선택자 먼저 확인
browser_fill("input[name='username']", "user01")
browser_fill("input[name='password']", "pass")
browser_press_key("Enter")             ← 폼 제출은 버튼 클릭 대신 Enter
browser_wait_for_url("/dashboard")
```

### 작업 완료까지 대기
```
(배포 시작)
wait_for_text("배포 완료", timeout=60)
save_screenshot("deploy_result.png")
```

### UAC/관리자 앱 제어
```
mouse_click(x, y, use_sendinput=True)
key_press("ctrl+s", use_sendinput=True)
```

### 워크플로우 기반 다단계 작업
```
workflow_init(task_type, thread_id, "배포 작업", steps=[
    {"title": "빌드 확인", "type": "auto"},
    {"title": "서버 접속", "type": "auto"},
    {"title": "배포 실행", "type": "semi_auto"},
])
→ 단계별로 workflow_set_step(status="running") / "done" 업데이트
```

---

## 빠른 테스트

```powershell
conda activate mes-agent
cd D:\GithubRepositories\mes-agent

# 툴 레지스트리 확인
python -c "from agent.tools import TOOLS, TOOL_LABELS; print(f'툴 수: {len(TOOLS)}')"

# 개별 툴 테스트
python -c "from agent.tools.desktop import get_mouse_position; print(get_mouse_position())"
python -c "from agent.tools.screen import get_pixel_color; print(get_pixel_color(100,100))"
python -c "from agent.tools.process import get_system_info; print(get_system_info())"

# 브라우저 툴 (Chromium 창 열림)
python -c "
from agent.tools.browser import _browser_open, _browser_close
print(_browser_open({'url': 'https://example.com'}))
print(_browser_close({}))
"

# 워크플로우 기본 템플릿 확인
python -c "
from agent.workflow.storage import load_workflow
wf = load_workflow('syncade', 'test-001')
for s in wf.steps: print(f'  [{s.type}] {s.title}')
"
```

---

## LLM 프로파일 전환

```python
from agent.config import get_active, active_llm
print(get_active())   # 'openai' 또는 'internal'
print(active_llm())   # {'base_url': ..., 'model': ..., 'api_key': ...}
```

`.env` 사내 LLM 설정:
```ini
LLM_INTERNAL_BASE_URL=http://192.168.x.x:8000/v1
LLM_INTERNAL_MODEL=your-model-name
INTERNAL_API_KEY=your-key
```
