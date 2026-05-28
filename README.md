# MES Agent

사내 폐쇄망 환경에서 동작하는 **LLM 기반 업무자동화 데스크탑 에이전트**.

자연어로 지시하면 에이전트가 화면 인식, 키보드/마우스 제어, 브라우저 자동화, 문서 처리 등 반복 업무를 대신 수행합니다.

---

## 기능 현황

| 기능 | 상태 | 설명 |
|------|------|------|
| 채팅 인터페이스 | ✅ 완성 | SSE 스트리밍, 툴 실행 단계 실시간 표시, 환영 메시지 |
| LLM 프로파일 전환 | ✅ 완성 | OpenAI ↔ 사내 LLM 런타임 전환 |
| 업무 스레드 대화 | ✅ 완성 | 사이드바 버튼별 독립 다중 스레드, 멀티턴 이력, Obsidian 저장 |
| 도구 테스트 패널 | ✅ 완성 | LLM 없이 툴 직접 호출 · 결과 즉시 확인 |
| 화면 OCR | ✅ 완성 | 전체/영역 캡처 후 한·영 텍스트 추출 (Tesseract 5.4) |
| 화면 인텔리전스 | ✅ 완성 | 이미지 템플릿 매칭, 텍스트 좌표 탐색, 이미지/텍스트 출현 대기, 픽셀 색상 (9종) |
| 데스크탑 제어 | ✅ 완성 | 마우스·키보드 완전 제어 (UAC 앱 포함), 클립보드, 창 관리 (18종) |
| 브라우저 자동화 | ✅ 완성 | Playwright Chromium, 클릭·입력·대기·JS·파일업로드·쿠키 (20종) |
| 프로세스/시스템 제어 | ✅ 완성 | PowerShell/CMD 실행, 프로세스 관리, 파일 시스템, 시스템 정보 (9종) |
| 문서 처리 | ✅ 완성 | Excel / Word / PDF / 텍스트 읽기·쓰기 (9종) |
| Obsidian 세션 관리 | ✅ 완성 | 세션 자동 기록, 개발 노트·백로그 저장, 세션 검색 (4종) |
| 멀티모달 비전 | 🔲 개발 예정 | 화면 이미지를 LLM에 전달해 도표·복잡한 UI 인식 |
| 일반 채팅 기억 | 🔲 개발 예정 | 스레드 미사용 시에도 이전 대화 컨텍스트 유지 |
| 업무 워크플로우 | 🔲 개발 예정 | Syncade 배포, Knox 수집 등 실제 업무 시나리오 자동화 |
| Obsidian RAG | 🔲 개발 예정 | Vault 검색 기반 도메인 지식 참조 |
| 앱 패키징 | 🔲 개발 예정 | `electron-builder`로 `.exe` 인스톨러 생성 |

**총 77종 툴** (화면 10 · 데스크탑 18 · 브라우저 20 · 프로세스 9 · 문서 9 · Obsidian RAG 7 · Obsidian 세션 4)

