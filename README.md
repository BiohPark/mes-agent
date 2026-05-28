# MES Agent

사내 폐쇄망 환경에서 동작하는 **LLM 기반 업무자동화 데스크탑 에이전트**.

자연어로 지시하면 에이전트가 화면 인식, 키보드/마우스 제어, 브라우저 자동화, 문서 처리 등 반복 업무를 대신 수행합니다.  
진행 상황은 우측 워크플로우 패널에서 실시간으로 확인하고, 언제든 개입하거나 중단할 수 있습니다.

---

## UI 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MES Agent     [██████░ 32k/128k]         [사내 LLM ▾]  ● 준비됨        │
├──────────────┬──────────────────────────────────┬──┬────────────────────┤
│ 업무 자동화  │ 🚀 Syncade 배포  #003 ×  + 새시작 │  │ 📋 워크플로우  🗒️ 로그 › │
│ 💬 기본업무  │              [완료하기] [🗑️ 보관함] │  ├────────────────────┤
│ 🚀 Syncade ● │──────────────────────────────────│  │ 1 ✓ 빌드 확인    🤖 │
│ 🧠 Obsidian  │                                  │  │ 2 ⏳ 서버 접속   🤖 │
│ 🤖 Unscript  │  채팅 메시지 영역                │  │ 3 ○ 패키지 업로드 👁️ │
│ 📥 Knox      │  (툴 실행 체크리스트 실시간 표시)│  │ 4 ○ 배포 실행    👁️ │
│ ──────────   │                                  │  │ 5 ○ 기동 확인    🤖 │
│ 빠른 작업    │                                  │  │ 6 ○ 결과 기록    🤖 │
│ 📷 화면 OCR  │──────────────────────────────────│  │                    │
│ 📂 파일 열기 │ ⚙️ 도구 실행 중...      [■ 중단] │  │                    │
│ 🌐 브라우저  │──────────────────────────────────│  └────────────────────┘
│ ⌨️ 타이핑   │  입력창 (Shift+Enter: 줄바꿈)  전송│    ← 드래그 리사이즈
└──────────────┴──────────────────────────────────┘
```

- **왼쪽 사이드바**: 업무 유형 전환, 빠른 작업 삽입, 도구 직접 테스트
- **가운데 채팅**: 멀티턴 대화, 툴 실행 단계 실시간 표시, 에이전트 상태 바
- **오른쪽 패널**: 워크플로우 단계 카드 / 실행 로그 탭, 드래그 리사이즈, 접기 가능
- **헤더**: LLM 프로파일 전환, 컨텍스트 사용량 바 (80% 경고, 95% 위험)

---

## 기능 현황

### 에이전트 런타임

| 기능 | 상태 | 설명 |
|------|------|------|
| 에이전트 루프 | ✅ | `_MAX_STEPS=20`, 도구 연속 실행, 중단 플래그 |
| SSE 스트리밍 | ✅ | text / tool_start / tool_done / agent_state / context_usage / workflow_update |
| 에이전트 상태 바 | ✅ | thinking → running → waiting → idle, `■ 중단` 버튼 |
| 컨텍스트 사용량 | ✅ | 헤더 프로그레스 바, 토큰 추정치 표시 |
| 사용자 확인 팝업 | ✅ | `ask_user` 툴 → 선택지 팝업, 텍스트 입력 지원, 300초 타임아웃 |
| LLM 프로파일 전환 | ✅ | OpenAI ↔ 사내 LLM 런타임 전환 |

### 업무 스레드

| 기능 | 상태 | 설명 |
|------|------|------|
| 멀티 스레드 대화 | ✅ | 업무별 독립 스레드, 탭 UI, 멀티턴 이력 |
| Obsidian 저장 | ✅ | 스레드 전체 메시지 `agent/threads/{type}/{id}.md` 저장 |
| 스레드 관리 | ✅ | 완료·보관·복원·영구 삭제 |
| 워크플로우 패널 | ✅ | 단계 카드(pending/running/waiting/done/error), 클릭 시 상세 펼침, 드래그 리사이즈 |
| 워크플로우 저장 | ✅ | `agent/workflows/{type}/{id}.json` Obsidian 저장 |
| 실행 로그 탭 | ✅ | 툴별 소요시간·결과 기록 |
| 기본 워크플로우 | ✅ | 파일 없을 때 업무별 기본 단계 템플릿 표시 |

### 툴 (83종)

| 분류 | 수 | 상태 |
|------|-----|------|
| 화면 인식 (OCR, 이미지 매칭, 텍스트 탐색 등) | 10 | ✅ |
| 마우스/키보드 제어 (UAC 앱 포함, 창 관리) | 19 | ✅ |
| 브라우저 자동화 (Playwright Chromium) | 22 | ✅ |
| 프로세스/시스템 (PowerShell, 파일, 프로세스) | 9 | ✅ |
| 문서 처리 (Excel·Word·PDF·텍스트) | 9 | ✅ |
| Obsidian RAG (검색·읽기·쓰기·링크 탐색) | 7 | ✅ |
| Obsidian 세션 (작업 이력·노트·백로그) | 4 | ✅ |
| 사용자 확인 (ask_user 팝업) | 1 | ✅ |
| 워크플로우 (init·set_step) | 2 | ✅ |

> 상세 툴 목록 → **[docs/agent-guide.md](docs/agent-guide.md)**

---

## 기술 스택

```
Electron 42 + Vanilla JS/CSS  — 데스크탑 앱 프레임워크 (Node.js 22)
FastAPI + uvicorn              — 에이전트 서버 (Python 3.11)
openai SDK                     — LLM 연결 (OpenAI 호환, base_url로 사내 LLM 전환)

