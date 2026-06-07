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

## 용어 사전 (Glossary)

> 사용자·개발자·에이전트(LLM)가 같은 단어를 같은 의미로 쓰기 위한 기준 문서.
> 새 용어를 도입하거나 UI 명칭을 바꾸면 **반드시 여기에 먼저 반영**한다.

### 핵심 개념 — 계층 관계

**업무 ⊃ 스레드 ⊃ (대화 + 워크플로우)**
하나의 업무는 여러 스레드를 갖고, 각 스레드는 **하나의 대화 + 하나의 워크플로우**를 가진다.
스레드와 워크플로우는 `task_type` + `thread_id` 조합으로 연결된다.

| 용어 | 영어 / 식별자 | 표시 위치 | 저장 위치 | 설명 |
|------|--------------|----------|----------|------|
| **업무** | Task / `task_type` | 사이드바 "업무 자동화" 버튼 | — | 업무 유형. `general`·`syncade`·`obsidian-rag`·`unscript`·`knox` |
| **스레드** | Thread / `thread_id` | 채팅 상단 스레드 바 탭 (`#001`…) | `agent/threads/{task_type}/{thread_id}.md` | 한 업무 안의 독립 작업 단위 = 하나의 대화 세션 |
| **대화** | Conversation / `messages` | 가운데 채팅 영역 | 스레드 `.md` 내부 | 스레드 안의 메시지(user/assistant/tool) 이력 |
| **워크플로우** | Workflow | 우측 패널 워크플로우 탭 | `agent/workflows/{task_type}/{thread_id}.json` | 그 스레드의 작업 단계 체크리스트 |
| **단계** | Step / `step_id` | 워크플로우 카드 1줄 | 워크플로우 `.json` 내부 | 워크플로우의 개별 항목(제목·유형·상태·메모) |

### 화면 구역 (Layout)

| 용어 | 코드 ID | 위치 | 설명 |
|------|---------|------|------|
| **헤더** | `#header` | 최상단 | 타이틀, 컨텍스트 사용량 바, LLM 프로파일 전환, 서버 상태 |
| **사이드바** | `#sidebar` | 왼쪽 | 업무 전환·빠른 작업·도구 테스트·스레드 관리 |
| **채팅 영역** | `#chat-area` | 가운데 | 스레드 바 + 대화 메시지 + 에이전트 상태 바 + 입력창 |
| **스레드 바** | `#thread-bar` | 채팅 상단 | 업무 라벨, 스레드 탭, `완료하기`, `🗑️ 보관함` |
| **우측 패널** | `#right-panel` | 오른쪽 | 워크플로우 / 실행 로그 탭 (드래그 리사이즈·접기) |

### 사이드바 버튼 종류

| 용어 | 코드 클래스 | 설명 |
|------|-----------|------|
| **업무 버튼** | `.task-btn` | 업무 전환. 클릭 시 해당 업무의 최근 스레드가 열림 |
| **빠른 작업** | `.quick-action-btn` | 자주 쓰는 프롬프트. 완성형(OCR·파일)은 원클릭 실행, 템플릿(브라우저·타이핑)은 입력창에 삽입 |
| **도구 테스트** | `.tool-test-btn` | LLM 없이 툴을 직접 호출 (개발·디버깅용) |

### 상태·유형 아이콘

- **단계 상태**(status): ○ 대기(pending) · ⏳ 실행 중(running) · ⏸ 확인 대기(waiting) · ✓ 완료(done) · ✗ 오류(error) · – 건너뜀(skipped)
- **단계 유형**(type): 🤖 자동(auto) · 👁️ 반자동(semi_auto) · ✋ 수동(manual)
- **에이전트 상태**: thinking(생각 중) · running(도구 실행 중) · waiting(사용자 확인 대기) · idle(대기)

### 워크플로우 편집 용어

- **편집모드**: 우측 패널 ✏️ 버튼으로 진입. 단계 제목·유형 수정, 추가(`+ 단계 추가`), 삭제(✕), 드래그앤드롭 순서변경 후 `💾 저장`. **진행 상태(status)는 편집 대상이 아님** — 진행도는 에이전트·실행이 관리.
- **AI 코웍 편집**: 편집모드 없이도 채팅으로 "단계 추가/삭제/순서변경 해줘" 하면 에이전트가 `workflow_add_step`·`update_step`·`remove_step`·`reorder` 툴로 같은 JSON을 편집.
- **워크플로우 삭제**(🗑️): 스레드의 워크플로우 파일을 삭제 → 다시 열면 업무 기본 템플릿으로 초기화.

