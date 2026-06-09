# MES Agent — Claude 개발 가이드

## ⚡ 문서 자동 업데이트 규칙 (필독)

**기능을 구현하거나 수정할 때마다 반드시 아래 항목을 함께 업데이트해야 한다.**

| 변경 유형 | 업데이트할 파일 |
|-----------|----------------|
| 새 툴 추가 (`agent/tools/*.py`) | `CLAUDE.md` 현재 상태, `README.md` 기능 표, `docs/agent-guide.md` 툴 목록 |
| 새 워크플로우 추가 (`agent/workflows/*.py`) | `CLAUDE.md` 현재 상태, `README.md` 기능 표, `electron/renderer/index.html` 사이드바 버튼 |
| UI 변경 | `CLAUDE.md` 현재 상태, `README.md` 스크린샷·설명 |
| 설정 항목 추가 (`.env`) | `.env.example`, `SETUP.md` 환경 설정 섹션 |
| 의존성 추가 (`requirements.txt` / `package.json`) | `SETUP.md` 사전 요구사항 |
| 버그 수정 | `CLAUDE.md` 현재 상태의 해당 항목에 ✅ 표시 또는 노트 추가 |
| 새 툴 추가 / 삭제 | `tests/smoke/test_tool_schemas.py`의 `EXPECTED_TOOL_COUNT` 상수도 업데이트 |

**체크리스트 형식**: 구현 완료 항목은 `- [ ]` → `- [x]` 로, 상태 표기는 `🔲 개발 예정` → `🚧 개발 중` → `✅ 완성` 순서로 변경한다.

---

## 프로젝트 개요

사내 폐쇄망 환경에서 동작하는 LLM 기반 업무자동화 데스크탑 에이전트.
사용자가 자연어로 지시하면 에이전트가 화면 인식, 키보드/마우스 제어, 문서 처리 등 업무를 대신 수행한다.

- **실행 환경**: Windows 10/11, 사내 폐쇄망
- **LLM**: OpenAI 호환 REST API (사내 LLM 또는 OpenAI, `.env`에서 전환)
- **UI**: Electron 데스크탑 앱 (채팅 + 사이드바 업무 버튼)

---

## 현재 상태

### ✅ 구현 완료

