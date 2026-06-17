# MES Agent — Claude 개발 가이드

## ⚡ 문서 자동 업데이트 규칙 (필독)

**기능을 구현하거나 수정할 때마다 반드시 아래 항목을 함께 업데이트해야 한다.**

| 변경 유형 | 업데이트할 파일 |
|-----------|----------------|
| 새 툴 추가 (`agent/tools/*.py`) | `CLAUDE.md` 현재 상태, `README.md` 기능 표, `CONTRIBUTING.md` 툴 목록 |
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
| 개발 하네스(ECC/Claude/Ralph) ✅ | `.claude/` + `.agents/` + `.codex/` + `docs/harness/` | Claude Code 전역 `ecc@ecc` plugin + repo-local `.claude/rules/ecc/{common,python,typescript,web}`를 표준으로 사용. ECC full/manual installer는 중복 skills/hooks 위험 때문에 금지. `ralph-loop` plugin은 Task T처럼 반복 테스트가 명확한 worker 카드부터 사용. 상세: `docs/harness/2026-06-14-ecc-rules-readiness.md` |
| 자동화 테스트 (TDD) | `tests/` + `pytest.ini` + `test.ps1` | unit/integration/smoke 3계층, 268개 테스트, `.\test.ps1` 으로 실행 |
| Electron 앱 실행 | `electron/main.js` | Python 서버 자동 시작, IPC server-ready 이벤트 |
| 채팅 UI | `electron/renderer/` | SSE 스트리밍, 툴 실행 단계 실시간 표시, 환영 메시지 |
| 앱 시작 시 기본업무 자동 진입 | `electron/renderer/chat.js` | `initWhenReady()` → `openTask('general')` 자동 호출 |
| LLM 프로파일 전환 | `agent/config.py` | OpenAI ↔ 사내 LLM 런타임 전환, UI 버튼 |
| FastAPI 서버 | `agent/server.py` | `/health` `/chat` `/profile` `/tool/test` `/task-config` `/threads/*` |
| OCR (전체/영역) | `agent/tools/ocr.py` + `screen.py` | Tesseract 5.4, kor+eng, 영역 지정 OCR |
| OCRProvider 어댑터 (트랙3a 1단계) ✅ | `agent/core/ocr_provider.py` + `ocr.py`·`screen.py` | OCR을 `pytesseract` 직접결합에서 분리 — `OCRProvider`(ABC)·`TesseractProvider`·`get_ocr_provider()`(`OCR_PROVIDER` env, 미지원값 tesseract 폴백). 도구 4곳이 provider 경유 → 향후 UIA/멀티모달로 교체·롤백 가능. tesseract 제거는 후속. 첫 Ralph 루프 실험 산출. 상세: `docs/specs/ocr-provider.md` |
| 화면 인텔리전스 | `agent/tools/screen.py` | 이미지 템플릿 매칭, 텍스트 좌표, 이미지/텍스트 대기(**interval 파라미터 명시화**), 스크린샷 비교, 픽셀 색상, 창 캡처 (9종) |
| 데스크탑 제어 | `agent/tools/desktop.py` | 마우스(클릭·이동·스크롤·드래그·down/up)·**mouse_click after_delay_ms 추가**, 키보드(press·down·up), 클립보드, 창 관리 (19종) |
| 브라우저 자동화 | `agent/tools/browser.py` | Playwright Chromium 싱글턴, 클릭·입력·대기·JS·스크린샷·파일업로드·쿠키 (22종), **전용 단일 스레드 executor로 greenlet 스레드 충돌("Cannot switch to a different thread") 해결**, **포커스 비탈취(백로그 I): open/navigate 시 사용자 foreground 창 복원, `bring_to_front`·`BROWSER_FOCUS_STEAL`** |
| Obsidian PKM (Phase 7 ✅) | `agent/tools/obsidian_rag.py` | 2-tier 탐색(preview/scan/backlinks/section), 편집(edit/replace_section/update_frontmatter), 이동, 고급검색 (16종) |
| 프로세스/시스템 | `agent/tools/process.py` | PowerShell/CMD 실행, 프로세스 관리, 파일 시스템, 시스템 정보 (9종) |
| 문서 처리 + Office 검토 | `agent/tools/document.py` | Excel/Word/PDF/텍스트 읽기·쓰기 + **마크다운→진짜 docx 변환(write_word)**, Word 검토메모·수정추적, Excel 셀메모, PPT 슬라이드 읽기 (15종) |
| 툴 직접 테스트 패널 | `electron/renderer/tool-test.js` | LLM 없이 `/tool/test` 직접 호출 |
| 환경 설정 | `.env` / `start.ps1` | conda + nvm PATH 자동 설정 |
| Obsidian 세션 관리 | `agent/obsidian_session.py` | 세션 자동 기록, 개발 노트, 백로그, 세션 검색 (4종 툴) |
| 동적 업무 타입 관리 (백로그 T) ✅ | `agent/obsidian_session.py` + `agent/tools/task_type.py` + `agent/server.py` + `electron/renderer/chat.js`·`index.html` | 기본 5타입은 `_DEFAULT_TASK_CONFIGS`, 사용자 정의 타입은 Vault `agent/task_types.json` 오버레이로 머지. `task_type_create`/`task_type_remove`(mutate 확인 게이트, 기본 타입 삭제 거부) 2종 추가. `/task-config` 동적 반환 + 사이드바 업무 그룹 동적 렌더링. |
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
| SSE 이벤트 상수 | `agent/core/events.py` | TEXT/TOOL_START/TOOL_DONE/CONFIRM/AGENT_STATE/CONTEXT_USAGE/WORKFLOW_UPDATE/COMPACTION/CONTEXT_TRIM/PLAN/VISION_CAPTURE/TOOL_WAIT/**INJECTED**/DONE/ERROR |
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
| 멀티모달 비전 분석 ✅ | `agent/tools/vision.py` | `analyze_screen`·`analyze_region` — 별도 LLM 호출로 화면을 텍스트 요약. VISION_ENABLED(기본 true) + 멀티모달 LLM 필요 |
| 멀티모달 화면 이해(메인 루프 주입) ✅ | `agent/tools/vision.py` + `agent/server.py` + `chat.js` | `capture_screen` — 화면을 캡처해 **실제 이미지를 메인 에이전트 대화에 user 멀티모달 메시지로 주입**, 메인 LLM이 화면을 직접 보고 이후 턴 맥락으로 활용(작업자와 호흡). `__capture__` 봉투를 루프가 감지→**tool 짝(I1) 보존**(tool은 짧은 텍스트, 이미지는 tool 묶음 종료 후 user 주입), `VISION_CAPTURE` SSE로 채팅에 썸네일 표시. `_estimate_tokens`(M3 타일링 추정)/`_history_to_text`가 이미지 블록 처리(`[화면 이미지]` 평탄화). 이미지 비용·누적·초과는 백로그 M(다이어트·eviction·복구)로 관리. 에이전트 온디맨드 |
| Windows UI Automation ✅ | `agent/tools/ui_automation.py` | `ui_list_windows`·`ui_inspect_window`·`ui_find_and_read` — 접근성 트리 읽기, OCR 없이 Win32 컨트롤 구조 파악 |
| 스레드 사이드바 접이식 그룹 ✅ | `electron/renderer/chat.js` + `index.html` + `style.css` | 탭 → 그룹 접기/펼치기, 스레드 인라인 표시, 그룹별 보관 서브섹션, 빨간 배지 |
| 브라우저 greenlet 스레드 버그 수정 ✅ | `agent/tools/browser.py` | 전용 단일 스레드 executor(`_on_pw_thread`)로 모든 Playwright 핸들러 위임 → "Cannot switch to a different thread" 해결 (웹 조사 실패 수정) |
| 마크다운→진짜 docx 변환 ✅ | `agent/tools/document.py` | `write_word` — 제목·목록·굵게·표를 Word 서식으로 변환한 OOXML .docx 저장. write_file 스키마에 .docx 경고 추가 |
| 긴 호흡·자가복구 에이전트 ✅ | `agent/obsidian_session.py` + `agent/server.py` | `_AUTO_EXEC`/`_AUTONOMOUS_INSTRUCTION`에 끈질긴 문제해결·근본원인 조사·선택지 제시 지침, `_MAX_STEPS` 20→40, 단계 상한 도달 시 '계속' 안내 |
| 실행 중 창 비켜 보기 UX (백로그 C + 감독 HUD) ✅ | `electron/main.js` + `preload.js` + `chat.js` + `index.html` + `electron/renderer/hud.*` | agentState=running 시 기본 `hud`(작게 비켜 보기)로 공용 HUD에 목표·단계·도구·위험 표시, 선택 모드로 자동 최소화/반투명/끄기 유지(헤더 토글, localStorage 저장), idle 시 원복 |
| 모델 선택 드롭다운 (백로그 D) ✅ | `agent/config.py` + `agent/llm.py` + `agent/server.py` + `chat.js` | `/models` 동적 조회(/v1/models, 3s 타임아웃) → .env `LLM_*_MODELS` 프리셋 폴백, 런타임 모델 오버라이드, 헤더 드롭다운 |
| IDE식 스레드 탭 (백로그 A) ✅ | `electron/renderer/chat.js` + `index.html` + `style.css` | 상단 열린 스레드 탭 바, X=탭 닫기(사이드바 보존), 탭 클릭 전환, 보관/삭제 시 탭 동기화 |
| 워크플로우 컴팩트·반응형 (백로그 B) ✅ | `electron/renderer/workflow.js` + `style.css` | ResizeObserver로 패널 폭 감지 → 좁으면(<250px) 세로 컴팩트 카드(완료 단계 접기), 이상이면 2D 그래프(기본 패널폭 300 → 그래프, fit-to-view로 맞춤) |
| MS Office 편집 엔진 (COM + 폴백) ✅ | `agent/tools/office_com.py` | Word(찾아바꾸기·삽입·메모·수정추적수락·PDF)·Excel(셀/수식·범위읽기)·PPT(슬라이드추가·찾아바꾸기·PDF)를 COM으로 구동(완전충실도). 전용 STA 단일스레드 executor, COM 불가 시 python-docx/openpyxl/python-pptx 자동 폴백, 편집 전 자동 백업, OOXML 검증 (11종) |
| Office Online(웹) 편집 진입 ✅ | `agent/tools/browser.py` | `office_web_open` — SharePoint/365 문서를 브라우저로 열고 편집화면 대기+스크린샷. `BROWSER_CHANNEL=msedge`로 실제 Edge 구동. 이후 키보드(Ctrl+H/Ctrl+S)+UI Automation 편집 |
| 보안: 인증·Origin 게이트 (S1/S3) ✅ | `agent/server.py` + `main.js` + `preload.js` + `chat.js` | 원격 Origin 차단 + 토큰(X-Auth-Token/?token) 검증. main.js 실행마다 랜덤토큰 생성, **포트·토큰을 `webPreferences.additionalArguments`로 preload에 전달(샌드박스 안전 — preload에서 `fs`/`path` require 금지, `sandbox:true` 유지)**, 토큰 미설정 시 미강제(dev/test 호환), /health 무인증 |
| 보안: 파괴적 작업 가드 (S2/S4/S5) ✅ | `agent/tools/_safety.py` + `process.py` + `document.py` | 치명적 명령(재귀삭제·포맷·디스크/레지스트리·종료) 차단→force 필요, 시스템 보호경로 쓰기 차단, 기존파일 덮어쓰기 전 자동 백업 |
| 중앙 집중 안전 게이트 (G3 / APPROVE1) ✅ | `agent/tools/_safety.py` + `agent/server.py` + `chat.js`/`style.css` | `classify_risk(safe/mutate/destructive)`를 **루프의 run_tool 직전에서 강제**(모델 force 우회 불가). 균형형: 읽기·관찰·입력형=safe, 쓰기·삭제·셸변경·office편집·네트워크만 확인. 기존 CONFIRM 팝업 재사용(예/항상/아니오), 타임아웃=거부(무인 자동승인 금지), "항상"은 세션 허용목록. tool 짝 보존(I1). `docs/contracts/L1_loop_contract.md` 기준 |
| 컨텍스트 compaction (G1) ✅ | `agent/core/compaction.py` + `agent/server.py` + `agent/core/transcript.py` | 컨텍스트가 임계(`COMPACT_RATIO`, 기본 0.7) 초과 시 루프 진입부에서 자동 압축: 선두 system+최근 N턴(8) 보존, 중간은 LLM 요약(`_summarize_history`, 비스트리밍 1회)으로 만들어 **첫 system 메시지에 병합**(사내 vLLM 호환: 중간 system 생성 금지). **tool_calls↔tool 짝 보존(I1)**, `COMPACTION` SSE 고지, `MAX_COMPACT=3` 상한(I3). `transcript.py`가 nudge·계획승인·끼어들기 같은 런타임 제어 메시지를 저장/표시에서 제외 |
| continuation nudge (G2) ✅ | `agent/server.py` | 모델이 도구 사용 도중 텍스트로 조기 종료하면(`finish_reason!=tool_calls`) 한도(`MAX_NUDGES=2`) 내에서 '계속' 메시지를 주입해 끈질기게 진행. 견고성 게이트: `tool_rounds>0`(잡담 제외)·되묻기(`?` 종결)·사용자 중단 시엔 nudge 안 함. 무한루프 방지(I3), 항상 `DONE` 마감(I4) |
| plan 모드 (G4 / PLAN1) ✅ | `agent/server.py` + `agent/core/events.py` + `chat.js`/`index.html`/`style.css` | `agent_mode='plan'`이면 **계획 먼저 → 승인 → 실행**. 계획 단계엔 `workflow_*`/`ask_user` 외 실행 도구를 구조적으로 차단(프롬프트 의존 X), 계획 완료 시 `plan_approval` CONFIRM(승인/수정/취소)으로 G3 팝업 재사용. 승인 후 실행 진입. 계획=기존 WorkflowDefinition·패널 재사용, 헤더 ⚡자동/📋계획 토글. `PLAN` 이벤트 추가 |
| 대화 간 장기기억 ✅ | `agent/memory.py` + `agent/server.py` | 스레드를 넘는 영속 기억. 사실·선호·결정을 LLM로 추출(`_extract_memories`, 주입식)해 `<vault>/agent/memory/long_term.md`에 dedup 저장, 새 대화 진입 시 키워드 검색(`MemoryStore.search`)으로 관련 기억을 system 프롬프트에 주입. `GET /memory`, `MEMORY_ENABLED` 게이트. (스레드 내 멀티턴은 기존 스레드 히스토리로 이미 동작) |
| 장기기억 후속(도구·UI·비용) ✅ | `agent/tools/memory_tools.py` + `agent/server.py` + `electron/renderer/memory.js` | **① 명시적 도구** `memory_remember`/`memory_forget`/`memory_recall`(3종) — 사용자 "기억해/잊어" 즉시 반영(`_AUTONOMOUS_INSTRUCTION` 안내). **② 관리 UI** 헤더 `🧠 기억` 모달(목록·추가·삭제), `POST /memory`·`DELETE /memory/{id}`. **③ 비용 최적화** `MEMORY_EXTRACT_MODE`(close 기본): 스레드는 `close_thread`에서 1회 일괄 추출(`_extract_and_store`), 단발 요청만 턴 추출 폴백 — 매 턴 LLM 호출 제거 |
| 요청당 툴 서브셋(128 한계) ✅ | `agent/tools/__init__.py` `select_tools` + `agent/server.py` | LLM API는 `tools` 배열을 **최대 128개**로 제한. 등록이 그보다 많으면 요청마다 **모듈 우선순위(core 우선) + 메시지/task_type 관련도**로 ≤`LLM_MAX_TOOLS`(기본 128)만 전송. 기본은 office_cloud(graph_*, 토큰 필요) 드롭, 관련 키워드 시 부스트 포함. `run_tool`·`/tool/test`·전체 등록은 그대로. (회귀: 테스트의 FakeLLM이 128 초과 시 예외) |
| 협업모드(코치) (백로그 H) ✅ | `agent/collaborate.py` + `agent/server.py` + `electron`(HUD) | 사용자가 직접 작업하는 동안 에이전트가 관찰자로 화면을 보며 비간섭 힌트. `/collaborate/start·tick·stop`, **toolless 단발 멀티모달**(`make_hint`)로 실행 도구 구조적 차단. 변화율 게이트(`COLLAB_CHANGE_THRESHOLD`)로 비용 통제. 항상-위 플로팅 HUD(`hud.html`, focusable:false, 포커스 비탈취), 헤더 `🤝 협업` + 목표 입력 바, 클라이언트 30s 폴링 |
| MCP 클라이언트 (백로그 J) ✅ | `agent/mcp_client.py` + `agent/tools/__init__.py` + `agent/server.py` | 외부 MCP 서버(예: Oracle DB) 도구를 런타임 등록(`register_tool` in-place, 전용 asyncio 루프 + `run_coroutine_threadsafe` sync 브릿지, `mcp` SDK 지연 import). `readOnlyHint`→`_risk`를 `classify_risk(risk_hint=)`로 반영(읽기=safe/쓰기=confirm). `mcp_servers.json`(.gitignore, `.example` 제공) + `MCP_ENABLED`. 무설정/미설치 무해. **Obsidian은 기존 유지**(대체 안 함). 실연결은 회사 환경 |
| 컨텍스트 초과 자동 처리·이미지 토큰 다이어트 (백로그 M) ✅ | `agent/tools/vision.py` + `agent/core/{tokens,overflow,compaction}.py` + `agent/config.py` + `agent/server.py` + `chat.js` | 이미지 주입 중 컨텍스트 초과로 채팅이 전면 실패하던 문제를 **5단 방어**로 해결. **M1** 적응형 이미지 다이어트(다운스케일·JPEG·`detail` 동적, 임계 근접 시 low 강등). **M2** `prune_images`로 최신 N개 이미지만 유지(과거=텍스트 자리표시자). **M3** `agent/core/tokens.py` OpenAI 타일링 공식 토큰 추정(이미지 고정 1000토큰 가정 대체, tiktoken 선택). **M4** `agent/core/overflow.py` 400 점진적 복구(prune→강제 compact→재시도, 항상 `DONE` I4, 모델 무관). **M5** `get_context_window`로 모델별 윈도우(known 맵 + `LLM_*_CONTEXT_TOKENS` 오버라이드). 상세: `docs/backlog/M-context-overflow.md` |
| 입력 에디터 개선 (백로그 R) ✅ | `electron/renderer/chat.js` + `index.html` + `style.css` | 입력칸 **자동 높이 확장**(내용 따라 늘어남, 최대 뷰포트 40%서 스크롤) + **⛶ 확대(팝업) 에디터**(장문 작성·Ctrl+Enter 전송·Esc 닫기) + **Ctrl+Enter·Ctrl+J 줄바꿈** 추가(Enter=전송·Shift+Enter=줄바꿈 유지). 빠른작업 템플릿 삽입 시도 auto-grow. 상세: `docs/backlog/done/R-chat-input-editor.md` |
| 대화 가독성: 의도 라벨·로그 접힘 (백로그 S) ✅ | `agent/server.py`(`_intent_label`) + `electron/renderer/chat.js`(`buildToolResult`) + `style.css` | **① 규칙 기반 의도 라벨**: `_AUTO_EXEC`가 모델 예고 문구를 금지(L1 루프 보호)하므로 서버가 도구명+핵심 인자(명령 excerpt·URL 호스트·파일명·selector)로 `tool_start.label` 합성. **② 명령 로그 접힘**: 스크립트(`run_command` 등)·긴 출력(>200자)은 기본 접힘(요약 1줄+토글), 에러는 펼침, 스크립트는 모노 작은폰트. 짧은 결과는 평문 유지. 상세: `docs/backlog/done/S-chat-readability.md` |
| 좌측 프레임 IA 개편 (백로그 P) ✅ | `electron/renderer/index.html` + `style.css` + `chat.js` + `agent/server.py`(`/search`) + `obsidian_session.py`(`search_threads`) | `#sidebar`를 **3영역**(상단 고정 검색·진행중 / 중단 스크롤 업무그룹 / 하단 고정 관리·개발자도구)으로 재구성 → 스레드가 늘어도 **관리 버튼이 화면 밖으로 안 밀림**. 빠른작업·도구테스트는 접이식 **🛠️ 개발자 도구**로 이동. **전역 검색**(`GET /search?q=` substring, 디바운스 드롭다운) + **진행 중 작업(Active runs)**(전 타입 in_progress 평면 목록). 상세: `docs/backlog/done/P-left-frame-ia.md` |
| 워크플로우 시각화 고도화 (백로그 U) ✅ | `electron/renderer/workflow.js` + `vendor/panzoom.min.js` + `style.css` + `index.html` + `chat.js` + `agent/workflow/model.py` + `agent/tools/workflow.py` + `agent/server.py` | **① 팬/줌** — 벤더링 anvaka/panzoom UMD(`vendor/panzoom.min.js`, 무의존, 폐쇄망 USB 반입용)로 그래프 캔버스 휠 줌·드래그 팬 + ⊕⊖⊙ 줌 버튼, 재렌더 간 뷰 보존(`anvaka`에 `reset`/`setTransform`이 없어 `zoomAbs`+`moveTo`로 복원), **최초 렌더 시 `_fitToViewport`로 그래프 전체가 보이도록 축소·중앙정렬**하고 실행/대기 노드가 바뀌면 현재 노드 쪽으로 뷰 보정(⊙=전체 보기). **② 동적 디테일(LoD)** — 줌 배율(<0.7/0.7–1.3/>1.3)에 따라 노드 정보 점진 노출(`lod-low/mid/high`). **③ 노드 인라인 로그** — 도구 실행 로그를 running 노드에 요약 표시(`recordToolLog`, chat.js `tool_done`에서 적재) → 백로그 S 근본 해결. **④ 미니맵** — 전체 그래프 오버뷰 + 뷰포트 사각형, 클릭 이동. **⑤ 그룹/서브워크플로우** — `WorkflowNode.group` 모델 필드 + 신규 `workflow_set_group` 툴, 그룹 박스·접기(pill)·레인 정렬. 하위 호환(group 미존재=빈 문자열). 상세: `docs/backlog/done/U-workflow-visualization.md` |
| 감독 콘솔 검증·RunSnapshot 라벨 ✅ | `electron/renderer/supervisor-state.js` + `workflow.js` + `chat.js` + `index.html` | 감독 상태 reducer를 순수 JS 모듈로 분리해 renderer와 Node fixture가 같은 전이 로직을 사용. 기존 SSE 이벤트를 `planning/executing/observing/verifying/waiting/done/error` phase와 `planner/executor/observer/verifier/safety/orchestrator` role로 매핑하고, 감독 탭·HUD에 `phase/role` 표시. confirm/tool/done/error 전이는 `tests/renderer/supervisor-state.test.js` + `tests/unit/test_supervisor_state_js.py`로 검증. **Track 1C(2026-06-17)**: `tool_done` 시 evidence 누적 ≥2이면 `verifying`/`verifier` 전이 — 결과 확인 단계를 구조적으로 구분. 상세: `docs/harness/cards/supervisor-ui-verification.md` |
| RunSnapshot 영속화 + RunLedger 감사 추적 (Track 1B) ✅ | `agent/workflow/model.py`(`LedgerEntry`) + `agent/workflow/storage.py`(`append_ledger/load_ledger`) + `agent/server.py`(`GET /ledger`, done/error/stop/max_steps 기록) + `electron/renderer/workflow.js`(`_saveSnapshot/_restoreSnapshot`, localStorage) | **① RunSnapshot(localStorage)**: `_supervisorState`의 persistent fields(goal/step/phase/role/agentState/evidence/lastError/contextText)를 `done·error·agent_state·workflow_update` 이벤트 후 자동 저장 → 스레드 전환·새로고침 후 `loadWorkflowForThread()`에서 복원. 실시간 ephemeral fields(currentTool/waitingApproval 등)는 복원 제외. **② RunLedger(JSONL)**: `{thread_id}_ledger.jsonl`에 세션 경계 이벤트(start→done/error/stopped/max_steps) 추적, `LedgerEntry.from_dict()` 역직렬화, 손상 줄 건너뜀. `GET /threads/{type}/{id}/ledger` 엔드포인트. `delete_workflow()`시 ledger도 삭제. 테스트: `tests/unit/test_run_ledger.py` 10개. |
| 도구 타임아웃 안전망·작업 가시성 (백로그 V 1단계) ✅ | `agent/core/timeouts.py` + `agent/server.py` + `agent/tools/office_com.py` + `agent/core/events.py` + `electron/renderer/chat.js`·`style.css` | **무한 행 방지**: 도구별 작은 baseline에서 시작해 단계적으로 타임아웃을 늘려 같은 작업을 더 기다리고, 디스패치 하드 캡(`TOOL_TIMEOUT_CAP`) 도달 시 구조화 오류로 마감(`_run_tool_watched`). office COM은 `OFFICE_COM_TIMEOUT` 워치독+**PID 스코프 킬**(사용자가 연 Office 보호)+executor 재생성+Open 대화상자 억제(`Notify=False`)로 무한 행 제거. **가시성**: 길어지면 `TOOL_WAIT` SSE 내레이션('더 기다리는 중')+경과시간+상태바 현재 도구+중단 강조. 전체 적응형(진행도 탐지·인루프 판단·자동 백그라운드)은 백로그 V 2단계. 출처 클린룸(claw-code MIT, 패턴만). 상세: `docs/adr/0003-adaptive-tool-timeout.md` |
| Adaptive timeout V2 liveness spike ✅ | `agent/core/timeouts.py` + `agent/tools/process.py` + `tests/unit/test_process_liveness.py` | `LivenessObservation`/`classify_liveness()`를 추가하고 `run_command` timeout 경로가 partial stdout/stderr를 관측해 `slow`/`stuck`을 구분. 기존 `툴 실행 오류` 접두와 structured timeout shape는 유지. Office COM kill, background registry, LLM 인루프 판단은 후속 카드로 분리. 상세: `docs/harness/cards/adaptive-timeout-v2-liveness-spike.md` |
| Adaptive timeout V2 인루프 판단 (V-2 Phase 2) ✅ | `agent/core/timeouts.py` + `tests/unit/test_timeout_inloop.py` | `_TOOL_ALTERNATIVES`(도구별·접두별 회복 대안 딕셔너리) + `_lookup_alternatives()`(개별→접두→기본 조회) 추가. `classify_timeout()` → `alternatives` 필드 포함. `timeout_error_text()` → "회복 옵션:\n  1. ...\n  2. ..." 번호 매긴 형식으로 개선 — LLM이 명확히 선택하도록 유도. 테스트 17개 전체 통과. 순수 로직, IO 없음. |
| 하네스 PoC v1 — Executor+Reviewer 2역할 (백로그 N) ✅ | `agent/harness/roles.py`·`orchestrator.py` + `docs/contracts/harness-poc-v1.md` + `agent/server.py`(`_harness_generate`·`_reviewer_call`·`HARNESS_ENABLED`) + `agent/core/events.py`(`HARNESS_ROUND`) + `electron/renderer/chat.js` | **Executor→Reviewer 자기교정 루프**: 역할 정의(`HarnessRole`, EXECUTOR/REVIEWER), `parse_verdict()`(JSON 파싱, 실패=안전 폴백), `run_harness()`(FakeLLM 테스트 가능 순수 오케스트레이터). 서버: `HARNESS_ENABLED=true` + `/chat harness_mode=true`로 활성화(`_harness_generate` 래퍼), `_reviewer_call()`(tools 미전송 I2, 비스트리밍). UI: `harness_round` 이벤트 뱃지("🔍 검증 중"·"↺ 재시도"). 기본 off — 기존 경로 무영향(I6). 계약: `docs/contracts/harness-poc-v1.md`. 테스트 26개 전체 통과. |
| 작업 상태 명확화·작업 중 끼어들기 (백로그 Q) ✅ | `agent/server.py` + `agent/core/events.py` + `electron/renderer/chat.js`·`index.html`·`style.css` | **① 끼어들기**: 실행 중에도 입력칸을 열어 두고(전송 버튼만 비활성) 별도 `↩ 끼어들기` 버튼·Enter로 메시지를 `POST /inject/{request_id}` → `_pending_messages` 큐 적재. `generate()` 루프가 **단계 경계(I1 도구 짝 보존 지점, 중단 확인 직후)에서 드레인**해 `[사용자 끼어들기]` user 메시지로 주입, `INJECTED` SSE로 투명 고지. stop과 구분(작업 유지). **② 상태 강조**: waiting을 "⏳ 당신 차례 — 입력해 주세요"로 색·펄스 강조(`data-state` 클래스). **큐 메커니즘은 백로그 O(외부 원격 제어)가 재사용**. 상세: `docs/backlog/done/Q-agent-state-and-intervention.md` |
| Vault 매개 원격 제어(명령함) (백로그 O) ✅ | `agent/control/inbox.py` + `agent/server.py` | **포트 개방 없이** 동기화되는 Obsidian Vault 파일로 원격 지시·모니터링. 폴러가 `agent/control/inbox.md`의 `- [ ] 명령`을 집어(체크박스=멱등 마커, 처리 시 `- [x]`) 실행하고 `agent/control/status.md`에 결과 누적(newest-first). 활성 러닝이 있으면 **백로그 Q 끼어들기 큐에 합류**(`_pending_messages`), 없으면 `generate(auto_confirm="deny")` **헤드리스 실행**. `auto_confirm`은 G3 게이트에서 UI 라운드트립 없이 즉시 결정 — 무인 환경이라 **위험·쓰기 작업 자동 거부**(GxP 안전, 읽기·관찰만 실행). `CONTROL_ENABLED` opt-in(기본 false)·`CONTROL_POLL_INTERVAL`. (B) LAN 바인딩은 후속. 상세: `docs/backlog/done/O-external-control.md` |