---

## 기능 현황

### 에이전트 런타임

| 기능 | 상태 | 설명 |
|------|------|------|
| 에이전트 루프 | ✅ | `_MAX_STEPS=40`, 도구 연속 실행, 중단 플래그, 상한 도달 시 '계속' 안내 |
| 긴 호흡·자가복구 | ✅ | 오류 시 근본원인 조사·다른 전략 재시도·선택지 제시 지침 (떠넘기지 않음) |
| SSE 스트리밍 | ✅ | text / tool_start / tool_done / agent_state / context_usage / workflow_update |
| 에이전트 상태 바 | ✅ | thinking → running → waiting → idle, `■ 중단` 버튼 |
| 실행 중 창 가림 회피 | ✅ | running 시 자동 최소화/반투명/끄기 (헤더 토글), idle 시 원복 |
| 컨텍스트 사용량 | ✅ | 헤더 프로그레스 바, 토큰 추정치 표시 |
| 사용자 확인 팝업 | ✅ | `ask_user` 툴 → 선택지 팝업, 텍스트 입력 지원, 300초 타임아웃 |
| LLM 프로파일 전환 | ✅ | OpenAI ↔ 사내 LLM 런타임 전환 |
| AI 모델 선택 | ✅ | 헤더 드롭다운, `/v1/models` 동적 조회 → `.env` 프리셋 폴백, 런타임 모델 전환 |
| 보안 게이트 | ✅ | 원격 Origin 차단 + 토큰 인증(실행마다 자동 생성), 위험명령 차단(force 필요), 보호경로 쓰기 차단·자동백업 |

### 업무 스레드

| 기능 | 상태 | 설명 |
|------|------|------|
| 멀티 스레드 대화 | ✅ | 업무별 독립 스레드, 멀티턴 이력 |
| IDE식 스레드 탭 | ✅ | 상단 열린 스레드 탭 바, X=탭 닫기(사이드바 보존), 탭 클릭 전환 |
| 워크플로우 컴팩트·반응형 | ✅ | 좁은 패널(<360px) 세로 카드(완료 단계 접기) ↔ 넓으면 2D 그래프 자동 전환 |
| Obsidian 저장 | ✅ | 스레드 전체 메시지 `agent/threads/{type}/{id}.md` 저장 |
| 스레드 관리 | ✅ | 완료·보관·복원·영구 삭제 |
| 그래프 캔버스 시각화 | ✅ | BFS 레이아웃 2D 그래프, running 애니메이션·done(녹색)·error(적색 shake), 분기 연결선 |
| 런타임 라우팅 | ✅ | `set_step("done")` 시 다음 노드 자동 running, `branch_output` 분기 선택, 병합 지원 |
| 인터랙티브 노드 컨트롤 | ✅ | 노드 ⋮ 클릭 → 완료·건너뛰기·실행·재시도·분기 선택 패널 |
| 워크플로우 편집모드 | ✅ | 제목·단계 CUD, 드래그앤드롭 순서변경, SVG 분기 연결 CUD, AI 코웍 편집 |
| 워크플로우 저장 | ✅ | `agent/workflows/{type}/{id}.md` YAML frontmatter + Obsidian 저장 |
| 워크플로우 파일 감지 | ✅ | SSE mtime 폴링, 외부 편집 즉시 반영 |
| 실행 로그 탭 | ✅ | 툴별 소요시간·결과 기록 |
| 기본 워크플로우 | ✅ | 파일 없을 때 업무별 기본 단계 템플릿 표시 |

### 툴 (127종)

