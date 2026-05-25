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
- **UI**: Electron 데스크탑 앱 (채팅 + 빠른 작업 버튼)

---

## 현재 상태

### ✅ 구현 완료

| 항목 | 파일 | 비고 |
|------|------|------|
| Electron 앱 실행 | `electron/main.js` | Python 서버 자동 시작, did-finish-load 후 IPC |
| 채팅 UI | `electron/renderer/` | SSE 스트리밍, 툴 실행 단계 실시간 표시 |
| LLM 프로파일 전환 | `agent/config.py` | OpenAI ↔ 사내 LLM 런타임 전환, UI 버튼 |
| FastAPI 서버 | `agent/server.py` | `/health` `/chat` `/profile` `/tool/test` |
| OCR 툴 | `agent/tools/ocr.py` | Tesseract 5.4, kor+eng, 전체화면 캡처 |
| 데스크탑 제어 툴 | `agent/tools/desktop.py` | 마우스 클릭/이동, 키보드, 창 포커스 (7종) |
| 툴 직접 테스트 패널 | `electron/renderer/tool-test.js` | LLM 없이 `/tool/test` 직접 호출 |
| 환경 설정 | `.env` / `start.ps1` | conda + nvm PATH 자동 설정 |
| Obsidian 세션 관리 | `agent/obsidian_session.py` | 세션 자동 기록, 개발 노트, 백로그, 세션 검색 (4종 툴) |
| 업무 스레드 대화 | `agent/obsidian_session.py` + `agent/server.py` | 사이드바 버튼별 독립 다중 스레드, 멀티턴 대화 이력, 완료 처리, Obsidian 저장 |
| 스레드 API | `agent/server.py` | `/task-config` `/threads/{type}` GET·POST `/threads/{type}/{id}/messages` `/threads/{type}/{id}/close` |

### 🚧 개발 예정 기능 상세

아래 각 기능은 **무엇을 하는지**, **왜 필요한지**, **어떻게 구현할지** 를 명시한다.

---

#### 1. 문서 처리 툴 (`agent/tools/excel.py`, `word.py`, `pdf.py`)

**무엇**: 업무에서 자주 쓰는 Excel·Word·PDF 파일을 에이전트가 직접 읽고 쓴다.

**왜 필요**: 수작업으로 파일을 열고 데이터를 복붙하는 반복 업무를 자동화하기 위해.

**구현 계획**:
```
agent/tools/
├── excel.py   — openpyxl: 셀 읽기/쓰기, 시트 조작, 수식 처리
├── word.py    — python-docx: 단락·표 읽기, 내용 삽입
└── pdf.py     — pdfplumber: 표·텍스트 추출 (읽기 전용)
```

툴 등록 후 `__init__.py`에 추가, 사이드바에 "📄 문서 작업" 버튼 추가.
완료 시 `CLAUDE.md` 현재 상태 업데이트 + `README.md` 기능 표 `✅` 변경 + `docs/agent-guide.md` 툴 목록 추가.

---

#### 2. 웹 자동화 툴 (`agent/tools/web_action.py`)

**무엇**: 인트라넷 웹 페이지(그룹웨어, MES 포털 등)를 Playwright로 자동 조작한다.

**왜 필요**: 브라우저를 직접 조작하는 반복 업무(로그인, 폼 입력, 데이터 수집) 자동화.

**구현 계획**:
```
agent/tools/web_action.py
  - open_browser(url)          — Chromium 실행 또는 기존 창 attach
  - click_selector(selector)   — CSS selector 클릭
  - fill_input(selector, text) — 입력 필드 채우기
  - get_page_text()            — 현재 페이지 텍스트 추출
  - take_screenshot_element(selector) — 특정 요소 스크린샷
```

폐쇄망 주의: Playwright 브라우저 바이너리 별도 이전 필요 (`SETUP.md` 참고).
완료 시 `CLAUDE.md` + `README.md` + `SETUP.md` Playwright 섹션 업데이트.

---

