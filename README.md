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
│ 업무 자동화  │ 🚀 Syncade 배포  #003 ×  + 새시작 │  │ 감독 📋 워크플로우 🗒️ 로그 › │
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

- **왼쪽 사이드바**: 상단 전역 검색·진행 중 작업 / 중단 업무 유형 전환(스크롤) / 하단 스레드 관리·접이식 개발자 도구(빠른 작업·도구 테스트)
- **가운데 채팅**: 멀티턴 대화, 툴 실행 단계 실시간 표시, 에이전트 상태 바
- **오른쪽 패널**: 감독 탭(현재 목표·단계·도구·승인·근거 요약·phase/role) / 워크플로우 단계 카드 / 실행 로그 탭, 드래그 리사이즈, 접기 가능
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
| **업무** | Task / `task_type` | 사이드바 "업무 자동화" 버튼 | — | 업무 유형. `general`·`syncade`·`obsidian`·`unscript`·`gmp-validation`·`knox` |
| **스레드** | Thread / `thread_id` | 채팅 상단 스레드 바 탭 (`#001`…) | `agent/threads/{task_type}/{thread_id}.md` | 한 업무 안의 독립 작업 단위 = 하나의 대화 세션 |
| **대화** | Conversation / `messages` | 가운데 채팅 영역 | 스레드 `.md` 내부 | 스레드 안의 메시지(user/assistant/tool) 이력 |
| **워크플로우** | Workflow | 우측 패널 워크플로우 탭 | `agent/workflows/{task_type}/{thread_id}.json` | 그 스레드의 작업 단계 체크리스트 |
| **단계** | Step / `step_id` | 워크플로우 카드 1줄 | 워크플로우 `.json` 내부 | 워크플로우의 개별 항목(제목·유형·상태·메모) |

### 화면 구역 (Layout)

| 용어 | 코드 ID | 위치 | 설명 |
|------|---------|------|------|
| **헤더** | `#header` | 최상단 | 타이틀, 컨텍스트 사용량 바, LLM 프로파일 전환, 서버 상태 |
| **사이드바** | `#sidebar` | 왼쪽 | 전역 검색·진행 중 작업·업무 전환·스레드 관리·개발자 도구(빠른 작업·도구 테스트) |
| **채팅 영역** | `#chat-area` | 가운데 | 스레드 바 + 대화 메시지 + 에이전트 상태 바 + 입력창 |
| **스레드 바** | `#thread-bar` | 채팅 상단 | 업무 라벨, 스레드 탭, `완료하기`, `🗑️ 보관함` |
| **우측 패널** | `#right-panel` | 오른쪽 | 감독 / 워크플로우 / 실행 로그 탭 (드래그 리사이즈·접기) |

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
| 중앙 안전 게이트 (G3) | ✅ | 모든 툴 실행 직전 위험도 분류(safe/mutate/destructive). 위험 작업만 승인 팝업(예/항상/아니오), 모델 우회 불가, 타임아웃=거부 |
| 협업모드(코치) | ✅ | 사용자가 직접 작업하는 동안 에이전트가 관찰자로 화면을 보며 비간섭 힌트(항상-위 플로팅 HUD, 포커스 비탈취). 변화율 게이트로 비용 통제, toolless 멀티모달 |
| MCP 클라이언트 | ✅ | 외부 MCP 서버(예: Oracle DB) 도구를 런타임 등록(`mcp_servers.json`). `readOnlyHint` 안전 분류, sync 브릿지. 무설정 무해 |
| 대화 간 장기기억 | ✅ | 과거 대화에서 사실·선호·결정을 자동 추출해 Obsidian 노트에 저장, 새 대화에 관련 기억 주입. `MEMORY_ENABLED`로 on/off |
| 장기기억 후속(도구·UI·비용) | ✅ | `memory_remember`/`forget`/`recall` 명시적 도구 + 헤더 `🧠 기억` 관리 모달(보기·추가·삭제) + `MEMORY_EXTRACT_MODE=close`(스레드 종료 시 1회 일괄 추출로 비용 절감) |
| LLM 프로파일 전환 | ✅ | OpenAI ↔ 사내 LLM 런타임 전환 |
| AI 모델 선택 | ✅ | 헤더 드롭다운, `/v1/models` 동적 조회 → `.env` 프리셋 폴백, 런타임 모델 전환 |
| 보안 게이트 | ✅ | 원격 Origin 차단 + 토큰 인증(실행마다 자동 생성), 위험명령 차단(force 필요), 보호경로 쓰기 차단·자동백업 |
| 입력 에디터 | ✅ | 입력칸 자동 높이 확장 + ⛶ 확대(팝업) 에디터 + Ctrl+Enter·Ctrl+J 줄바꿈 |
| 대화 가독성 | ✅ | 도구 의도 라벨(명령·URL·파일명 노출) + 명령/긴 로그 기본 접힘(에러는 펼침) |
| 사이드바 IA | ✅ | 3영역(상단 검색·진행중 / 중단 스크롤 / 하단 관리·개발자도구), 전역 검색, 진행 중 작업 목록 |

