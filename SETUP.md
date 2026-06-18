# 설치 및 환경 설정 가이드

## 사전 요구사항

| 소프트웨어 | 버전 | 비고 |
|-----------|------|------|
| Windows | 10 / 11 (64비트) | |
| Miniconda | 최신 | Python 3.11 환경 생성용 |
| Node.js | 22.x | nvm-windows 권장 |
| Tesseract OCR | 5.x | UB-Mannheim 설치본 (선택, 기본 UIA 전환으로 생략 가능) |
| Git | 최신 | 저장소 클론용 |

---

## 1단계 — Node.js 설치 (nvm-windows)

1. [nvm-windows](https://github.com/coreybutler/nvm-windows/releases) 에서 `nvm-setup.exe` 다운로드 후 설치
2. PowerShell 재시작 후:

```powershell
nvm install 22
nvm use 22
node --version   # v22.x.x 확인
```

---

## 2단계 — Python 환경 생성

```powershell
conda create -n mes-agent python=3.11 -y
conda activate mes-agent
pip install -r requirements.txt
```

### OCR 및 UI Automation (UIA) 설정

mes-agent는 기본적으로 Windows UI Automation(`OCR_PROVIDER=uia`)을 사용하여 화면 내 텍스트와 좌표를 긁어옵니다. 따라서 **별도의 Tesseract OCR 엔진을 설치할 필요가 없습니다.**

만약 레거시 OCR(Tesseract) 엔진을 사용해야 하는 특수 환경의 경우에만 다음 단계를 수행하세요:

1. [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) 에서 `tesseract-ocr-w64-setup-*.exe` 다운로드 및 설치.
2. 설치 시 **Korean** 언어 팩 체크 (Korean.traineddata).
3. 설치 경로 및 환경변수를 `.env`에 반영:
   ```ini
   OCR_PROVIDER=tesseract
   OCR_TESSERACT_CMD=D:/Program Files/Tesseract-OCR/tesseract.exe
   ```

### Playwright 브라우저 바이너리 설치

Playwright Python 패키지는 `pip install -r requirements.txt`로 설치되지만,
실제 Chromium 브라우저 바이너리는 별도로 다운로드해야 합니다:

```powershell
conda activate mes-agent
python -m playwright install chromium
```

> **주의**: `playwright install chromium` (CLI) 또는 `npx playwright install chromium` 이 아닌
> `python -m playwright install chromium` 을 사용해야 conda 환경의 Playwright와 일치합니다.

설치 후 바이너리 위치: `%LOCALAPPDATA%\ms-playwright\chromium-xxxx\`

---

## 3단계 — 저장소 클론 및 Node 패키지

```powershell
git clone https://github.com/your-org/mes-agent.git
cd mes-agent
npm install
```

---

## 4단계 — 환경 설정 (.env)

```powershell
copy .env.example .env
```

`.env`를 열어 아래 항목을 설정합니다:

```ini
# ── 개발 환경 경로 ────────────────────────────────────
NODE_VERSION=22.22.3
CONDA_ENV=mes-agent
NVM_HOME=C:\Users\<사용자명>\AppData\Local\nvm
NVM_SYMLINK=C:\nvm4w\nodejs
MINICONDA_HOME=C:\ProgramData\miniconda3   # 설치 경로에 맞게

# ── LLM 설정 ─────────────────────────────────────────
LLM_ACTIVE=openai                          # openai 또는 internal
LLM_OPENAI_BASE_URL=https://api.openai.com/v1
LLM_OPENAI_MODEL=gpt-4o

LLM_INTERNAL_BASE_URL=http://사내LLM주소/v1
LLM_INTERNAL_MODEL=사내모델명

# 미지/사내 모델의 보수적 컨텍스트 기본값과 압축 시작 비율
LLM_DEFAULT_CONTEXT_TOKENS=100000
COMPACT_RATIO=0.7

# ── API 키 ────────────────────────────────────────────
OPENAI_API_KEY=sk-...
# INTERNAL_API_KEY=...

# ── Agent 서버 ────────────────────────────────────────
AGENT_PORT=8000

# ── OCR ──────────────────────────────────────────────
OCR_TESSERACT_CMD=D:/Program Files/Tesseract-OCR/tesseract.exe
OCR_LANG=kor+eng

# ── Obsidian ──────────────────────────────────────────
OBSIDIAN_VAULT_PATH=D:/archive/obsidian/brain
OBSIDIAN_HOST=https://127.0.0.1:27124
OBSIDIAN_API_KEY=<발급받은 API 키>

# ── Vault 매개 원격 제어(명령함, 백로그 O) — 선택 ────────
# 기본 비활성. 켜면 동기화되는 Vault의 agent/control/inbox.md 에 "- [ ] 명령" 을
# 적으면 에이전트가 실행하고 agent/control/status.md 에 결과를 적는다(포트 개방 없음).
CONTROL_ENABLED=false
CONTROL_POLL_INTERVAL=5
```

> **주의**: `.env`는 `.gitignore`에 포함되어 있어 git에 올라가지 않습니다.

> **원격 제어(선택)**: `CONTROL_ENABLED=true`로 켜면 Obsidian Sync 등으로 공유되는 Vault를 통해
> 폰/다른 PC에서 명령을 던질 수 있습니다. 무인 실행이므로 위험·쓰기 작업은 자동 거부(읽기·관찰 위주),
> 위험 작업은 데스크톱에서 직접 승인하세요.

### Obsidian API 키 발급

Obsidian Local REST API 키는 Obsidian 앱 내에서 발급합니다:

1. Obsidian 실행 → **설정(⚙)** → **Community plugins**
2. `Local REST API` 플러그인 찾아서 **옵션** 클릭
3. **API Key** 항목에서 키 복사
4. `.env`의 `OBSIDIAN_API_KEY=` 뒤에 붙여넣기

> 폐쇄망 주의: `Local REST API` 플러그인이 없으면 외부망 PC에서 미리 다운로드해야 합니다.

---

## 5단계 — 실행

### PowerShell 초기화 (최초 1회)

conda를 PowerShell에서 쓰려면 conda init이 필요합니다:

```powershell
# Miniconda Prompt에서 실행
conda init powershell
# PowerShell 재시작
```

### 개발 환경 시작

```powershell
cd mes-agent
.\start.ps1          # conda + Node PATH 자동 설정
npm start            # Electron 앱 실행 (FastAPI 서버 자동 시작)
```

### 개발 모드 (DevTools 포함)

```powershell
$env:DEV_TOOLS=1; npm start
```

---

## 폐쇄망 이전

외부 인터넷 접근이 불가한 사내 PC로 이전하는 방법입니다.

### Python 환경 이전 (conda-pack)

외부망 PC에서:
```powershell
conda activate mes-agent
conda install conda-pack -y
conda pack -n mes-agent -o mes-agent-env.tar.gz
```

사내 PC에서:
```powershell
mkdir C:\conda-envs\mes-agent
tar -xzf mes-agent-env.tar.gz -C C:\conda-envs\mes-agent
C:\conda-envs\mes-agent\Scripts\activate
conda-unpack
```

`.env`의 `MINICONDA_HOME`을 `C:\conda-envs`로 수정합니다.

### Node 패키지 이전

`node_modules` 폴더 전체를 ZIP으로 압축해서 이전하거나,
`package-lock.json` 포함하여 클론 후 오프라인 상태에서 `npm ci --prefer-offline`.

### Playwright 브라우저 이전

외부망 PC에서:
```powershell
conda activate mes-agent
python -m playwright install chromium
# 이후 %LOCALAPPDATA%\ms-playwright\ 폴더 전체를 USB에 복사
```

사내 PC에서 동일 경로에 붙여넣기:
```
C:\Users\<사용자명>\AppData\Local\ms-playwright\
```

또는 환경변수로 경로를 지정할 수 있습니다:
```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "D:\playwright-browsers"
```

### Tesseract OCR 이전

UB-Mannheim 설치본(`tesseract-ocr-w64-setup-*.exe`)을 USB로 복사 후 설치.

---

## 문제 해결

### conda가 PowerShell에서 안 될 때
```powershell
# Miniconda Prompt에서 실행
conda init powershell
# PowerShell을 관리자 권한으로 재시작
```

### npm을 못 찾을 때
```powershell
# nvm 경로를 수동으로 추가
$env:PATH = "C:\Users\<사용자명>\AppData\Local\nvm;C:\nvm4w\nodejs;" + $env:PATH
```
또는 `start.ps1`을 실행하면 자동 처리됩니다.

### Tesseract 오류
```
TesseractNotFoundError
```
`.env`의 `OCR_TESSERACT_CMD` 경로가 실제 `tesseract.exe` 위치와 일치하는지 확인하세요.

### Playwright 브라우저 오류
```
Executable doesn't exist / BrowserNotFound
```
conda 환경이 활성화된 터미널에서 아래 명령을 실행하세요:
```powershell
conda activate mes-agent
python -m playwright install chromium
```
앱 실행 후에도 오류가 계속되면 앱을 재시작하세요.

### Python 서버 포트 충돌
`.env`에서 `AGENT_PORT`를 다른 포트(예: `8001`)로 변경하세요.