| 분류 | 수 | 상태 |
|------|-----|------|
| 화면 인식 (OCR, 이미지 매칭, 텍스트 탐색 등) | 10 | ✅ |
| 마우스/키보드 제어 (UAC 앱 포함, 창 관리) | 19 | ✅ |
| 브라우저 자동화 (Playwright Chromium/Edge, Office Online 진입) | 23 | ✅ |
| 프로세스/시스템 (PowerShell, 파일, 프로세스 — 위험명령 가드) | 9 | ✅ |
| 문서 처리 (Excel·Word·PDF·텍스트·마크다운→docx·검토메모·수정추적·PPT·로컬파일탐색) | 15 | ✅ |
| **MS Office 편집 (COM: Word·Excel·PPT 찾아바꾸기·삽입·셀/수식·메모·수정추적·PDF, 라이브러리 폴백)** | 11 | ✅ |
| **LibreOffice 변환 (오프라인 PDF/포맷 변환, MS Office 미설치 폴백)** | 1 | ✅ |
| **클라우드 Office (MS Graph: M365 Excel 셀/수식 REST 편집)** | 3 | ✅ |
| Obsidian PKM (탐색·편집·이동·고급검색·Templater) | 18 | ✅ |
| Obsidian 세션 (작업 이력·노트·백로그) | 4 | ✅ |
| 사용자 확인 (ask_user 팝업) | 1 | ✅ |
| 워크플로우 (init·set_step·add·update·remove·reorder·add_connection·remove_connection) | 8 | ✅ |
| 멀티모달 비전 (전체화면·영역 분석, VISION_ENABLED 게이트) | 2 | ✅ |
| Windows UI Automation (접근성 트리, OCR 없이 Win32 컨트롤 파악) | 3 | ✅ |

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
zipfile + xml.etree             — Office OpenXML 검토메모·수정추적·PPT 파싱 (추가 설치 불필요)
Obsidian Local REST API        — Vault 읽기·쓰기 (fallback: 직접 파일)
VISION_ENABLED=true            — 멀티모달 LLM 비전 게이트 (사내 LLM 지원 여부 선확인)
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
│   └── tools/               — 87종 툴 (MANIFEST 자동 디스커버리)
│       ├── __init__.py      — 자동 등록 레지스트리 (수정 불필요)
│       ├── ocr.py           — 화면 OCR (1종)
│       ├── screen.py        — 화면 인텔리전스 (9종)
│       ├── desktop.py       — 마우스·키보드·창 관리 (19종)
│       ├── browser.py       — Playwright 브라우저 자동화 (22종)
│       ├── process.py       — 프로세스·시스템·파일 (9종)
│       ├── document.py      — Excel·Word·PDF·텍스트·docx변환 (14종)
│       ├── obsidian_rag.py  — Obsidian Vault RAG (18종)
│       ├── interaction.py   — 사용자 확인 팝업 ask_user (1종)
│       ├── workflow.py      — 워크플로우 관리 (8종)
│       ├── vision.py        — 멀티모달 비전 분석 (2종, VISION_ENABLED 게이트)
│       └── ui_automation.py — Windows UI Automation / 접근성 트리 (3종)
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
| GET/POST/DELETE | `/threads/{type}/{id}/workflow` | 워크플로우 조회/저장/삭제 |
| PATCH | `/threads/{type}/{id}/workflow/nodes/{node_id}` | 노드 상태 직접 변경 (인터랙티브 컨트롤) |
| GET | `/threads/{type}/{id}/workflow/events` | 워크플로우 파일 변경 감지 SSE |
| GET | `/workflow/templates/{task_type}` | 업무별 기본 워크플로우 템플릿 조회 |
| PUT | `/workflow/templates/{task_type}` | 기본 템플릿 저장 (Vault `_templates/{type}.md`) |
| POST | `/confirm/{confirm_id}` | 사용자 확인 응답 |
| POST | `/tool/test` | 툴 직접 테스트 |

---

## 개발 이력 & 로드맵

### Phase 0 — 워크플로우 루프 완성 ✅
- [x] task_type·thread_id를 시스템 프롬프트에 주입
- [x] _AUTO_EXEC에 워크플로우 사용 지시 추가
- [x] workflow_set_step 단계 id 고정 (기본 템플릿 최초 1회 영속화)
- [x] LLM 스트리밍 중 즉시 중단 (청크 루프 내 stop 플래그 체크)

### Phase 1 — 워크플로우 편집 ✅
- [x] 워크플로우 단계 클릭 → 결과 상세 드로어
- [x] 빠른 작업 버튼 — 완성형 원클릭 실행 / 템플릿 삽입 구분
- [x] 워크플로우 편집모드 — 단계 CUD·드래그앤드롭·AI 코웍 편집

### Phase 2~4 — 그래프 모델·스토리지·SSE ✅
- [x] 그래프 모델 (WorkflowNode·WorkflowConnection·WorkflowRunState)
- [x] SVG 분기 연결선 (from_output별 색상, 편집모드 연결 CUD UI)
- [x] YAML frontmatter 스토리지 (`.md` 포맷 저장·로드)
- [x] 워크플로우 파일 감지 SSE (`/workflow/events`, mtime 폴링)
- [x] 툴 실패 → error 단계 자동 전환 + 재시도 버튼