### 업무 스레드

| 기능 | 상태 | 설명 |
|------|------|------|
| 멀티 스레드 대화 | ✅ | 업무별 독립 스레드, 멀티턴 이력 |
| IDE식 스레드 탭 | ✅ | 상단 열린 스레드 탭 바, X=탭 닫기(사이드바 보존), 탭 클릭 전환 |
| 워크플로우 컴팩트·반응형 | ✅ | 좁은 패널(<360px) 세로 카드(완료 단계 접기) ↔ 넓으면 2D 그래프 자동 전환 |
| Obsidian 저장 | ✅ | 스레드 전체 메시지 `agent/threads/{type}/{id}.md` 저장 |
| 스레드 관리 | ✅ | 완료·보관·복원·영구 삭제 |
| 그래프 캔버스 시각화 | ✅ | BFS 레이아웃 2D 그래프, running 애니메이션·done(녹색)·error(적색 shake), 분기 연결선 |
| 워크플로우 시각화 고도화 | ✅ | 팬/줌(anvaka/panzoom `panzoom.min.js`)·동적 디테일(LoD)·노드 인라인 로그·미니맵·그룹(서브워크플로우 접기) |
| 감독 콘솔 검증 | ✅ | 기존 SSE 이벤트를 RunSnapshot 1차 phase/role로 매핑해 감독 탭·HUD에 표시, 순수 reducer + Node fixture로 상태 전이 검증 |
| 런타임 라우팅 | ✅ | `set_step("done")` 시 다음 노드 자동 running, `branch_output` 분기 선택, 병합 지원 |
| 인터랙티브 노드 컨트롤 | ✅ | 노드 ⋮ 클릭 → 완료·건너뛰기·실행·재시도·분기 선택 패널 |
| 워크플로우 편집모드 | ✅ | 제목·단계 CUD, 드래그앤드롭 순서변경, SVG 분기 연결 CUD, AI 코웍 편집 |
| 워크플로우 저장 | ✅ | `agent/workflows/{type}/{id}.md` YAML frontmatter + Obsidian 저장 |
| 워크플로우 파일 감지 | ✅ | SSE fingerprint 폴링(mtime+size+digest), 외부 편집 즉시 반영 |
| 실행 로그 탭 | ✅ | 툴별 소요시간·결과 기록 |
| 기본 워크플로우 | ✅ | 파일 없을 때 업무별 기본 단계 템플릿 표시 |
| GMP 품질평가 업무 | ✅ | `gmp-validation` 업무타입, 7단계 검증 워크플로우, harness 옵트인, CSV fixture 파서, artifact ledger 기록 |

### 툴 (136종)

> LLM API의 `tools` 배열 한계(128)로, 요청마다 `select_tools`가 관련도 상위 ≤128개만 전송합니다(전체 등록은 136).

| 분류 | 수 | 상태 |
|------|-----|------|
| 화면 인식 (OCR, 이미지 매칭, 텍스트 탐색 등) | 10 | ✅ |
| 마우스/키보드 제어 (UAC 앱 포함, 창 관리) | 19 | ✅ |
| 브라우저 자동화 (Playwright Chromium/Edge, Office Online 진입) | 23 | ✅ |
| 프로세스/시스템 (PowerShell, 파일, 프로세스 — 위험명령 가드) | 9 | ✅ |
| 문서 처리 (Excel·Word·PDF·텍스트·마크다운→docx·검토메모·수정추적·PPT·로컬파일탐색) | 15 | ✅ |
| **MS Office 편집 (COM: Word·Excel·PPT 찾아바꾸기·삽입·셀/수식·메모·수정추적·PDF·Active Excel 실시간 연동, 라이브러리 폴백)** | 13 | ✅ |
| **LibreOffice 변환 (오프라인 PDF/포맷 변환, MS Office 미설치 폴백)** | 1 | ✅ |
| **클라우드 Office (MS Graph: M365 Excel 셀/수식 REST 편집)** | 3 | ✅ |
| Obsidian PKM (탐색·편집·이동·고급검색·Templater) | 18 | ✅ |
| Obsidian 세션 (작업 이력·노트·백로그) | 4 | ✅ |
| 업무 타입 관리 (Vault 사용자 정의 업무 타입 추가·삭제) | 2 | ✅ |
| 사용자 확인 (ask_user 팝업) | 1 | ✅ |
| 워크플로우 (init·set_step·add·update·remove·reorder·add_connection·remove_connection·set_group) | 9 | ✅ |
| 멀티모달 화면 (capture_screen 메인루프 이미지 주입·전체화면·영역 분석, VISION_ENABLED 기본 켬) | 3 | ✅ |
| Windows UI Automation (접근성 트리, OCR 없이 Win32 컨트롤 파악) | 3 | ✅ |
| 장기기억 도구 (memory_remember·forget·recall — 명시적 기억/삭제/회수) | 3 | ✅ |