> 상세 구현 계획은 [CLAUDE.md — 개발 예정 기능 상세](CLAUDE.md#-개발-예정-기능-상세)를 참고하세요.

---

## 기술 스택

```
Electron 42              — 데스크탑 앱 프레임워크 (Node.js 22)
FastAPI + uvicorn        — 에이전트 서버 (Python 3.11)
openai SDK               — LLM 연결 (OpenAI 호환, base_url 교체로 사내 LLM 연결)

pyautogui + pynput       — 마우스/키보드 제어
pywin32 (SendInput)      — UAC/관리자 앱 제어
pyperclip                — 클립보드 경유 한글 입력
playwright (Chromium)    — 브라우저 자동화
psutil                   — 프로세스 관리

pytesseract + Tesseract  — OCR (kor+eng)
opencv-python + mss      — 이미지 매칭, 빠른 스크린샷
pillow                   — 이미지 처리

openpyxl                 — Excel 읽기/쓰기
python-docx              — Word 읽기/쓰기
pdfplumber               — PDF 텍스트 추출

Obsidian Local REST API  — Vault 읽기·쓰기 (세션·스레드 저장소)
```

---

## 시작하기

> 상세 설치 방법은 **[SETUP.md](SETUP.md)** 를 참고하세요.

### 빠른 시작

```powershell
# 1. 저장소 클론
git clone https://github.com/your-org/mes-agent.git
cd mes-agent

# 2. 환경 설정
copy .env.example .env
# .env 열어서 LLM API 주소 및 키 설정

# 3. Python 패키지 설치 (mes-agent conda 환경)
conda activate mes-agent
pip install -r requirements.txt

# 4. Playwright 브라우저 바이너리 설치
python -m playwright install chromium

# 5. Node 패키지 설치
npm install

# 6. 실행
.\start.ps1
npm start
```

### 개발 모드 (DevTools 포함)

```powershell
$env:DEV_TOOLS=1; npm start
```

---

## 프로젝트 구조

```
mes-agent/
├── electron/
│   ├── main.js              — Electron 메인 (Python 서버 자동 시작)
│   ├── preload.js           — 보안 컨텍스트 브릿지
│   └── renderer/
│       ├── index.html       — UI 레이아웃 (사이드바 5종 업무 버튼)
│       ├── chat.js          — 채팅 + SSE 스트리밍 (기본업무 자동 진입)
│       ├── tool-test.js     — 도구 직접 테스트 패널
│       └── style.css        — 다크 테마
├── agent/
│   ├── server.py            — FastAPI (/health /chat /profile /tool/test /task-config /threads/*)
│   ├── llm.py               — LLM 클라이언트
│   ├── config.py            — LLM 프로파일 관리 (openai/internal)
│   ├── obsidian_session.py  — Obsidian 세션·스레드 관리 (TASK_CONFIGS 5종)
│   └── tools/
│       ├── __init__.py      — 자동 디스커버리 레지스트리 (수정 불필요)
│       ├── ocr.py           — 전체화면 OCR (1종) ✅
│       ├── screen.py        — 화면 인텔리전스 (9종) ✅
│       ├── desktop.py       — 마우스/키보드/창 관리 (18종) ✅
│       ├── browser.py       — Playwright 브라우저 자동화 (20종) ✅
│       ├── process.py       — 프로세스/시스템 제어 (9종) ✅
│       └── document.py      — Excel/Word/PDF/텍스트 (9종) ✅
├── docs/
│   └── agent-guide.md       — 툴 추가 방법 가이드
├── start.ps1                — 개발 환경 시작 (conda + nvm PATH 설정)
├── .env                     — 로컬 설정 (git 제외)
├── .env.example             — 설정 템플릿
├── requirements.txt         — Python 의존성 (17개 패키지)
├── SETUP.md                 — 상세 설치 가이드
└── CLAUDE.md                — 개발 가이드 (기능 구현 계획 포함)
```

---

## 폐쇄망 배포

외부 인터넷이 차단된 환경에서는 패키지를 사전에 준비해야 합니다.

- **Python**: `conda-pack`으로 환경 압축 → USB 이전
- **Node**: `node_modules` 폴더 전체 복사 또는 `npm ci --prefer-offline`
- **Playwright 브라우저**: `python -m playwright install chromium` 실행 후 `%LOCALAPPDATA%\ms-playwright\` 폴더 전체 이전
- **Tesseract OCR**: UB-Mannheim 설치본 오프라인 설치

자세한 내용은 [SETUP.md — 폐쇄망 이전](SETUP.md#폐쇄망-이전) 참고.

---

## 개발 기여

새 툴 추가 방법은 **[docs/agent-guide.md](docs/agent-guide.md)** 를 참고하세요.
기능 구현 시 **[CLAUDE.md](CLAUDE.md)** 의 문서 자동 업데이트 규칙을 따라주세요.

---

## 라이선스

사내 전용 프로젝트 — 외부 배포 금지