### Phase 5 — 파라미터 명시화 ✅
- [x] `wait_for_image`/`wait_for_text` `interval` 파라미터 MANIFEST 노출 → LLM이 폴링 간격 직접 제어
- [x] `mouse_click` `after_delay_ms` 추가 → 클릭 후 안정화 대기

### Phase 6 — 런타임 라우팅 + 그래프 UX ✅
- [x] 런타임 라우팅 엔진: `set_step("done")` 시 다음 노드 자동 running, `branch_output` 분기 선택
- [x] `PATCH /workflow/nodes/{id}` UI 제어 엔드포인트
- [x] BFS 레이아웃 2D 그래프 캔버스 (running 펄스·done·error shake 애니메이션, 흐름 연결선)
- [x] 노드 ⋮ 인터랙티브 컨트롤 패널 (완료·건너뛰기·실행·재시도·분기 선택)
- [x] 진행률 프로그레스 바

### Phase 7 — Obsidian PKM 스레드 ✅
- [x] `obsidian-rag` → `obsidian` (🗂️ Obsidian PKM) 스레드 전환
- [x] 2-tier 탐색: `obsidian_preview_note`·`obsidian_scan_vault`·`obsidian_get_backlinks`·`obsidian_read_section`
- [x] 편집 툴: `obsidian_edit_note`(텍스트 replace)·`obsidian_replace_section`·`obsidian_update_frontmatter`
- [x] 정리 툴: `obsidian_move_note` (wikilink 자동 업데이트)
- [x] 고급 검색: `obsidian_search_advanced` (태그·폴더 필터)
- [x] `obsidian_follow_links` `max_chars_per_note` 파라미터 추가 (토큰 절약)
- [x] PKM 특화 시스템 프롬프트 (탐색 전략 명시)

### Phase 8 — Office 문서 심화 + 비전 + 템플릿 편집 ✅

- [x] Office 문서 검토 읽기 — Word 검토메모(`read_word_comments`)·수정추적(`read_word_track_changes`), Excel 셀메모(`read_excel_comments`), PPT 슬라이드+노트(`read_ppt_content`) (OpenXML 파싱, 추가 설치 불필요)
- [x] 멀티모달 비전 — `analyze_screen`·`analyze_region` (VISION_ENABLED 런타임 게이트, 사용 전 LLM 지원 여부 유저 확인 흐름)
- [x] Windows UI Automation — `ui_list_windows`·`ui_inspect_window`·`ui_find_and_read` (pywin32 접근성 트리, OCR 없이 Win32 컨트롤 파악)
- [x] 기본 워크플로우 템플릿 편집 UI — "📋 기본 템플릿 편집" 버튼, Vault `_templates/{type}.md` 저장
- [x] 패널 접기 UX 버그 수정 — `width:0` 대신 `.collapsed` CSS 클래스, `‹` 버튼이 항상 보이는 26px 스트립 유지

### 다음 단계 (단기)
- [ ] 도메인별 실제 시스템 URL을 .env + 시스템 프롬프트에 반영 (Syncade·Knox)
- [ ] 컨텍스트 80% 도달 시 자동 압축
- [ ] Electron 패키징 → `.exe` 인스톨러
- [ ] COM Interop 오피스 편집 (`win32com`) — 현재 읽기만, 깊은 편집은 미구현

---

## 향후 개선 아이디어 (Backlog)

> 우선순위 없음. 아이디어 단계 — 설계 전 타당성 검토 필요.

### 🖥️ A. 프론트엔드 — IDE식 탭 + 스레드 관리 개선

**배경**: 스레드가 몇 개만 쌓여도 사이드바 관리가 어렵고, 상단 탭 영역(스레드 전환 바)이 현재 사이드바로 이전되어 빈 공간으로 남아 있음.

**아이디어**:
- 상단 탭 영역을 IDE처럼 활용 — 현재 활성 스레드를 탭으로 "열어두기" (VS Code처럼 여러 파일을 탭으로 관리)
- `×` 버튼은 **삭제가 아닌 닫기** — 탭에서만 제거, 스레드는 사이드바 목록에 보존
- 사이드바: 최근 N개 + 검색 + 접이식 그룹 (완료됨 / 보관됨)
- 스레드 드래그앤드롭으로 탭 순서 변경

**검토 포인트**: 탭 bar가 채팅 영역 상단에 고정 → 가로 공간 부족 시 스크롤 or overflow 메뉴 처리 방식 결정 필요.