pyautogui + pynput             — 마우스/키보드 제어 (key_down/up 분리)
pywin32 (SendInput)            — UAC/관리자 앱 제어
pyperclip                      — 클립보드 경유 한글 입력
playwright (Chromium)          — 브라우저 자동화
psutil                         — 프로세스 관리

pytesseract + Tesseract 5.4    — OCR (kor+eng)
opencv-python + mss            — 이미지 매칭, 고속 스크린샷
pillow                         — 이미지 처리

openpyxl / python-docx / pdfplumber  — 문서 처리
Obsidian Local REST API        — Vault 읽기·쓰기 (fallback: 직접 파일)
```

---

## 시작하기

> 상세 설치 방법 → **[SETUP.md](SETUP.md)**

```powershell
# 1. 저장소 클론
git clone https://github.com/your-org/mes-agent.git
cd mes-agent

# 2. 환경 설정
copy .env.example .env
# .env 열어서 LLM API 주소·키, Obsidian Vault 경로 설정

# 3. Python 패키지 설치
conda activate mes-agent
pip install -r requirements.txt
python -m playwright install chromium   # Chromium 브라우저 바이너리

# 4. Node 패키지 설치
npm install

# 5. 실행
.\start.ps1      # conda + nvm PATH 자동 설정
npm start
```

### DevTools 모드

```powershell
$env:DEV_TOOLS=1; npm start
```

---

## 프로젝트 구조

```
mes-agent/
├── electron/
│   ├── main.js              — Electron 메인 (Python 서버 자동 시작, IPC)
│   ├── preload.js           — 보안 컨텍스트 브릿지 (serverPort 노출)
│   └── renderer/
│       ├── index.html       — 3-패널 레이아웃 (사이드바·채팅·워크플로우)
│       ├── chat.js          — 채팅 + SSE 처리 + 에이전트 상태 바 + 중단
│       ├── workflow.js      — 우측 워크플로우 패널 + 실행 로그 + 리사이즈
│       ├── tool-test.js     — 도구 직접 테스트 패널
│       └── style.css        — 다크 테마
├── agent/
│   ├── server.py            — FastAPI 서버 (모든 엔드포인트)
│   ├── llm.py               — LLM 클라이언트 팩토리
│   ├── config.py            — LLM 프로파일 (openai / internal)
│   ├── obsidian_session.py  — 세션·스레드 관리, TASK_CONFIGS 5종
│   ├── core/
│   │   └── events.py        — SSE 이벤트 타입 상수
│   ├── workflow/
│   │   ├── model.py         — Workflow·WorkflowStep 데이터클래스
│   │   └── storage.py       — Obsidian JSON 저장 + 기본 템플릿
│   └── tools/               — 83종 툴 (MANIFEST 자동 디스커버리)
│       ├── __init__.py      — 자동 등록 레지스트리 (수정 불필요)
│       ├── ocr.py           — 화면 OCR (1종)
│       ├── screen.py        — 화면 인텔리전스 (9종)
│       ├── desktop.py       — 마우스·키보드·창 관리 (19종)
│       ├── browser.py       — Playwright 브라우저 자동화 (22종)
│       ├── process.py       — 프로세스·시스템·파일 (9종)
│       ├── document.py      — Excel·Word·PDF·텍스트 (9종)
│       ├── obsidian_rag.py  — Obsidian Vault RAG (7종)
│       ├── interaction.py   — 사용자 확인 팝업 ask_user (1종)
│       └── workflow.py      — 워크플로우 관리 (2종)
├── docs/
│   └── agent-guide.md       — 툴 추가 가이드 + 전체 툴 목록
├── start.ps1                — 개발 환경 시작 (conda + nvm PATH 설정)
├── .env                     — 로컬 설정 (git 제외)
├── .env.example             — 설정 템플릿
├── requirements.txt         — Python 의존성
├── SETUP.md                 — 상세 설치 가이드
└── CLAUDE.md                — 개발 가이드 + 현재 상태 + 로드맵
```

---

## Obsidian Vault 구조

에이전트가 자동으로 생성·관리하는 폴더 구조:

```
Vault/
├── agent/
│   ├── threads/             — 업무 스레드 대화 이력
│   │   ├── general/         — 기본업무 스레드
│   │   ├── syncade/         — Syncade 배포 스레드
│   │   ├── obsidian-rag/    — Obsidian RAG 스레드
│   │   ├── unscript/        — Unscript 테스트 스레드
│   │   ├── knox/            — Knox 수집 스레드
│   │   └── _archive/        — 보관된 스레드
│   ├── workflows/           — 스레드별 워크플로우 JSON
│   │   ├── syncade/
│   │   └── (task_type)/
│   ├── sessions/            — 일반 채팅 세션 자동 기록
│   ├── notes/               — 개발 메모 (add_dev_note)
│   └── plans/
│       └── backlog.md       — 할 일 목록 (add_plan_item)
└── (나머지)                  — 사용자 지식베이스 (RAG 검색 대상)
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |
| POST | `/chat` | 에이전트 채팅 (SSE 스트리밍) |
| POST | `/stop/{request_id}` | 에이전트 중단 |
| GET | `/profile` | LLM 프로파일 조회 |
| POST | `/profile/{name}` | 프로파일 전환 |
| GET | `/task-config` | 업무 타입 설정 조회 |
| GET | `/threads` | 전체 스레드 목록 |
| GET/POST | `/threads/{type}` | 스레드 목록 / 새 스레드 생성 |
| GET | `/threads/{type}/{id}/messages` | 스레드 메시지 |
| DELETE | `/threads/{type}/{id}` | 스레드 보관 |
| POST | `/threads/{type}/{id}/close` | 스레드 완료 |
| GET/POST | `/threads/{type}/{id}/workflow` | 워크플로우 조회/저장 |
| POST | `/confirm/{confirm_id}` | 사용자 확인 응답 |
| POST | `/tool/test` | 툴 직접 테스트 |

