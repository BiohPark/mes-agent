# MES Agent

사내 폐쇄망 환경에서 동작하는 **LLM 기반 업무자동화 데스크탑 에이전트**.

자연어로 지시하면 에이전트가 화면 인식, 키보드/마우스 제어, 문서 처리 등 반복 업무를 대신 수행합니다.

---

## 기능 현황

| 기능 | 상태 | 설명 |
|------|------|------|
| 채팅 인터페이스 | ✅ 완성 | SSE 스트리밍, 툴 실행 단계 실시간 표시 |
| LLM 프로파일 전환 | ✅ 완성 | OpenAI ↔ 사내 LLM 런타임 전환 |
| 화면 OCR | ✅ 완성 | 전체 화면 캡처 후 한/영 텍스트 추출 (Tesseract 5.4) |
| 데스크탑 제어 | ✅ 완성 | 마우스 클릭/이동, 키보드 입력, 창 포커스 (7종 툴) |
| 도구 테스트 패널 | ✅ 완성 | LLM 없이 툴 직접 호출 · 결과 즉시 확인 |
| Obsidian 세션 관리 | ✅ 완성 | 업무 세션 자동 기록, 개발 노트·백로그 저장, 세션 검색 (4종 툴) |
| 업무 스레드 대화 | ✅ 완성 | 사이드바 버튼별 독립 다중 스레드, 멀티턴 대화 이력, Obsidian 저장 |
| 문서 처리 | 🚧 개발 예정 | Excel / Word / PDF 읽기·쓰기 (`openpyxl`, `python-docx`, `pdfplumber`) |
| 웹 자동화 | 🚧 개발 예정 | Playwright 기반 인트라넷 자동화 (로그인, 폼, 데이터 수집) |
| 멀티모달 비전 | 🚧 개발 예정 | 화면 이미지를 LLM에 전달해 도표·복잡한 UI 인식 |
| 일반 채팅 기억 | 🚧 개발 예정 | 스레드 外 일반 채팅의 이전 대화 컨텍스트 유지 |
| 업무 워크플로우 | 🚧 개발 예정 | Syncade 배포, Knox 수집 등 실제 업무 시나리오 자동화 |
| Obsidian RAG | 🚧 개발 예정 | Vault 검색 기반 도메인 지식 참조 |
| 앱 패키징 | 🚧 개발 예정 | `electron-builder`로 `.exe` 인스톨러 생성 |

> 상세 구현 계획은 [CLAUDE.md — 개발 예정 기능 상세](CLAUDE.md#-개발-예정-기능-상세)를 참고하세요.

---

## 기술 스택

```
Electron 42              — 데스크탑 앱 프레임워크 (Node.js 22)
FastAPI + uvicorn        — 에이전트 서버 (Python 3.11)
openai SDK               — LLM 연결 (OpenAI 호환, base_url 교체로 사내 LLM 연결)
pyautogui                — 마우스/키보드 제어
pytesseract              — OCR (Tesseract 5.4 엔진, kor+eng)
pillow / opencv          — 화면 캡처 및 이미지 처리
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

# 4. Node 패키지 설치
npm install

# 5. 실행
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
│       ├── index.html       — UI 레이아웃
│       ├── chat.js          — 채팅 + SSE 스트리밍
│       ├── tool-test.js     — 도구 직접 테스트 패널
│       └── style.css        — 다크 테마
├── agent/
│   ├── server.py            — FastAPI (/health /chat /profile /tool/test /task-config /threads/*)
│   ├── llm.py               — LLM 클라이언트
│   ├── config.py            — LLM 프로파일 관리
│   ├── obsidian_session.py  — Obsidian 세션·스레드 관리
│   └── tools/
│       ├── __init__.py      — 툴 레지스트리 (11종)
│       ├── ocr.py           — 화면 OCR ✅
│       └── desktop.py       — 마우스/키보드 제어 ✅
├── docs/
│   └── agent-guide.md       — 새 툴 추가 방법
├── start.ps1                — 개발 환경 시작 (conda + nvm PATH 설정)
├── .env                     — 로컬 설정 (git 제외)
├── .env.example             — 설정 템플릿
├── SETUP.md                 — 상세 설치 가이드
└── CLAUDE.md                — 개발 가이드 (기능 구현 계획 포함)
```

---

## 폐쇄망 배포

외부 인터넷이 차단된 환경에서는 패키지를 사전에 준비해야 합니다.

- **Python**: `conda-pack`으로 환경 압축 → USB 이전
- **Node**: `npm pack` / offline mirror 활용
- **Playwright 브라우저**: 별도 바이너리 이전 필요
- **Tesseract OCR**: UB-Mannheim 설치본 오프라인 설치

자세한 내용은 [SETUP.md — 폐쇄망 이전](SETUP.md#폐쇄망-이전) 참고.

---

## 개발 기여

새 툴 추가 방법은 **[docs/agent-guide.md](docs/agent-guide.md)** 를 참고하세요.
기능 구현 시 **[CLAUDE.md](CLAUDE.md)** 의 문서 자동 업데이트 규칙을 따라주세요.

---

## 라이선스

사내 전용 프로젝트 — 외부 배포 금지