---

### 📋 B. 워크플로우 패널 — 컴팩트 레이아웃 + 반응형 개선

**배경**: 현재 그래프 캔버스의 화살표·노드가 커서 좁은 사이드바에 표시 가능한 정보량이 적음. 초기 선형 워크플로우는 좌우로 그려져 사이드바 너비를 낭비함.

**아이디어**:
- **반응형 레이아웃**: 사이드바 너비를 감지해 동적으로 방향 전환
  - 넓음(≥350px): 기존 2D 그래프 (좌우 분기 시각화)
  - 좁음(<350px): 선형 세로 목록 (1열 카드, 진행 상태 아이콘만)
- **컴팩트 노드**: 화살표 크기 축소, 노드 높이 감소, 제목 1줄 말줄임
- **상태 중심 표시**: 완료된 노드는 접혀서 아이콘만, running/error는 펼침
- **미니맵**: 전체 그래프 축소 미리보기 (노드 수 많을 때)

**검토 포인트**: Phase 6에서 구현한 BFS 레이아웃 엔진 (`_layout()`) 수정 필요. `workflow.js`의 canvas 렌더링 로직 분기 처리.

---

### 🪟 C. 에이전트 실행 중 대화창 최소화 UX

**배경**: 에이전트가 화면을 직접 조작하는 동안 앱 창이 화면을 가려 OCR·이미지 매칭이 실패하는 심각한 충돌. 현재 회피책: 에이전트가 창을 수동으로 최소화하거나 화면 여백 영역만 사용.

**아이디어 (실현 가능성 검토 필요)**:
1. **자동 최소화**: `agent_state = running` SSE 수신 시 `BrowserWindow.minimize()` 호출. 완료(idle)되면 자동 복원.
2. **뱃지 모드**: 실행 중에는 작은 플로팅 위젯(100×60px, `alwaysOnTop: false`)으로 축소. 진행 상태(단계명, 경과시간)만 표시. 대화 필요 시 클릭하면 전체 창 복원.
3. **반투명 오버레이**: 창을 최소화하지 않고 `opacity: 0.15`의 반투명 상태로 유지. 내용은 보이지 않지만 화면에서 OCR 방해 최소화.
4. **분리 창**: 에이전트 실행창과 대화창을 별도 프로세스로 분리 (더 복잡한 구현).

**우선 검토**: Electron `BrowserWindow` API — `minimize()` / `restore()` / `setOpacity()` / `setAlwaysOnTop()` 모두 지원됨. **옵션 1(자동 최소화)이 가장 단순하고 즉시 구현 가능**. `chat.js`에서 `agentState` 이벤트 수신 시 `ipcRenderer.send('minimize-window')` 호출, `main.js`에서 수신 처리.

---

### 🤖 D. AI 모델 다중 선택 UI

**배경**: 현재 LLM 전환은 "프로파일" 단위 (OpenAI ↔ 사내 LLM)로만 가능. 같은 API 엔드포인트에서 모델만 바꾸고 싶어도 `.env`를 직접 수정해야 함.

**아이디어**:
- 헤더의 [LLM 프로파일] 버튼을 드롭다운 또는 팝오버로 확장
- 구성 항목: 엔드포인트(프로파일), 모델명, 온도(temperature), 최대 토큰
- 사용 패턴별 프리셋: 빠른 응답(nano), 균형(mini), 정밀(full), 코딩 특화
- 스레드별 모델 오버라이드: 특정 스레드는 비전 모델로 실행
- 구현: `config.py`에 `MODEL_OVERRIDES` dict 추가, `/profile` API 확장, UI는 헤더 드롭다운

**검토 포인트**: 사내 LLM 모델 목록을 `/models` 엔드포인트에서 동적으로 조회할 수 있는지 확인 (OpenAI 호환 API는 `GET /v1/models` 지원).

---

### 🗂️ E. 일반 채팅 기억 (컨텍스트 유지)

기본업무 채팅(스레드 없는 단일 메시지)에서도 이전 대화를 기억하고 멀티턴 동작. `server.py` `generate()` 내 세션 메시지 리스트 유지, 80% 컨텍스트 도달 시 슬라이딩 윈도우 또는 자동 요약.

### 📦 F. Electron 패키징 배포

`electron-builder`로 `.exe` 인스톨러 빌드. Python 환경은 `conda-pack` 동봉 또는 설치 가이드 제공. `npm run dist` 한 명령으로 빌드.

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