> 상세 툴 목록 → **[CONTRIBUTING.md](CONTRIBUTING.md)**

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


opencv-python + mss            — 이미지 매칭, 고속 스크린샷
pillow                         — 이미지 처리

openpyxl / python-docx / pdfplumber  — 문서 처리
zipfile + xml.etree             — Office OpenXML 검토메모·수정추적·PPT 파싱 (추가 설치 불필요)
Obsidian Local REST API        — Vault 읽기·쓰기 (fallback: 직접 파일)
VISION_ENABLED=true            — 멀티모달 화면 게이트(기본 켬): capture_screen·analyze_* (비전 미지원 모델만 false)
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

### 최초 실행 시 화면

`npm start` 실행 후 앱이 뜨면 헤더 상태 표시가 다음 순서로 바뀝니다.

1. `● 서버 연결 중...` — Python 에이전트 서버(FastAPI)가 뜨는 동안 표시 (최대 약 20초 폴링)
2. `● 준비됨` — 서버 연결 성공. 이 시점에 LLM 프로파일·모델 목록·업무 설정을 불러오고,
   **기본업무(`general`) 탭이 자동으로 열립니다** (`openTask('general')`)
3. 좌측 사이드바에는 기본 6개 업무타입(기본업무·Syncade·Obsidian·Unscript·GMP 검증·Knox) 버튼이 표시됩니다

**`● 서버 연결 실패`가 뜬다면** 흔한 원인은 다음 두 가지입니다.