**총 툴 수: 134종** (각 툴 파일의 `MANIFEST` 기준 — 자동 디스커버리로 등록. 단, LLM API 128 한계로 **요청당 `select_tools`가 ≤128개만 전송**)

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
| `workflow.py` | 9 |
| `obsidian_session.py` | 4 |
| `vision.py` | 3 |
| `ui_automation.py` | 3 |
| `office_com.py` | 11 |
| `office_libre.py` | 1 |
| `office_cloud.py` | 3 |
| `memory_tools.py` | 3 |
| `task_type.py` | 2 |

---

> **Phase 0 기반(2026-05-29) ✅ 완료**: task_type/thread_id 주입·`_AUTO_EXEC` 워크플로우 지침·기본 업무 타입 5종·태스크별 기본 템플릿·워크플로우 모델/스토리지/툴/API·우측 패널·상태 바·컨텍스트 바·실행 로그·빠른 작업·SSE 이벤트 상수. (상세는 위 "현재 상태" 표 + `agent/workflow/`·`obsidian_session.py`)
>
> **미착수 항목은 아래 "향후 개선 아이디어(Backlog)"가 단일 목록**(F·G·K·L·N·T·V·W·X·Y). **최우선 핫픽스는 `docs/TRANSFORMATION_PLAN.md` 트랙0**(P1·P2·P3+I1).