#### 3. 멀티모달 비전 (`agent/tools/vision.py`)

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

#### 4. 일반 채팅 대화 기억 (`agent/memory.py`)

> ⚠️ **스레드 모드는 이미 구현됨**: 사이드바 업무 버튼을 통한 스레드 대화는 Obsidian에 전체 히스토리를 저장하고 이어서 대화 가능. 아래는 **일반 채팅창(스레드 미사용)** 에 대한 기억 기능이다.

**무엇**: 일반 채팅창에서도 이전 대화를 기억하고, 맥락을 참고해 답변한다.

**왜 필요**: 현재 일반 채팅은 매 메시지가 독립적이어서 "아까 했던 거 다시 해줘" 같은 지시가 불가능.

**구현 계획**:
```
agent/server.py 내 generate() 수정
  - messages 리스트를 세션 단위로 유지 (role: user/assistant/tool)
  - 컨텍스트 한계 도달 시 요약 또는 슬라이딩 윈도우 적용
```

완료 시 `CLAUDE.md` + `README.md` 업데이트.

---

#### 5. 업무 워크플로우 (`agent/workflows/`)

**무엇**: 여러 툴을 조합한 실제 사내 업무 시나리오를 자동화한다.

**왜 필요**: 사용자는 "Syncade 배포해줘" 한 마디로 끝내고 싶다. 복잡한 단계를 워크플로우로 캡슐화.

**구현 계획**:
```
agent/workflows/
├── syncade_deploy.py    — 빌드 확인 → 서버 접속 → 배포 → 결과 확인
├── knox_collect.py      — Knox Chat/Mail 수집 모드 활성화
├── obsidian_rag.py      — Obsidian Vault attach → 검색 인덱스 구성
└── unscript_test.py     — Unscript 테스트 에이전트 활성화
```

각 워크플로우는 툴로 등록하여 LLM이 호출 가능하게 한다.
사이드바 "업무 자동화" 버튼이 이 워크플로우를 실행한다.
완료 시 `CLAUDE.md` + `README.md` + `electron/renderer/index.html` 사이드바 업데이트.

---

#### 6. Obsidian RAG 연동

**무엇**: Obsidian Vault를 지식 베이스로 활용해 에이전트가 업무 도메인 지식을 참조한다.

**왜 필요**: 사내 시스템 명세, 프로세스, 과거 분석 내용을 LLM이 검색해서 더 정확한 자동화 수행.

**구현 계획**:
- `OBSIDIAN_HOST` MCP 서버 사용 (Local REST API 기반)
- `.env`의 `OBSIDIAN_VAULT_PATH`, `OBSIDIAN_HOST` 설정
- 폐쇄망 주의: `npm pack`으로 `mcp-obsidian` 패키지 사전 준비

완료 시 `CLAUDE.md` + `README.md` + `SETUP.md` Obsidian 섹션 업데이트.

---

#### 7. Electron 패키징 / 배포 (`electron-builder`)

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
- **pyautogui** — 마우스/키보드 제어 ✅
- **playwright** — 웹 자동화 🔲
- **pywin32** — Windows COM/SAP 자동화 🔲

### 화면 인식
- **pytesseract + Tesseract 5.4** — OCR ✅
- **pillow** — 스크린샷 캡처 ✅
- **opencv-python** — 이미지 매칭 🔲
- **멀티모달 LLM** — 복잡한 화면 해석 🔲

### 문서 처리
- **openpyxl** — Excel 🔲
- **python-docx** — Word 🔲
- **pdfplumber** — PDF 🔲

---

## UI 구성

업무 버튼 클릭 전 (일반 채팅 모드):
```
┌──────────────────────────────────────────────────────┐
│  MES Agent                      [LLM 프로파일] ● 준비됨 │  ← 헤더
├──────────────┬───────────────────────────────────────┤
│  업무 자동화  │                                       │
│  🚀 Syncade  │   채팅 메시지 영역                     │
│  🧠 Obsidian │   (툴 실행 단계 체크리스트 실시간 표시) │
│  🤖 Unscript │                                       │
│  📥 Knox     │                                       │
│  ──────────  │                                       │
│  도구 테스트  │                                       │
│  📷 OCR      │                                       │
│  🖱️ 마우스   ├───────────────────────────────────────┤
└──────────────┤  입력창                    [전송]      │
               └───────────────────────────────────────┘
```