---

## 다음 단계 로드맵

### Phase 0 — 즉시 (워크플로우 루프 완성) ✅ 완료
- [x] task_type·thread_id를 시스템 프롬프트에 주입
- [x] _AUTO_EXEC에 워크플로우 사용 지시 추가
- [x] workflow_set_step 단계 id 고정 (기본 템플릿 최초 1회 영속화)
- [x] LLM 스트리밍 중 즉시 중단 (청크 루프 내 stop 플래그 체크)
- [ ] 도메인별 실제 시스템 URL을 .env + 시스템 프롬프트에 반영

### Phase 1 — 이번 주 (실제 업무 연결)
- [ ] Syncade·Knox 실제 접속 URL·경로 구체화
- [x] 워크플로우 단계 클릭 → 결과 상세 드로어
- [x] 실행 로그 스레드 전환 시 초기화
- [x] 빠른 작업 버튼 — 완성형 원클릭 실행 / 템플릿 삽입 구분

### Phase 2 — 2주 내 (안정성)
- [ ] 실제 토큰 수 (LLM 응답 usage 필드)
- [ ] 컨텍스트 80% 도달 시 자동 압축
- [ ] 툴 실패 시 워크플로우 단계 error 자동 표시 + 재시도 버튼

### Phase 3 — 1달 내 (배포·확장)
- [ ] Electron 패키징 → `.exe` 인스톨러
- [ ] 워크플로우 템플릿 라이브러리
- [ ] 멀티모달 비전 (사내 LLM 지원 여부 확인 후)

---

## 폐쇄망 배포

외부 인터넷이 차단된 환경에서는 패키지를 사전에 준비해야 합니다.

- **Python**: `conda-pack`으로 환경 압축 → USB 이전
- **Node**: `node_modules` 폴더 전체 복사
- **Playwright**: `python -m playwright install chromium` 후 `%LOCALAPPDATA%\ms-playwright\` 전체 이전
- **Tesseract**: UB-Mannheim 설치본 오프라인 설치

자세한 내용 → [SETUP.md — 폐쇄망 이전](SETUP.md#폐쇄망-이전)

---

## 개발 가이드

- 새 툴 추가 → **[docs/agent-guide.md](docs/agent-guide.md)**
- 기능 구현 시 문서 업데이트 규칙 → **[CLAUDE.md](CLAUDE.md)**

---

사내 전용 프로젝트 — 외부 배포 금지