---

## 외부 하니스 패턴 도입 시 규칙 (클린룸)

L1 루프 강화는 클린룸 거버넌스 하에 완료됨(G3·G1·G2·G4). 향후 외부 에이전트 하니스 패턴을
도입할 때는 **유출 소스 금지**, ADR(`docs/adr/`) 먼저 → TDD 구현 원칙을 따른다.
**claw-code는 MIT 라이선스로 사용자 확인 완료 — 패턴 참고는 허용하되 코드 복붙은 금지**(2026-06-12, ADR-0003).
다른 출처는 적합성 확인 전까지 금지. 상세: `docs/adr/0002-L1-loop-contract.md`(L1 명세), `docs/adr/0003-adaptive-tool-timeout.md`(타임아웃).

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
├── CLAUDE.md               ← 이 파일 (Claude Code AI 지침 + 구현 상태 SSOT)
├── AGENTS.md               ← 범용 AI agent 코드베이스 오리엔테이션 (짧은 안내)
├── CONTRIBUTING.md         ← 툴 추가 방법 + 전체 툴 목록 (사람 개발자용)
├── USAGE.md                ← 사용자 가이드 (앱 실행·기능·단축키)
├── LICENSE                 ← MIT License
├── SECURITY.md             ← 보안 정책·취약점 보고 절차
├── README.md               ← GitHub용 소개
├── SETUP.md                ← 설치 가이드
├── .github/
│   ├── ISSUE_TEMPLATE/     ← 이슈 양식 (bug_report, feature_request)
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       ├── ci.yml          ← 사외망 CI (GitHub-hosted runner, 전체 테스트)
│       └── ci-internal.yml ← 사내망 CI (self-hosted runner, 전체 + 내부 LLM)
├── docs/
│   ├── adr/                ← 아키텍처 의사결정 기록 (ADR-0001·0002)
│   └── backlog/
│       ├── pending/        ← 미착수 기능 사양 (N·O·Q·T·U)
│       └── done/           ← 완료 구현 배경 기록 (H·I·J·M·P·R·S)
├── electron/
│   ├── main.js             ← Python 서버 자동 시작, 창 생성 + 협업 HUD 창(백로그 H)
│   ├── preload.js          ← contextBridge (serverPort·authToken·협업 HUD 제어 노출). 샌드박스 안전: process.argv(additionalArguments)에서 값 수신, fs/path 미사용
│   ├── hud-preload.js      ← 협업 HUD 창 전용 preload (백로그 H)
│   └── renderer/
│       ├── index.html      ← UI 레이아웃 (3-패널: 사이드바 + 채팅 + 우측 워크플로우)
│       ├── chat.js         ← 채팅 + SSE 스트리밍 + 에이전트 상태 바 + 협업모드 컨트롤러
│       ├── workflow.js     ← 우측 워크플로우 패널 + 실행 로그 탭 + 드래그 리사이즈
│       ├── tool-test.js    ← 도구 직접 테스트 패널
│       ├── memory.js       ← 🧠 장기기억 관리 모달
│       ├── hud.html/hud.js ← 협업 코치 플로팅 HUD (백로그 H)
│       └── style.css       ← 다크 테마
├── agent/
│   ├── server.py           ← FastAPI 루프(generate) + 안전게이트(G3)·compaction(G1)·nudge(G2)·plan모드(G4)·장기기억 + `_intent_label`(S) + 명령함 폴러(O). (/health /chat /stop /inject /memory /collaborate/* /profile /models /confirm /tool/test /task-config /search /threads/* /workflow)
│   ├── control/            ← 백로그 O: Vault 매개 원격 제어(명령함). inbox.py=순수 파싱/마킹/status 포맷, 폴러는 server.py ✅
│   ├── llm.py              ← LLM 클라이언트 팩토리
│   ├── config.py           ← LLM 프로파일 (openai/internal) + 모델 오버라이드
│   ├── memory.py           ← 대화 간 장기기억 MemoryStore (추출/주입/검색) ✅
│   ├── collaborate.py      ← 협업모드 코치: 화면 변화감지 + toolless 힌트 (백로그 H) ✅
│   ├── mcp_client.py       ← MCP 클라이언트: 외부 서버 도구 런타임 등록 + sync 브릿지 (백로그 J) ✅
│   ├── obsidian_session.py ← Obsidian 세션·스레드 관리, 기본 업무 타입 + Vault 오버레이
│   ├── core/
│   │   ├── events.py       ← SSE 이벤트 타입 상수
│   │   ├── compaction.py   ← G1 컨텍스트 compaction 순수 로직(첫 system 병합 + 짝 보존) ✅
│   │   ├── transcript.py   ← 런타임 제어 메시지 저장/표시 필터(트랙0 P1) ✅
│   │   ├── timeouts.py     ← 도구 타임아웃 baseline·escalation·분류 순수 로직(백로그 V 1단계) ✅
│   │   └── ocr_provider.py ← OCR 제공자 어댑터(Tesseract 래퍼, OCR_PROVIDER 전환) 트랙3a 1단계 ✅
│   ├── workflow/
│   │   ├── model.py        ← WorkflowDefinition/Node/Connection(불변) + RunState(가변) + 마이그레이션
│   │   └── storage.py      ← Vault 저장/로드(YAML frontmatter) + 구포맷 자동 마이그레이션
│   └── tools/
│       ├── __init__.py     ← 자동 디스커버리 레지스트리 + select_tools(요청당 ≤128 서브셋) (수정 불필요)
│       ├── ocr.py          ← 전체화면 OCR (1종) ✅
│       ├── desktop.py      ← 마우스·키보드·클립보드·창 관리 (19종) ✅
│       ├── screen.py       ← 화면 인텔리전스: 영역OCR·이미지매칭·텍스트위치·대기·비교·픽셀 (9종) ✅
│       ├── browser.py      ← Playwright 브라우저 자동화 + Office Online 진입 (23종) ✅
│       ├── process.py      ← 프로세스·시스템·파일 관리 (9종) ✅
│       ├── document.py     ← Excel·Word·PDF·텍스트 처리 + 마크다운→docx + office_locate (15종) ✅
│       ├── obsidian_rag.py ← Obsidian PKM: 탐색·편집·이동·Templater (18종) ✅
│       ├── office_com.py    ← MS Office COM 편집(Word·Excel·PPT) + 폴백 (11종) ✅
│       ├── office_libre.py   ← LibreOffice 헤드리스 변환(오프라인 폴백) (1종) ✅
│       ├── office_cloud.py    ← MS Graph 클라우드 Excel 편집(셀/수식 REST) (3종) ✅
│       ├── vision.py        ← 멀티모달 화면: capture_screen(메인루프 이미지 주입)·analyze_screen/region (3종) ✅
│       ├── ui_automation.py ← Windows UI Automation 접근성 트리 읽기 (3종) ✅
│       ├── memory_tools.py  ← 명시적 장기기억 도구 remember/forget/recall (3종) ✅
│       ├── _safety.py       ← 파괴적 작업 가드 + G3 위험도 분류(classify_risk) — 툴 아님
│       ├── interaction.py  ← 사용자 확인 요청 ask_user (1종) ✅
│       └── workflow.py     ← 워크플로우 init·set/add/update/remove_step·reorder·add/remove_connection·set_group (9종) ✅
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

> **상세 문서**: `CONTRIBUTING.md` — "Obsidian RAG" 섹션 참조

### 에이전트 작업 시 Obsidian 활용 방식
- **분석 시작 전** — `obsidian_search`로 관련 도메인 노트 먼저 검색
- **설계 결정 시** — `obsidian_read_note`로 시스템 명세, 이전 분석 참조
- **작업 중 인사이트** — `obsidian_write_note` / `obsidian_append_note`로 기록

---

## 향후 개선 아이디어 (Backlog) — 미착수만

> **완료 항목은 위 "현재 상태" 표가 단일 기록**(중복 방지). 완료된 백로그 — A·B·C·D·E·H·I·J·M·P·Q·R·S·U 등 — 은 표 참조. 상세 설계·구현 기록은 `docs/backlog/done/` 참조.

> **설계 원칙 — 외부 서비스 Config 분리**: LLM API(`LLM_*`)·SharePoint/M365(`GRAPH_*`, `SHAREPOINT_*`)·외부 SaaS 설정은 각각 별도 `.env` 블록으로 관리한다. 회사 PC(폐쇄망)가 기본 배포 환경이지만, 동일 코드가 개발 환경(홈PC, 외부 API)에서도 동작하도록 설계한다. **폐쇄망 여부는 feature 제거 이유가 아니라 config 선택 이유다.**

### F. Electron 패키징 배포 🔲

`electron-builder` → `.exe` 인스톨러. Python 환경 `conda-pack` 동봉. `npm run dist` 한 명령 빌드. 완료 시 `README.md`·`SETUP.md` 배포 섹션 갱신.

### G. Office 편집 고도화 로드맵 🏢 — 대부분 완료, P3만 대기

> P1 LibreOffice 변환(`office_libre.py`)·P2 라운드트립 프롬프트(`office_locate_file`)·P4 MS Graph Excel(`office_cloud.py`)은 ✅ 완료(현재 상태 표). 아래 비교표·전략은 **P3(OnlyOffice) 설계 참고용**으로 남긴다.

**방식 비교**:

| 방식 | 장점 | 한계 | 자체호스팅 적합 |
|------|------|------|:---:|
| **MS COM** (구현됨) | 로컬 파일 완전충실도(수식·서식·수정추적·메모·PDF) | Windows+Office 설치 필요 | 로컬 ◎ |
| **MS Graph API** (구현됨) | Excel 셀/수식 REST 편집(세션 기반), 클라우드 파일 직접 | **M365+Azure AD OAuth 필요**, Word/PPT 콘텐츠 편집 미지원 | M365 연결 시만 △ |
| **OnlyOffice Docs + Document Builder** | 오픈소스·Docker 자체호스팅, OOXML 완전 편집, 헤드리스 빌더 JS API | 서버 호스팅·JWT 설계 필요 | **◎ (P3 후보)** |
| **LibreOffice headless** (구현됨) | 오픈소스·MS Office 불필요, 헤드리스 변환 | MS 대비 미세 서식차 | ◎ (오프라인) |
| **Edge UI 자동화** (구현됨) | API 없는 웹 에디터도 가능(최후수단) | 깨지기 쉬움·느림 | 보편 △ |

**핵심 전략(라운드트립)**: 클라우드 문서를 브라우저 직접 편집(취약) 대신 **로컬(다운로드/OneDrive 동기화) → COM/LibreOffice 완전충실도 편집 → 업로드**.

**P3 OnlyOffice Document Server** 🔲 대기 — 폐쇄망 자체호스팅 시 헤드리스 Document Builder로 대량 생성·편집·변환. 서버 호스팅 + JWT 서명/콜백 설계 필요(라이브 환경 확정 시).

**⏭ 가이드**: `docs/backlog/pending/office-editing-next-steps.md` — **`sbiologics.com`이 사내 전용이라 회사 PC에서 실제 문서 URL/경로 확인 선행.** `GRAPH_BASE_URL`로 사내 M365 엔드포인트 재정의 지원.

### K. Office 문서 base64 멀티모달 📄 — 🔲 미착수

Office 문서를 base64로 멀티모달 LLM에 직접 보내 읽히는 경로(`capture_screen` 주입 패턴을 문서로 확장). `vision.py` 패턴 직접 재사용.
**선행 확인**: ① 사내 LLM 멀티모달 지원 여부 — 미지원 시 `.env`의 `VISION_*` 설정으로 외부 API(OpenAI) 전환 후 즉시 적용 가능. ② DRM 바이트 접근 제한은 확인 필요하나 블로커로 간주하지 않는다.

### L. OpenHands 기능 이식 🛠 — 🔲 대기 (조사 중심)

오픈소스 자율 에이전트 OpenHands의 좋은 패턴 조사·선별 이식. 후보: 이벤트 스트림/상태머신, 마이크로에이전트(지식 주입),
샌드박스 런타임, 구조화된 브라우징 관찰, 컨덴서(메모리 압축—기존 G1과 비교). **출처 governance(클린룸, `docs/CLAW_PORT_PLAN.md`) 준수.**

---

> **에픽 N·O·T·V** 상세 설계·확인사항은 각 `docs/backlog/pending/{N,O,T,V}-*.md`.
> **PO 추천 시퀀스**: **트랙0 핫픽스(P2→P1→W)** → **T**(Vault 영속 업무타입) → **O**(원격 제어) → **V-2단계**(타임아웃 고도화) → **N**(멀티에이전트, L과 통합). X·Y는 보안/회사PC 선검증 후.
> **의존성**: Q↔O(메시지 큐) · P↔T(사이드바 동적화) · N↔L(이벤트 스트림).

### N. 하네스(멀티에이전트 역할) 모드 🤖🤖 — 🔬 리서치·PoC 우선

단일 `generate()` 루프를 역할 분리(Planner/Executor/Reviewer)로. 오케스트레이터가 역할별 서브-루프(전용 프롬프트 + `select_tools` 서브셋 + 공유 RunState/Vault)를 호출. 참조 HarnessLab/claw-code-agent는 **라이선스·클린룸 적합성 확인 후** 패턴만 참고(계약서→TDD). L(OpenHands)과 이벤트 스트림 통합 검토. PoC 스파이크(역할 2개)로 가치 검증. 상세: `docs/backlog/pending/N-harness-mode.md`.

### O. 외부 기기 지시·모니터링(원격 제어) 📱 — ✅ (A)안 완료 (현재 상태 표 참조)

폰/다른 PC에서 작업 지시+진행 확인. **(A) Vault 매개 명령함** ✅ 완료(`agent/control/inbox.md` 폴링 — 포트 개방 없이 동기화로 원격, 백로그 Q 큐 재사용, 무인 위험작업 자동 거부). **(B) LAN 바인딩+인증 강화** 🔲 후속: `host=0.0.0.0` 옵트인 + Origin 허용목록 + 토큰 영속화, `LAN_ENABLED=true`로 활성화. 상세: `docs/backlog/done/O-external-control.md`.

### T. 동적 업무 타입 관리(AI 대화로 추가/제거) 🧩 — ✅ 완료

`_DEFAULT_TASK_CONFIGS` + Vault `agent/task_types.json` 오버레이 + 신규 도구 `task_type_create/remove`(확인 게이트) + `/task-config` 동적 반환 + 사이드바 업무 그룹 동적 렌더링까지 완료. 기본 5타입 삭제는 차단. 상세: `docs/backlog/done/T-dynamic-task-types.md`.

### V-2단계. 적응형 타임아웃 고도화 🔲

V-1단계(완료) 위에: 진행도(liveness) 탐지(CPU/stdout/창 응답성) → 에이전트 인루프 판단(스턱 시 구조화 결과 LLM 환류) → 자동 백그라운드 디태치(정당히 긴 작업은 SSE 비블록) → baseline 적응 학습(p50/p90 누적 보정). 상세: `docs/backlog/pending/V-adaptive-tool-timeout.md`.

### W. 설정 정리·모델 출처 표기 (트랙0 P3·I1) ✅

> **완료 (2026-06-16)**: `.env.example` LLM/Office/Vision 블록 분리, COMPACT_RATIO 0.7, 모델 드롭다운 `loadModels()`에 `source` title 표시 (`chat.js`). 상세: `docs/TRANSFORMATION_PLAN.md` 트랙0 P3·P2·I1.

`.env` 그룹핑(LLM/Office/외부SaaS 블록 분리) + 기본값으로 슬림화 + 전문가 섹션 분리. 모델 드롭다운에 출처(`/v1/models` 동적 vs `.env` 프리셋) 표시. 저비용·같은 표면. 상세: `docs/TRANSFORMATION_PLAN.md` 트랙0.

### X. 창 UX 고도화 (트랙0 I2) 🔲 — Electron 수동확인, 보안 검토 선행

실행 중 채팅창 드롭 방지: 기본 busy_mode `minimize`→`translucent`(반투명). "비켜보기" 팝업 확대 + 상세 동작 설명. Codex식 윈도우 네이티브 컴퓨터 사용 UX 모방(동작 중 모니터 테두리·작업권 회수·ESC 중지). **작업권 회수·전역 ESC는 입력 가로채기 리스크 → 보안 검토 후.** 백로그 C 후속. 상세: `docs/TRANSFORMATION_PLAN.md` 트랙0.

### Y. Office365 로그인·로컬 작업 강화 (트랙0 I3) 🔲 — 회사 PC 선검증 필수

Office365 로그인창 뜨나 로그인 시도 안 함 → 자격증명 사전 주입 방안. 스크린샷 인식 취약 → API 사용 재확인, 어려우면 **로컬 다운로드→`office_com` 편집(집계·분석·편집) 적극 보완**(폐쇄망 폴백 1순위, 신규의존 0). **평문 자격증명 .env 저장은 GxP/보안 리스크 → DPAPI/자격증명관리자 검토 전 보류.** 백로그 G/K 연계. 상세: `docs/TRANSFORMATION_PLAN.md` 트랙0.

### (대기) Office 편집 백엔드 확정

사내 문서 백엔드(네트워크 드라이브 / 온프렘 SharePoint / 사내 M365 / OnlyOffice) 확인 후 경로 구현 → G·`docs/office-editing-next-steps.md`. 회사 PC 확인 선행.

---

## 설치·배포 환경 특이사항

- npm, pip 외부 설치 불가 (네트워크 차단)
- 패키지는 외부망 PC에서 미리 받아 USB로 이동
- conda 환경은 `conda-pack`으로 압축 후 이전
- Playwright 브라우저 바이너리: `python -m playwright install chromium` 실행 후 `%LOCALAPPDATA%\ms-playwright\` 폴더 전체 이전
- Electron 배포는 나중에 (현재는 개발 단계)
- `npx -y`는 외부 다운로드 시도 → `mcp-obsidian`은 외부망에서 `npm pack`으로 챙길 것
- MCP 클라이언트(백로그 J): Python `mcp` 패키지 + Oracle MCP 서버(python-oracledb 기반 권장)를 USB 사전반입. 미설치여도 앱은 동작(지연 import)

대전환 프로젝트 진행 시 docs/TRANSFORMATION_PLAN.md를 먼저 읽을 것
