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
| Electron 앱 실행 | `electron/main.js` | Python 서버 자동 시작, IPC server-ready 이벤트 |
| 채팅 UI | `electron/renderer/` | SSE 스트리밍, 툴 실행 단계 실시간 표시, 환영 메시지 |
| 앱 시작 시 기본업무 자동 진입 | `electron/renderer/chat.js` | `initWhenReady()` → `openTask('general')` 자동 호출 |
| LLM 프로파일 전환 | `agent/config.py` | OpenAI ↔ 사내 LLM 런타임 전환, UI 버튼 |
| FastAPI 서버 | `agent/server.py` | `/health` `/chat` `/profile` `/tool/test` `/task-config` `/threads/*` |
| OCR (전체/영역) | `agent/tools/ocr.py` + `screen.py` | Tesseract 5.4, kor+eng, 영역 지정 OCR |
| 화면 인텔리전스 | `agent/tools/screen.py` | 이미지 템플릿 매칭, 텍스트 좌표, 이미지/텍스트 대기, 스크린샷 비교, 픽셀 색상, 창 캡처 (9종) |
| 데스크탑 제어 | `agent/tools/desktop.py` | 마우스(클릭·이동·스크롤·드래그·down/up), 키보드(press·down·up), 클립보드, 창 관리 (19종) |
| 브라우저 자동화 | `agent/tools/browser.py` | Playwright Chromium 싱글턴, 클릭·입력·대기·JS·스크린샷·파일업로드·쿠키 (22종) |
| Obsidian RAG | `agent/tools/obsidian_rag.py` | Vault 전체 검색·읽기·쓰기·추가·태그 조회·링크 순회 (7종), REST API + 파일 fallback |
| 프로세스/시스템 | `agent/tools/process.py` | PowerShell/CMD 실행, 프로세스 관리, 파일 시스템, 시스템 정보 (9종) |
| 문서 처리 | `agent/tools/document.py` | Excel/Word/PDF/텍스트 읽기·쓰기 (9종) |
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
| 워크플로우 편집 툴 | `agent/tools/workflow.py` | `workflow_init`·`set_step`·**`add_step`·`update_step`·`remove_step`·`reorder`** (6종), AI 코웍 편집 |
| 워크플로우 데이터 모델 | `agent/workflow/model.py` + `storage.py` | Vault `agent/workflows/{type}/{id}.json` 저장, **기본 템플릿 최초 1회 영속화로 단계 id 고정** |
| 워크플로우 API | `agent/server.py` | `GET/POST/DELETE /threads/{type}/{id}/workflow` |
| 빠른 작업 버튼 | `electron/renderer/index.html` | OCR·파일은 **완성형 → 원클릭 자동 실행**, 브라우저·타이핑은 템플릿 삽입 후 포커스 |
| SSE 이벤트 상수 | `agent/core/events.py` | TEXT/TOOL_START/TOOL_DONE/CONFIRM/AGENT_STATE/CONTEXT_USAGE/WORKFLOW_UPDATE/DONE/ERROR |

**총 툴 수: 87종** (각 툴 파일의 `MANIFEST` 기준 — 자동 디스커버리로 등록)

| 모듈 | 툴 수 |
|------|-------|
| `ocr.py` | 1 |
| `screen.py` | 9 |
| `desktop.py` | 19 |
| `browser.py` | 22 |
| `process.py` | 9 |
| `document.py` | 9 |
| `obsidian_rag.py` | 7 |
| `interaction.py` | 1 |
| `workflow.py` | 6 |
| `obsidian_session.py` | 4 |

---

### ✅ 완성된 기능 (Phase 0 — 2026-05-29)

| 항목 | 내용 |
|------|------|
| Phase 0 task_type/thread_id 주입 | `server.py generate()` — 시스템 프롬프트에 세션 컨텍스트 삽입, LLM이 workflow 툴 호출 시 올바른 값 사용 |
| `_AUTO_EXEC` 워크플로우 지침 | `obsidian_session.py` — 작업 시작 시 `workflow_init` 강제, 각 단계 `workflow_set_step` 업데이트 지침 |
| TASK_CONFIGS 시스템 프롬프트 보강 | `obsidian_session.py` — 5개 업무별 워크플로우 상세 지침, 브라우저 조작 전략 명시 |
| 태스크별 기본 워크플로우 템플릿 | `agent/workflow/storage.py` — general(4)/syncade(6)/obsidian-rag(4)/unscript(5)/knox(5) 단계 |
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

#### 1. 멀티모달 비전 (`agent/tools/vision.py`)

**무엇**: 화면을 캡처해 이미지 그대로 LLM에 전달하여 도표, 플로우차트, UI 레이아웃을 인식한다.

**왜 필요**: OCR은 텍스트만 추출하지만, SAP/MES 화면처럼 복잡한 UI나 차트는 LLM 비전으로만 해석 가능.

**구현 계획**:
```
agent/tools/vision.py
  - analyze_screen(prompt)     — 전체화면 base64 인코딩 → LLM messages에 image_url 첨부
  - analyze_region(x,y,w,h)    — 특정 영역만 분석
```

사내 LLM의 멀티모달 지원 여부 먼저 확인 필요 (담당자 문의).
완료 시 `CLAUDE.md` + `README.md` 업데이트.

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

**구현 완료**: `agent/tools/obsidian_rag.py` (7종 툴)
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
│       ├── document.py     ← Excel·Word·PDF·텍스트 처리 (9종) ✅
│       ├── interaction.py  ← 사용자 확인 요청 ask_user (1종) ✅
│       └── workflow.py     ← 워크플로우 init·set_step·add/update/remove_step·reorder (6종) ✅
├── start.ps1               ← 개발 환경 시작 (conda + nvm PATH 자동 설정)
├── .env                    ← 로컬 설정 (git 제외)
├── .env.example            ← 설정 템플릿
├── requirements.txt        ← Python 의존성 (17개 패키지)
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

## 폐쇄망 환경 제약

- npm, pip 외부 설치 불가 (네트워크 차단)
- 패키지는 외부망 PC에서 미리 받아 USB로 이동
- conda 환경은 `conda-pack`으로 압축 후 이전
- Playwright 브라우저 바이너리: `python -m playwright install chromium` 실행 후 `%LOCALAPPDATA%\ms-playwright\` 폴더 전체 이전
- Electron 배포는 나중에 (현재는 개발 단계)
- `npx -y`는 외부 다운로드 시도 → `mcp-obsidian`은 외부망에서 `npm pack`으로 챙길 것