| 항목 | 파일 | 비고 |
|------|------|------|
| 자동화 테스트 (TDD) | `tests/` + `pytest.ini` + `test.ps1` | unit/integration/smoke 3계층, 268개 테스트, `.\test.ps1` 으로 실행 |
| Electron 앱 실행 | `electron/main.js` | Python 서버 자동 시작, IPC server-ready 이벤트 |
| 채팅 UI | `electron/renderer/` | SSE 스트리밍, 툴 실행 단계 실시간 표시, 환영 메시지 |
| 앱 시작 시 기본업무 자동 진입 | `electron/renderer/chat.js` | `initWhenReady()` → `openTask('general')` 자동 호출 |
| LLM 프로파일 전환 | `agent/config.py` | OpenAI ↔ 사내 LLM 런타임 전환, UI 버튼 |
| FastAPI 서버 | `agent/server.py` | `/health` `/chat` `/profile` `/tool/test` `/task-config` `/threads/*` |
| OCR (전체/영역) | `agent/tools/ocr.py` + `screen.py` | Tesseract 5.4, kor+eng, 영역 지정 OCR |
| 화면 인텔리전스 | `agent/tools/screen.py` | 이미지 템플릿 매칭, 텍스트 좌표, 이미지/텍스트 대기(**interval 파라미터 명시화**), 스크린샷 비교, 픽셀 색상, 창 캡처 (9종) |
| 데스크탑 제어 | `agent/tools/desktop.py` | 마우스(클릭·이동·스크롤·드래그·down/up)·**mouse_click after_delay_ms 추가**, 키보드(press·down·up), 클립보드, 창 관리 (19종) |
| 브라우저 자동화 | `agent/tools/browser.py` | Playwright Chromium 싱글턴, 클릭·입력·대기·JS·스크린샷·파일업로드·쿠키 (22종), **전용 단일 스레드 executor로 greenlet 스레드 충돌("Cannot switch to a different thread") 해결** |
| Obsidian PKM (Phase 7 ✅) | `agent/tools/obsidian_rag.py` | 2-tier 탐색(preview/scan/backlinks/section), 편집(edit/replace_section/update_frontmatter), 이동, 고급검색 (16종) |
| 프로세스/시스템 | `agent/tools/process.py` | PowerShell/CMD 실행, 프로세스 관리, 파일 시스템, 시스템 정보 (9종) |
| 문서 처리 + Office 검토 | `agent/tools/document.py` | Excel/Word/PDF/텍스트 읽기·쓰기 + **마크다운→진짜 docx 변환(write_word)**, Word 검토메모·수정추적, Excel 셀메모, PPT 슬라이드 읽기 (14종) |
| 툴 직접 테스트 패널 | `electron/renderer/tool-test.js` | LLM 없이 `/tool/test` 직접 호출 |
| 환경 설정 | `.env` / `start.ps1` | conda + nvm PATH 자동 설정 |
| Obsidian 세션 관리 | `agent/obsidian_session.py` | 세션 자동 기록, 개발 노트, 백로그, 세션 검색 (4종 툴) |
| 업무 스레드 대화 | `agent/obsidian_session.py` + `agent/server.py` | 사이드바 버튼별 독립 다중 스레드, 멀티턴 대화 이력, 완료/보관/삭제, Obsidian 저장 |
| 스레드 API | `agent/server.py` | `/task-config` `/threads/{type}` GET·POST·DELETE `/threads/{type}/{id}/messages·close·restore·unarchive·permanent` |
| Playwright 브라우저 바이너리 | `%LOCALAPPDATA%\ms-playwright\` | `python -m playwright install chromium` 으로 설치 |
| 에이전트 루프 + 중단 | `agent/server.py` | `_MAX_STEPS=20`, `POST /stop/{request_id}`, `_stop_flags` 딕셔너리 |
| 에이전트 상태 바 | `electron/renderer/chat.js` + `style.css` | thinking/running/waiting/idle 상태 표시, 중단 버튼 |
| 컨텍스트 사용량 표시 | `agent/server.py` + `chat.js` | 토큰 추정치 헤더 바 표시 |
| 우측 워크플로우 패널 | `electron/renderer/workflow.js` + `style.css` | 리사이즈 핸들, 탭(워크플로우/실행로그), 접기/펼치기, **단계 카드 클릭 시 상세 펼침**, **편집모드(제목·단계 CUD·드래그앤드롭 순서변경)** |
| 워크플로우 편집 툴 | `agent/tools/workflow.py` | `workflow_init`·`set_step`·`add_step`·`update_step`·`remove_step`·`reorder`·**`add_connection`·`remove_connection`** (8종), AI 코웍 편집, 내부 그래프 모델 |
| 워크플로우 데이터 모델 | `agent/workflow/model.py` + `storage.py` | Vault `agent/workflows/{type}/{id}.json` 저장, **기본 템플릿 최초 1회 영속화로 단계 id 고정** |
| 워크플로우 그래프 모델 (Phase 1 ✅) | `agent/workflow/model.py` | `WorkflowNode`·`WorkflowConnection`·`WorkflowDefinition`(불변)·`NodeState`·`WorkflowRunState`(가변), `migrate_linear_to_graph()` |
| 그래프 스토리지 + 마이그레이션 | `agent/workflow/storage.py` | `detect_format`·`load_definition`·`save_definition`·`load_run_state`·`save_run_state`, 구 포맷 자동 마이그레이션, 하위 호환 |
| RunState 동기화 | `agent/server.py` | workflow 툴 결과 + 툴 실패 auto-error 시 RunState 파일(`*_state.json`) 자동 동기화 |
| 워크플로우 API | `agent/server.py` | `GET/POST/DELETE /threads/{type}/{id}/workflow` |
| SVG 분기 연결선 (Phase 3 ✅) | `electron/renderer/workflow.js` + `style.css` | 비선형 연결만 SVG 오버레이 표시, from_output별 색상 (기본/true/false 분기), 편집모드 연결 CUD UI |
| YAML frontmatter 스토리지 (Phase 4C ✅) | `agent/workflow/storage.py` | `_def_path()`·`save_definition()`이 `.md` 형식으로 저장, `load_definition()`이 `.md` 우선 로드, `.json` 자동 마이그레이션 후 삭제 |
| SSE 파일 감지 엔드포인트 (Phase 4B ✅) | `agent/server.py` | `GET /threads/{type}/{id}/workflow/events` — mtime 폴링 SSE, `WF_POLL_INTERVAL` 환경변수(기본 2s), heartbeat 30s 주기 |
| 워크플로우 파일 감지 (Phase 4 frontend ✅) | `electron/renderer/workflow.js` | `_startFileWatcher()`·`_stopFileWatcher()` EventSource, 스레드 전환 시 자동 연결·해제, 편집 중 캐시 갱신 |
| 빠른 작업 버튼 | `electron/renderer/index.html` | OCR·파일은 **완성형 → 원클릭 자동 실행**, 브라우저·타이핑은 템플릿 삽입 후 포커스 |
| SSE 이벤트 상수 | `agent/core/events.py` | TEXT/TOOL_START/TOOL_DONE/CONFIRM/AGENT_STATE/CONTEXT_USAGE/WORKFLOW_UPDATE/DONE/ERROR |
| 툴 실패 자동 error 전환 | `agent/server.py` | 툴 예외 발생 시 running 단계 → error 상태 자동 갱신, WORKFLOW_UPDATE SSE 발행 |
| 단계 재시도 버튼 | `electron/renderer/workflow.js` + `style.css` | error 단계에 ↺ 재시도 버튼, 클릭 시 채팅 입력으로 에이전트 재시작 |
| `WorkflowStep.max_retry` | `agent/workflow/model.py` | 재시도 횟수 설정 (기본 0), 직렬화/역직렬화 + 기존 JSON 하위 호환 |
| wait_for_image/wait_for_text interval 명시화 (Phase 5 ✅) | `agent/tools/screen.py` | MANIFEST 스키마에 `interval` 파라미터 노출 → LLM이 폴링 간격 직접 제어 가능 |
| mouse_click after_delay_ms (Phase 5 ✅) | `agent/tools/desktop.py` | 클릭 후 안정화 대기 옵션, MANIFEST 스키마 및 함수 시그니처에 추가 |
| 런타임 라우팅 엔진 (Phase 6A ✅) | `agent/workflow/model.py` + `workflow.py` + `server.py` | `set_step("done")` 시 다음 노드 자동 running, `branch_output` 분기 선택, `PATCH /workflow/nodes/{id}` UI 제어 엔드포인트 |
| 그래프 캔버스 시각화 (Phase 6B ✅) | `electron/renderer/workflow.js` + `style.css` | BFS 레이아웃 2D 그래프, running/done/error 애니메이션, 분기 색상·흐름 연결선, 진행 바 |
| 인터랙티브 노드 컨트롤 (Phase 6C ✅) | `electron/renderer/workflow.js` + `style.css` | 노드 ⋮ 클릭 → 완료/건너뛰기/실행/재시도/분기 선택 패널 |
| Obsidian PKM 스레드 (Phase 7 ✅) | `agent/tools/obsidian_rag.py` + `obsidian_session.py` | `obsidian-rag` → `obsidian` 전환, 2-tier 탐색·편집·이동 9종 신규 툴, 시스템 프롬프트 전면 개편 |
| Vault 노트작성 가이드 (Phase 7B ✅) | `D:\_Archives\obsidian\brain\agent\guides\🤖 Agent 노트작성 가이드.md` | frontmatter 스키마·태그·Templater 연동 기준, `🏛 Vault Guides.md` 연결 |
| Templater 명령 툴 (Phase 7B ✅) | `agent/tools/obsidian_rag.py` | `obsidian_list_commands`·`obsidian_run_command` — REST API `/commands/` 엔드포인트 |
| RAG-first 지침 전파 (Phase 7B ✅) | `agent/obsidian_session.py` | `_AUTO_EXEC` + syncade/knox/obsidian 시스템 프롬프트에 Obsidian 선조회·결과저장 지시 추가 |
| Office 문서 검토·메모 읽기 ✅ | `agent/tools/document.py` | Word 검토메모·수정추적, Excel 셀메모, PPT 슬라이드+노트 (OpenXML 파싱, 설치 불필요) |
| 멀티모달 비전 분석 ✅ | `agent/tools/vision.py` | `analyze_screen`·`analyze_region` — VISION_ENABLED=true + 멀티모달 LLM 필요, 사용 전 유저 확인 |
| Windows UI Automation ✅ | `agent/tools/ui_automation.py` | `ui_list_windows`·`ui_inspect_window`·`ui_find_and_read` — 접근성 트리 읽기, OCR 없이 Win32 컨트롤 구조 파악 |
| 스레드 사이드바 접이식 그룹 ✅ | `electron/renderer/chat.js` + `index.html` + `style.css` | 탭 → 그룹 접기/펼치기, 스레드 인라인 표시, 그룹별 보관 서브섹션, 빨간 배지 |
| 브라우저 greenlet 스레드 버그 수정 ✅ | `agent/tools/browser.py` | 전용 단일 스레드 executor(`_on_pw_thread`)로 모든 Playwright 핸들러 위임 → "Cannot switch to a different thread" 해결 (웹 조사 실패 수정) |
| 마크다운→진짜 docx 변환 ✅ | `agent/tools/document.py` | `write_word` — 제목·목록·굵게·표를 Word 서식으로 변환한 OOXML .docx 저장. write_file 스키마에 .docx 경고 추가 |
| 긴 호흡·자가복구 에이전트 ✅ | `agent/obsidian_session.py` + `agent/server.py` | `_AUTO_EXEC`/`_AUTONOMOUS_INSTRUCTION`에 끈질긴 문제해결·근본원인 조사·선택지 제시 지침, `_MAX_STEPS` 20→40, 단계 상한 도달 시 '계속' 안내 |
| 실행 중 창 최소화 UX (백로그 C) ✅ | `electron/main.js` + `preload.js` + `chat.js` + `index.html` | agentState=running 시 자동 최소화/반투명/끄기 (헤더 토글, localStorage 저장), idle 시 원복 |
| 모델 선택 드롭다운 (백로그 D) ✅ | `agent/config.py` + `agent/llm.py` + `agent/server.py` + `chat.js` | `/models` 동적 조회(/v1/models, 3s 타임아웃) → .env `LLM_*_MODELS` 프리셋 폴백, 런타임 모델 오버라이드, 헤더 드롭다운 |
| IDE식 스레드 탭 (백로그 A) ✅ | `electron/renderer/chat.js` + `index.html` + `style.css` | 상단 열린 스레드 탭 바, X=탭 닫기(사이드바 보존), 탭 클릭 전환, 보관/삭제 시 탭 동기화 |
| 워크플로우 컴팩트·반응형 (백로그 B) ✅ | `electron/renderer/workflow.js` + `style.css` | ResizeObserver로 패널 폭 감지 → 좁으면(<360px) 세로 컴팩트 카드(완료 단계 접기), 넓으면 2D 그래프 |
| MS Office 편집 엔진 (COM + 폴백) ✅ | `agent/tools/office_com.py` | Word(찾아바꾸기·삽입·메모·수정추적수락·PDF)·Excel(셀/수식·범위읽기)·PPT(슬라이드추가·찾아바꾸기·PDF)를 COM으로 구동(완전충실도). 전용 STA 단일스레드 executor, COM 불가 시 python-docx/openpyxl/python-pptx 자동 폴백, 편집 전 자동 백업, OOXML 검증 (11종) |
| Office Online(웹) 편집 진입 ✅ | `agent/tools/browser.py` | `office_web_open` — SharePoint/365 문서를 브라우저로 열고 편집화면 대기+스크린샷. `BROWSER_CHANNEL=msedge`로 실제 Edge 구동. 이후 키보드(Ctrl+H/Ctrl+S)+UI Automation 편집 |
| 보안: 인증·Origin 게이트 (S1/S3) ✅ | `agent/server.py` + `main.js` + `preload.js` + `chat.js` | 원격 Origin 차단 + 토큰(X-Auth-Token/?token) 검증. main.js 실행마다 랜덤토큰 생성·주입, 토큰 미설정 시 미강제(dev/test 호환), /health 무인증 |
| 보안: 파괴적 작업 가드 (S2/S4/S5) ✅ | `agent/tools/_safety.py` + `process.py` + `document.py` | 치명적 명령(재귀삭제·포맷·디스크/레지스트리·종료) 차단→force 필요, 시스템 보호경로 쓰기 차단, 기존파일 덮어쓰기 전 자동 백업 |
| 중앙 집중 안전 게이트 (G3 / APPROVE1) ✅ | `agent/tools/_safety.py` + `agent/server.py` + `chat.js`/`style.css` | `classify_risk(safe/mutate/destructive)`를 **루프의 run_tool 직전에서 강제**(모델 force 우회 불가). 균형형: 읽기·관찰·입력형=safe, 쓰기·삭제·셸변경·office편집·네트워크만 확인. 기존 CONFIRM 팝업 재사용(예/항상/아니오), 타임아웃=거부(무인 자동승인 금지), "항상"은 세션 허용목록. tool 짝 보존(I1). `docs/contracts/L1_loop_contract.md` 기준 |
| 컨텍스트 compaction (G1) ✅ | `agent/core/compaction.py` + `agent/server.py` | 컨텍스트가 임계(`_CONTEXT_MAX_TOKENS*0.8`) 초과 시 루프 진입부에서 자동 압축: 선두 system+최근 N턴(8) 보존, 중간을 LLM 요약(`_summarize_history`, 비스트리밍 1회) system 1개로 치환. **tool_calls↔tool 짝 보존(I1)**, `COMPACTION` SSE 고지, `MAX_COMPACT=3` 상한(I3). 요약 LLM은 주입식이라 순수·테스트 가능 |
| continuation nudge (G2) ✅ | `agent/server.py` | 모델이 도구 사용 도중 텍스트로 조기 종료하면(`finish_reason!=tool_calls`) 한도(`MAX_NUDGES=2`) 내에서 '계속' 메시지를 주입해 끈질기게 진행. 견고성 게이트: `tool_rounds>0`(잡담 제외)·되묻기(`?` 종결)·사용자 중단 시엔 nudge 안 함. 무한루프 방지(I3), 항상 `DONE` 마감(I4) |

**총 툴 수: 127종** (각 툴 파일의 `MANIFEST` 기준 — 자동 디스커버리로 등록)

| 모듈 | 툴 수 |
|------|-------|
| `ocr.py` | 1 |
| `screen.py` | 9 |
| `desktop.py` | 19 |
| `browser.py` | 23 |
| `process.py` | 9 |
| `document.py` | 15 |
| `obsidian_rag.py` | 18 |
| `interaction.py` | 1 |
| `workflow.py` | 8 |
| `obsidian_session.py` | 4 |
| `vision.py` | 2 |
| `ui_automation.py` | 3 |
| `office_com.py` | 11 |
| `office_libre.py` | 1 |
| `office_cloud.py` | 3 |

---

### ✅ 완성된 기능 (Phase 0 — 2026-05-29)

| 항목 | 내용 |
|------|------|
| Phase 0 task_type/thread_id 주입 | `server.py generate()` — 시스템 프롬프트에 세션 컨텍스트 삽입, LLM이 workflow 툴 호출 시 올바른 값 사용 |
| `_AUTO_EXEC` 워크플로우 지침 | `obsidian_session.py` — 작업 시작 시 `workflow_init` 강제, 각 단계 `workflow_set_step` 업데이트 지침 |
| TASK_CONFIGS 시스템 프롬프트 보강 | `obsidian_session.py` — 5개 업무별 워크플로우 상세 지침, 브라우저 조작 전략 명시 |
| 태스크별 기본 워크플로우 템플릿 | `agent/workflow/storage.py` — general(4)/syncade(6)/obsidian(5)/unscript(5)/knox(5) 단계 |
| 워크플로우 데이터 모델 | `agent/workflow/model.py` — Workflow·WorkflowStep 데이터클래스, StepType·StepStatus Literal |
| 워크플로우 스토리지 | `agent/workflow/storage.py` — Vault `agent/workflows/{type}/{id}.json` 저장/로드/삭제 |
| 워크플로우 툴 | `agent/tools/workflow.py` — `workflow_init`·`set_step`·`add_step`·`update_step`·`remove_step`·`reorder` (6종) |
| 워크플로우 API | `agent/server.py` — `GET/POST /threads/{type}/{id}/workflow` |
| 우측 워크플로우 패널 | `electron/renderer/workflow.js` + `style.css` — 탭 전환, 드래그 리사이즈, 접기/펼치기 |
| 에이전트 상태 바 + 중단 버튼 | `electron/renderer/chat.js` — thinking/running/waiting/idle, `POST /stop/{request_id}` |
| 컨텍스트 사용량 표시 | `agent/server.py` + `chat.js` — 헤더 진행 바, 80%/95% 경고 |
| 실행 로그 패널 | `electron/renderer/workflow.js` — 툴 실행 시간·결과 기록, 최대 50개 유지 |
| 빠른 작업 버튼 | `electron/renderer/index.html` — OCR·파일·브라우저·타이핑 프롬프트 삽입 |
| SSE 이벤트 상수 | `agent/core/events.py` — 모든 이벤트 타입 중앙화 |

---

### 🚧 개발 예정 기능 상세

---

#### 1. ✅ 멀티모달 비전 (`agent/tools/vision.py`) — 완성

**구현 완료** (2026-06-07):
- `analyze_screen(prompt)` — 전체화면 base64 → LLM `image_url` 전달
- `analyze_region(x,y,width,height,prompt)` — 영역 지정 분석
- `VISION_ENABLED=true` 환경변수 게이트 — 비활성 시 안내 메시지 반환
- 사용 전 사내 LLM 비전 지원 여부 유저 확인 흐름 (`ask_user` 연동)

---

#### 2. 일반 채팅 대화 기억 (`agent/memory.py`)

> ⚠️ **스레드 모드는 이미 구현됨**: 사이드바 업무 버튼을 통한 스레드 대화는 Obsidian에 전체 히스토리를 저장하고 이어서 대화 가능. 아래는 **기본업무 채팅(스레드 미사용 단일 메시지)** 에 대한 기억 기능이다.

**무엇**: 기본업무 채팅에서도 이전 대화를 기억하고, 맥락을 참고해 답변한다.

**왜 필요**: 현재 기본업무는 thread_id 없이 호출 시 매 메시지가 독립적이어서 "아까 했던 거 다시 해줘" 같은 지시가 불가능.

**구현 계획**:
```
agent/server.py 내 generate() 수정
  - messages 리스트를 세션 단위로 유지 (role: user/assistant/tool)
  - 컨텍스트 한계 도달 시 요약 또는 슬라이딩 윈도우 적용