- **포트 충돌**: 8000번(또는 `.env`의 `AGENT_PORT`) 포트를 다른 프로세스가 이미 사용 중 →
  [문제 해결 — Python 서버 포트 충돌](SETUP.md#python-서버-포트-충돌) 참고
- **conda 환경 미활성화**: `start.ps1`을 거치지 않고 `npm start`만 실행하면 Python 서버가
  뜨지 않습니다 → [SETUP.md — 5단계 실행](SETUP.md#5단계--실행) 순서대로 다시 시도

> 💡 `npm install` 전에 `node -v`로 Node 버전을 확인하세요. `.env.example`의 `NODE_VERSION`과
> 다른 버전이면 네이티브 모듈(Electron) 빌드가 실패할 수 있습니다.

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
│   ├── server.py            — FastAPI 루프(안전게이트·compaction·nudge·plan모드·장기기억) + 모든 엔드포인트
│   ├── llm.py               — LLM 클라이언트 팩토리
│   ├── config.py            — LLM 프로파일 (openai / internal) + 모델 오버라이드
│   ├── memory.py            — 대화 간 장기기억 MemoryStore
│   ├── collaborate.py       — 협업모드 코치(화면 변화감지 + toolless 힌트)
│   ├── mcp_client.py        — MCP 클라이언트(외부 서버 도구 런타임 등록)
│   ├── obsidian_session.py  — 세션·스레드 관리, 기본 업무 타입 + Vault 오버레이
│   ├── core/
│   │   ├── events.py        — SSE 이벤트 타입 상수
│   │   └── compaction.py    — 컨텍스트 compaction 순수 로직(짝 보존)
│   ├── workflow/
│   │   ├── model.py         — Definition/Node/Connection(불변) + RunState(가변) + 마이그레이션
│   │   └── storage.py       — Vault 저장(YAML frontmatter) + 구포맷 마이그레이션
│   └── tools/               — 136종 툴 (MANIFEST 자동 디스커버리)
│       ├── __init__.py      — 자동 등록 레지스트리 (수정 불필요)
│       ├── ocr.py           — 화면 OCR (1종)
│       ├── screen.py        — 화면 인텔리전스 (9종)
│       ├── desktop.py       — 마우스·키보드·창 관리 (19종)
│       ├── browser.py       — Playwright 브라우저 + Office Online 진입 (23종)
│       ├── process.py       — 프로세스·시스템·파일 (9종)
│       ├── document.py      — Excel·Word·PDF·텍스트·docx변환·파일탐색 (15종)
│       ├── office_com.py    — MS Office COM 편집 + Active Excel 실시간 연동 + 폴백 (13종)
│       ├── office_libre.py  — LibreOffice 헤드리스 변환 (1종)
│       ├── office_cloud.py  — MS Graph 클라우드 Excel (3종)
│       ├── obsidian_rag.py  — Obsidian PKM 탐색·편집·이동 (18종)
│       ├── interaction.py   — 사용자 확인 팝업 ask_user (1종)
│       ├── workflow.py      — 워크플로우 관리 (9종)
│       ├── vision.py        — 멀티모달 화면: capture_screen(메인루프 주입)·analyze_* (3종, VISION_ENABLED 기본 켬)
│       ├── ui_automation.py — Windows UI Automation / 접근성 트리 (3종)
│       ├── memory_tools.py  — 장기기억 명시적 도구 remember/forget/recall (3종)
│       ├── task_type.py     — 업무 타입 생성/삭제 (2종)
│       └── _safety.py       — 파괴적 작업 가드 + 위험도 분류 (툴 아님)
├── docs/
│   ├── adr/                 — 아키텍처 결정 기록(ADR-0001·0002)
│   └── backlog/
│       ├── pending/         — 미착수 기능 사양(N·V)
│       └── done/            — 완료 구현 배경 기록(H·I·J·M·O·P·Q·R·S·T·U·W)
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
│   │   ├── obsidian/        — Obsidian PKM 스레드
│   │   ├── unscript/        — Unscript 테스트 스레드
│   │   ├── gmp-validation/  — GMP 기능명세 검증 스레드
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
| GET/POST | `/memory` | 장기기억 조회 / 수동 추가 |
| DELETE | `/memory/{id}` | 장기기억 삭제 |
| POST | `/collaborate/start·tick·stop` | 협업모드(코치) — 목표 설정 / 화면 힌트 틱 / 종료 |
| GET/POST | `/models`, `/models/{name}` | 모델 목록 / 모델 전환 |
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
- [x] 워크플로우 파일 감지 SSE (`/workflow/events`, fingerprint 폴링)
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
- [x] 멀티모달 화면 이해 — `capture_screen`(실제 이미지를 메인 LLM 대화에 주입, 작업자와 호흡)·`analyze_screen`·`analyze_region` (VISION_ENABLED 기본 켬, 캡처 썸네일 채팅 표시)
- [x] Windows UI Automation — `ui_list_windows`·`ui_inspect_window`·`ui_find_and_read` (pywin32 접근성 트리, OCR 없이 Win32 컨트롤 파악)
- [x] 기본 워크플로우 템플릿 편집 UI — "📋 기본 템플릿 편집" 버튼, Vault `_templates/{type}.md` 저장
- [x] 패널 접기 UX 버그 수정 — `width:0` 대신 `.collapsed` CSS 클래스, `‹` 버튼이 항상 보이는 26px 스트립 유지

## 향후 개선 아이디어 (Backlog) — 미착수만

> 완료 기능은 위 **기능 현황** 표가 단일 기록. 완료된 백로그(IDE식 탭·반응형 패널·창 최소화·모델 선택·장기기억·
> 루프 강화 G1~G4·**협업모드·포커스 비탈취·MCP 클라이언트**)는 표 참조. H·I·J 상세는 `docs/backlog/`.

- **Office 문서 base64 멀티모달** 📄 — 회사 DRM 환경 인식 테스트 선행. → [CLAUDE.md K](CLAUDE.md)
- **OpenHands 기능 이식** 🛠 — 좋은 패턴 조사·선별(클린룸 규칙). → [CLAUDE.md L](CLAUDE.md)
- **Electron 패키징 배포** — `electron-builder` `.exe` 인스톨러 + `conda-pack`.
- **Office 편집 백엔드 확정**(P3 OnlyOffice 포함) — 사내 문서 백엔드 확인 후 경로 구현 → [docs/office-editing-next-steps.md](docs/office-editing-next-steps.md)
- 도메인별 실제 시스템 URL을 `.env` + 시스템 프롬프트에 반영 (Syncade·Knox)

---

## 폐쇄망 배포

외부 인터넷이 차단된 환경에서는 패키지를 사전에 준비해야 합니다.

- **Python**: `conda-pack`으로 환경 압축 → USB 이전
- **Node**: `node_modules` 폴더 전체 복사
- **Playwright**: `python -m playwright install chromium` 후 `%LOCALAPPDATA%\ms-playwright\` 전체 이전


자세한 내용 → [SETUP.md — 폐쇄망 이전](SETUP.md#폐쇄망-이전)

---

## 개발 가이드

- 새 툴 추가 → **[CONTRIBUTING.md](CONTRIBUTING.md)**
- 기능 구현 시 문서 업데이트 규칙 → **[CLAUDE.md](CLAUDE.md)**

---

사내 전용 프로젝트 — 외부 배포 금지