업무 버튼 클릭 후 (스레드 모드):
```
┌──────────────────────────────────────────────────────┐
│  MES Agent                      [LLM 프로파일] ● 준비됨 │  ← 헤더
├──────────────┬───────────────────────────────────────┤
│  업무 자동화  │ 🚀 Syncade | +새시작 | #003 | #002✓ | [완료로 닫기] [✕ 일반] │ ← 스레드 바
│ 🚀 Syncade ● ├───────────────────────────────────────┤
│  🧠 Obsidian │                                       │
│  🤖 Unscript │   채팅 메시지 영역 (선택된 스레드)     │
│  📥 Knox     │                                       │
│  ──────────  │                                       │
│  도구 테스트  │                                       │
│  📷 OCR      │                                       │
│  🖱️ 마우스   ├───────────────────────────────────────┤
└──────────────┤  입력창 (스레드 컨텍스트)  [전송]      │
               └───────────────────────────────────────┘
```

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
│       ├── index.html      ← UI 레이아웃
│       ├── chat.js         ← 채팅 + SSE 스트리밍
│       ├── tool-test.js    ← 도구 직접 테스트 패널
│       └── style.css       ← 다크 테마
├── agent/
│   ├── server.py           ← FastAPI (/health /chat /profile /tool/test /task-config /threads/*)
│   ├── llm.py              ← LLM 클라이언트 팩토리
│   ├── config.py           ← LLM 프로파일 (openai/internal)
│   ├── obsidian_session.py ← Obsidian 세션·스레드 관리, 싱글턴
│   └── tools/
│       ├── __init__.py     ← 툴 레지스트리 + run_tool() (11종)
│       ├── ocr.py          ← 화면 OCR ✅
│       └── desktop.py      ← 마우스/키보드/창 ✅
├── start.ps1               ← 개발 환경 시작 (conda + nvm)
├── .env                    ← 로컬 설정 (git 제외)
├── .env.example            ← 설정 템플릿
├── requirements.txt
└── package.json
```

---

## Obsidian Knowledge Base 연동

### 개요
Obsidian Vault를 로컬 RAG로 활용한다.
Claude가 개발 작업 중 업무 도메인 지식, 시스템 명세, 기존 분석 노트를 참조하기 위해 Vault를 오간다.

### Vault 경로 설정
Vault 경로는 하드코딩하지 않는다. 반드시 `.env` 파일에서 읽어온다.

### 검색 및 접근 방식
**MCP를 우선 사용한다. glob/grep 같은 파일 직접 접근은 사용하지 않는다.**

MCP 서버: `OBSIDIAN_HOST` (Obsidian Local REST API 기반)

MCP가 동작하지 않는 경우에만 파일 직접 접근을 fallback으로 허용한다.

### Claude 작업 시 Obsidian 활용 방식
- **분석 시작 전** — Vault에서 관련 도메인 노트 먼저 검색해서 맥락 파악
- **설계 결정 시** — 기존 시스템 명세, 이전 분석 노트 참조해서 일관성 유지
- **작업 중 인사이트** — 사용자 요청 시 Vault에 노트로 정리해서 저장

---

## 폐쇄망 환경 제약

- npm, pip 외부 설치 불가 (네트워크 차단)
- 패키지는 외부망 PC에서 미리 받아 USB로 이동
- conda 환경은 `conda-pack`으로 압축 후 이전
- Playwright 브라우저 바이너리 별도 이전 필요
- Electron 배포는 나중에 (현재는 개발 단계)
- `npx -y`는 외부 다운로드 시도 → `mcp-obsidian`은 외부망에서 `npm pack`으로 챙길 것