```

완료 시 `CLAUDE.md` + `README.md` 업데이트.

---

#### 3. ✅ 업무 워크플로우 패널 — 완성

**구현 완료** (2026-05-29):
- `agent/workflow/model.py` — Workflow·WorkflowStep 데이터클래스
- `agent/workflow/storage.py` — Vault JSON 저장 + 태스크별 기본 템플릿
- `agent/tools/workflow.py` — `workflow_init`·`set_step`·`add_step`·`update_step`·`remove_step`·`reorder` (6종)
- `electron/renderer/workflow.js` — 우측 패널 렌더링·리사이즈·탭
- `agent/server.py` — `GET/POST /threads/{type}/{id}/workflow` API
- Phase 0: task_type/thread_id 시스템 프롬프트 주입으로 LLM이 툴 호출 가능

---

#### 4. ✅ Obsidian RAG 연동 — 완성

**구현 완료**: `agent/tools/obsidian_rag.py` (16종 툴, Phase 7 확장)
- `obsidian_search` — Vault 전체 키워드 검색
- `obsidian_read_note` — 노트 읽기
- `obsidian_list_notes` — 폴더 목록
- `obsidian_write_note` — 노트 생성/덮어쓰기
- `obsidian_append_note` — 노트에 내용 추가
- `obsidian_get_tags` — 태그 조회
- `obsidian_follow_links` — `[[wikilink]]` BFS 다중 뎁스 스캔

접근: Local REST API (`OBSIDIAN_HOST`) → 직접 파일 fallback (`OBSIDIAN_VAULT_PATH`)

---

#### 5. Electron 패키징 / 배포 (`electron-builder`)

**무엇**: 앱을 `.exe` 인스톨러로 패키징하여 사내 PC에 배포한다.

**왜 필요**: 현재는 개발 환경(`npm start`)으로만 실행 가능. 일반 사용자에게는 설치 파일 필요.

**구현 계획**:
- `electron-builder` 설정 (`package.json`에 `build` 섹션 추가)
- Python 환경을 앱에 번들하거나 별도 설치 가이드 제공
- `npm run dist` 명령으로 빌드

완료 시 `CLAUDE.md` + `README.md` + `SETUP.md` 배포 섹션 업데이트.

---

## 리팩토링 작업 규칙 (L1 루프 개선)

### 출처 거버넌스 (절대)
- 설계 출처는 ① 이 레포 코드 ② openclaw(MIT) ③ LangGraph/Temporal 공개 문서뿐.
- 유출된 Claude Code 소스("openclaude"/query.ts 등) 및 그 파생물은 **금지 소스**.
  읽지도, 참고하지도, 인용하지도 마라. ref/ 는 절대 커밋 금지(.gitignore 확인).

### 작업 방식
- 구현 기준은 docs/contracts/L1_loop_contract.md (이 계약서만 따른다).
- 전체 맥락은 docs/CLAW_PORT_PLAN.md 참고.
- TDD: 계약서의 불변조건(§10) → 실패 테스트 먼저 → 최소 구현.
- 한 번에 한 격차(G3→G1→G2→G4 순). 다른 파일 광범위 수정 금지.
- 외부 네트워크 호출 추가 금지. 모델 엔드포인트는 기존 설정(config) 사용.
- 설치 명령(pip/conda) 실행 금지 — 필요하면 알려만 줘라.
- git push 금지. 커밋 메시지 초안만 제안.

---

## 기술 스택

### Frontend
- **Electron 42** — 데스크탑 앱 (Node.js 22)
- **Vanilla JS + HTML/CSS** — 빌드 도구 없이 단순하게 유지

### Backend
- **Python FastAPI + uvicorn** — 에이전트 서버 (Python 3.11)
- **openai SDK** — LLM 클라이언트 (OpenAI 호환, `base_url`로 사내 LLM 연결)

### 자동화
- **pyautogui** — 마우스/키보드 기본 제어
- **pynput** — key_down/up 분리, 정밀 키 홀드
- **pyperclip** — 클립보드 경유 한글 입력
- **pywin32 (SendInput)** — UAC/관리자 권한 앱 제어
- **playwright** — 웹 자동화 (Chromium 싱글턴, `python -m playwright install chromium` 필요)
- **psutil** — 프로세스 관리

### 화면 인식
- **pytesseract + Tesseract 5.4** — OCR (kor+eng)
- **pillow** — 이미지 처리
- **opencv-python** — 이미지 템플릿 매칭, 스크린샷 비교
- **mss** — 빠른 스크린샷 (pyautogui 대비 ~10x)
- **멀티모달 LLM** — 복잡한 화면 해석 🔲 개발 예정

### 문서 처리
- **openpyxl** — Excel 읽기/쓰기/행 추가
- **python-docx** — Word 읽기/내용 추가
- **pdfplumber** — PDF 텍스트 추출

---

## UI 구성

> **용어 기준**: UI·도메인 용어(업무/스레드/대화/워크플로우/단계, 화면 구역명 등)는
> `README.md`의 **용어 사전(Glossary)** 을 단일 기준으로 삼는다.
> 새 용어를 쓰거나 명칭을 바꿀 때는 README 용어 사전을 먼저 갱신하고 코드·문서를 맞춘다.
> 계층: **업무(task_type) ⊃ 스레드(thread_id) ⊃ 대화(messages) + 워크플로우(workflow) ⊃ 단계(step)**

```
┌───────────────────────────────────────────────────────────────────────┐
│  MES Agent        [컨텍스트 ████░ 40k/128k]    [LLM 프로파일] ● 준비됨 │ ← 헤더
├──────────────┬──────────────────────────────┬──│──────────────────────┤
│  업무 자동화  │ 💬 기본업무 | +새 시작 | #001×│  │  📋 워크플로우  🗒️ 로그  › │
│ 💬 기본업무● │         [완료하기] [보관됨↓]  │  ├──────────────────────┤
│  🚀 Syncade  ├──────────────────────────────┤  │ 1 ○ 환경 확인      🤖 │
│  🧠 Obsidian │                              │  │ 2 ⏳ 서버 접속 중  🤖 │
│  🤖 Unscript │   채팅 메시지 영역            │  │ 3 ○ 배포 실행      👁️ │
│  📥 Knox     │   (툴 실행 체크리스트)        │  │ 4 ○ 결과 확인      🤖 │
│  ──────────  │                              │  │                      │
│  빠른 작업   ├──────────────────────────────┤  │                      │
│  📷 화면 OCR │ 🧠 생각 중...    [■ 중단]    │  │                      │
│  📂 파일열기 ├──────────────────────────────┤  │                      │
│  🌐 브라우저  │  입력창              [전송]   │  │                      │
│  ⌨️ 타이핑   └──────────────────────────────┘  └──────────────────────┘
└──────────────                                       우측 패널 (리사이즈)
```

- 앱 시작 시 **기본업무** 탭이 자동으로 열림
- 빈 스레드에서는 업무 설명(welcome 메시지)이 표시되고, 대화창 클릭 시 입력 포커스
- 업무 버튼 전환 시 메시지가 있는 가장 최근 스레드를 자동 선택
- 스레드 탭의 `×` 버튼으로 영구 삭제
- 우측 패널: 워크플로우 단계 카드 / 실행 로그 탭 전환, 드래그 리사이즈, `›` 버튼으로 접기
- 에이전트 상태 바: thinking/running/waiting/idle 상태 + 중단 버튼
- 헤더 컨텍스트 바: 토큰 사용량 시각화 (80% 경고, 95% 위험)

---

## 프로젝트 구조 (현재)

```
mes-agent/
├── CLAUDE.md               ← 이 파일 (개발 가이드 + 상태 추적)
├── README.md               ← GitHub용 소개
├── SETUP.md                ← 설치 가이드
├── docs/
│   └── agent-guide.md      ← 툴 추가 방법 가이드
├── electron/
│   ├── main.js             ← Python 서버 자동 시작, 창 생성
│   ├── preload.js          ← contextBridge (serverPort 노출)
│   └── renderer/
│       ├── index.html      ← UI 레이아웃 (3-패널: 사이드바 + 채팅 + 우측 워크플로우)
│       ├── chat.js         ← 채팅 + SSE 스트리밍 + 에이전트 상태 바 + 중단 버튼
│       ├── workflow.js     ← 우측 워크플로우 패널 + 실행 로그 탭 + 드래그 리사이즈
│       ├── tool-test.js    ← 도구 직접 테스트 패널
│       └── style.css       ← 다크 테마
├── agent/
│   ├── server.py           ← FastAPI (/health /chat /stop /profile /tool/test /task-config /threads/* /workflow)
│   ├── llm.py              ← LLM 클라이언트 팩토리
│   ├── config.py           ← LLM 프로파일 (openai/internal)
│   ├── obsidian_session.py ← Obsidian 세션·스레드 관리, TASK_CONFIGS (5종)
│   ├── core/
│   │   └── events.py       ← SSE 이벤트 타입 상수
│   ├── workflow/
│   │   ├── model.py        ← Workflow·WorkflowStep 데이터클래스
│   │   └── storage.py      ← Vault agent/workflows/ 파일 저장/로드
│   └── tools/
│       ├── __init__.py     ← 자동 디스커버리 레지스트리 (수정 불필요)
│       ├── ocr.py          ← 전체화면 OCR (1종) ✅
│       ├── desktop.py      ← 마우스·키보드·클립보드·창 관리 (19종) ✅
│       ├── screen.py       ← 화면 인텔리전스: 영역OCR·이미지매칭·텍스트위치·대기·비교·픽셀 (9종) ✅
│       ├── browser.py      ← Playwright 브라우저 자동화 (22종) ✅
│       ├── process.py      ← 프로세스·시스템·파일 관리 (9종) ✅
│       ├── document.py     ← Excel·Word·PDF·텍스트 처리 + 마크다운→docx (14종) ✅
│       ├── office_com.py    ← MS Office COM 편집(Word·Excel·PPT 찾아바꾸기·삽입·셀/수식·메모·PDF) + 폴백 (11종) ✅
│       ├── office_libre.py   ← LibreOffice 헤드리스 변환(오프라인 PDF/포맷 폴백) (1종) ✅
│       ├── office_cloud.py    ← MS Graph 클라우드 Excel 편집(셀/수식 REST) (3종) ✅
│       ├── _safety.py       ← 파괴적 작업 가드(위험명령·보호경로·백업) — 툴 아님
│       ├── interaction.py  ← 사용자 확인 요청 ask_user (1종) ✅
│       └── workflow.py     ← 워크플로우 init·set_step·add/update/remove_step·reorder (6종) ✅
├── start.ps1               ← 개발 환경 시작 (conda + nvm PATH 자동 설정)
├── .env                    ← 로컬 설정 (git 제외)
├── .env.example            ← 설정 템플릿
├── requirements.txt        ← Python 의존성 (22개 패키지 — 런타임 18 + 테스트 4)
└── package.json            ← Electron 42, Node 22
```

---

## Obsidian Knowledge Base 연동

### 개요
Obsidian Vault를 로컬 RAG로 활용한다.
에이전트가 업무 도메인 지식, 시스템 명세, 기존 분석 노트를 참조하기 위해 Vault를 오간다.

### Vault 경로 설정
Vault 경로는 하드코딩하지 않는다. 반드시 `.env` 파일에서 읽어온다.

### 검색 및 접근 방식

**`obsidian_rag.py` 툴을 사용한다.** 직접 파일 접근(glob/grep)은 하지 않는다.

접근 우선순위: `OBSIDIAN_HOST` (Local REST API) → `OBSIDIAN_VAULT_PATH` (직접 파일, fallback)

> **상세 문서**: `docs/agent-guide.md` — "Obsidian RAG" 섹션 참조

### 에이전트 작업 시 Obsidian 활용 방식
- **분석 시작 전** — `obsidian_search`로 관련 도메인 노트 먼저 검색
- **설계 결정 시** — `obsidian_read_note`로 시스템 명세, 이전 분석 참조
- **작업 중 인사이트** — `obsidian_write_note` / `obsidian_append_note`로 기록

---

## 향후 개선 아이디어 (Backlog)

> 우선순위 없음. 설계 전 타당성 검토 필요. README.md에도 동일 내용 기재.

> ✅ **A·B·C·D 완료 (2026-06-08)** — 아래 항목들은 구현되었습니다. 기록 보존을 위해 원문을 남겨둡니다.

### A. IDE식 탭 + 스레드 관리 개선 🖥️ — ✅ 완료

**배경**: 스레드가 조금만 쌓여도 사이드바 관리 어려움. 상단 채팅 탭 영역이 사이드바로 이전된 뒤 빈 공간으로 방치 중.

**아이디어**:
- 상단 빈 탭 바를 IDE처럼 "활성 스레드 탭"으로 활용 (VS Code 스타일)
- `×` 버튼은 **삭제 아닌 닫기** — 탭에서만 제거, 사이드바 목록 보존
- 사이드바: 최근 N개 + 폴더 검색 + 접이식 그룹(진행 중 / 완료 / 보관)
- 탭 overflow 시 스크롤 or `>` 드롭다운 메뉴

**구현 포인트**: `chat.js` 탭 렌더 로직 + `index.html` 레이아웃 수정. 탭 상태는 메모리 유지(새로고침 시 재로드).

---

### B. 워크플로우 패널 컴팩트 + 반응형 레이아웃 📋 — ✅ 완료

**배경**: 그래프 캔버스 화살표·노드가 커서 좁은 사이드바(300px)에 정보량이 너무 적음. 초기 선형 플로우가 좌우로 그려져 공간 낭비.

**아이디어**:
- **반응형**: 사이드바 너비 감지 → 좁음(<350px): 세로 1열 카드 목록, 넓음(≥350px): 2D 그래프
- **컴팩트 노드**: 화살표 축소, 노드 높이 최소화, 완료 노드는 아이콘만 표시로 접기
- **상태 중심 표시**: running/error 노드만 펼침, 나머지는 collapsed
- 구현: `workflow.js` `_layout()` 및 `renderCanvas()` 분기 처리. `ResizeObserver`로 패널 너비 감지.

---

### C. 에이전트 실행 중 창 최소화 UX 🪟 — ✅ 완료 (자동최소화·반투명·끄기 토글)

**배경**: 에이전트가 화면 OCR/이미지 매칭을 수행하는 동안 앱 창이 화면을 가려 심각한 동작 실패. 현재 회피책 없음.

**구현 가능성: 높음** — Electron BrowserWindow API로 즉시 구현 가능.

**옵션 (난이도 낮은 순)**:
1. **자동 최소화** (권장): `agentState=running` SSE → `ipcRenderer.send('minimize-window')` → `main.js`에서 `win.minimize()`. idle 수신 시 `win.restore()`.
2. **뱃지 창 모드**: 100×60px 플로팅 윈도우로 전환. 진행 상태(단계명, 시간)만 표시. 클릭 시 복원.
3. **반투명 모드**: `win.setOpacity(0.15)` — 창은 유지하되 화면 간섭 최소화.

**구현 항목**: `main.js` IPC 핸들러 추가, `chat.js` agentState 이벤트 훅, (옵션 2의 경우) 별도 뱃지 창 `BrowserWindow` 생성.

---

### D. AI 모델 다중 선택 UI 🤖 — ✅ 완료 (헤더 드롭다운, 동적/프리셋)

**배경**: LLM 전환이 "프로파일" 단위만 가능. 같은 엔드포인트에서 모델명만 바꾸려면 `.env` 직접 수정 필요.

**아이디어**:
- 헤더 [LLM 프로파일] 버튼 → 드롭다운: 엔드포인트·모델명·temperature 선택
- 모델 프리셋: 빠른(nano) / 균형(mini) / 정밀(full) / 비전(vision 지원 모델)
- 스레드별 모델 오버라이드 지원
- `GET /v1/models` API로 사내 LLM 모델 목록 동적 조회 (OpenAI 호환 시)

**구현 항목**: `config.py` `MODEL_OVERRIDES` 추가, `/profile` API 확장, `index.html` 드롭다운 UI.

---

### E. 일반 채팅 대화 기억

기본업무 단일 메시지 채팅에서 멀티턴 컨텍스트 유지. `generate()` 내 세션 메시지 리스트 유지, 80% 도달 시 슬라이딩 윈도우 또는 자동 요약.

### F. Electron 패키징 배포

`electron-builder` → `.exe` 인스톨러. Python 환경 `conda-pack` 동봉. `npm run dist` 한 명령 빌드.

---

### G. Office 편집 고도화 로드맵 (2026-06-08 웹조사 반영) 🏢

**배경**: 기존 Office 편집은 ① 로컬+Office설치 → COM, ② Office 없음 → python-docx/openpyxl/pptx 폴백, ③ 클라우드 → 브라우저 진입(office_web_open)+UI Automation 까지 구현됨. 웹 조사로 더 나은 경로를 정리한다.

**조사한 방식 비교 (출처는 커밋 메시지·세션노트 참조)**:

| 방식 | 장점 | 한계 | 폐쇄망 적합 |
|------|------|------|:---:|
| **MS COM** (구현됨) | 로컬 파일 완전충실도(수식·서식·수정추적·메모·PDF) | Windows+Office 설치 필요 | 로컬 ◎ |
| **MS Graph API** | Excel 셀/수식/서식 REST 편집 풍부(세션 기반), 클라우드 파일 직접 | **M365 테넌트+Azure AD OAuth 필요**, Word/PPT 콘텐츠 편집은 미지원(Aspose/Office.js 필요) | M365 연결 시만 △ |
| **OnlyOffice Docs + Document Builder** | **오픈소스·Docker 자체호스팅**, OOXML(docx/xlsx/pptx) 완전 편집, 브라우저 협업 에디터 + **헤드리스 빌더 JS API**(UI 없이 생성·편집·변환) | 서버 호스팅 필요, 빌더 JS 스크립팅 학습, Community 동시 20연결 | **◎ (최적)** |
| **LibreOffice headless / UNO** | 오픈소스·무료·크로스플랫폼, **MS Office 불필요**, 헤드리스 변환(docx→pdf)·UNO 편집 | pyuno가 Python 버전과 일치해야, MS 대비 미세 서식차 | ◎ (오프라인) |
| **Edge UI 자동화 + OCR/UI Automation** (구현됨) | API 없는 어떤 웹 에디터도 가능(최후수단) | 깨지기 쉬움, 느림 | 보편 △ |

**핵심 전략 — 라운드트립이 최선**: 클라우드 문서(SharePoint/OneDrive)를 *브라우저에서 직접 편집*(취약)하지 말고, **다운로드(또는 OneDrive 동기화 로컬 파일) → COM/LibreOffice로 완전충실도 편집 → 업로드** 한다. OneDrive 동기화 폴더면 클라우드 문서가 곧 로컬 파일이라 COM이 바로 동작한다.

**구현 우선순위**:
1. **P1 LibreOffice 변환 엔진** (`office_libre.py`) — MS Office 없는 PC의 고품질 오프라인 폴백. `soffice --headless --convert-to`로 신뢰성 높은 PDF/포맷 변환(`libre_convert` 툴). `word_export_pdf`/`ppt_export_pdf`가 COM 불가 시 자동 폴백. ✅ **완료** (단, 검증 PC에 LibreOffice 미설치 — 설치 환경에서 종단 검증 필요)
2. **P2 라운드트립 프롬프트 전략** — 클라우드 문서는 동기화/다운로드 로컬 경로를 우선 탐색해 COM 편집 후 저장. ✅ **완료** (`office_locate_file` 툴: OneDrive/SharePoint 동기화 폴더 탐색 + 프롬프트 지침)
3. **P3 OnlyOffice Document Server 연동** (폐쇄망 자체호스팅 시) — 헤드리스 Document Builder API로 대량 생성·편집·변환, 브라우저 협업 에디터 임베드. `.env`로 서버 URL 설정. 🔲 **대기**(서버 호스팅 + JWT 서명/콜백 설계 필요 — 라이브 환경 확정 시 진행)
4. **P4 MS Graph Excel 클라이언트** (M365 사용 시) — 클라우드 Excel 셀/수식 REST 편집. ✅ **완료** (`office_cloud.py`: graph_find_item·graph_excel_get_range·graph_excel_set_range, `GRAPH_ACCESS_TOKEN` 게이트, urllib 무의존, 요청구성 mock 검증. Azure AD 토큰 발급은 사용자 환경)

> 참고 출처: ONLYOFFICE DocumentServer/DocumentBuilder(GitHub, api.onlyoffice.com), MS Graph Excel API(learn.microsoft.com/graph), LibreOffice headless/UNO·unoconv.

**⏭ 다음 작업 가이드**: `docs/office-editing-next-steps.md` — 사내 문서 백엔드(네트워크드라이브 / 온프렘 SharePoint / 사내 M365 / OnlyOffice) 확인 절차 + 각 경로별 구현 스케치. **`sbiologics.com`이 일반 O365가 아닌 사내 전용이라, 회사 PC에서 실제 문서 URL/경로를 먼저 확인해야 정확한 경로 결정 가능.** `GRAPH_BASE_URL` 환경변수로 사내 M365 엔드포인트 재정의는 이미 지원.

---

## 폐쇄망 환경 제약

- npm, pip 외부 설치 불가 (네트워크 차단)
- 패키지는 외부망 PC에서 미리 받아 USB로 이동
- conda 환경은 `conda-pack`으로 압축 후 이전
- Playwright 브라우저 바이너리: `python -m playwright install chromium` 실행 후 `%LOCALAPPDATA%\ms-playwright\` 폴더 전체 이전
- Electron 배포는 나중에 (현재는 개발 단계)
- `npx -y`는 외부 다운로드 시도 → `mcp-obsidian`은 외부망에서 `npm pack`으로 챙길 것
