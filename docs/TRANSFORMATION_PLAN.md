# mes-agent 대전환 프로젝트 마스터 플랜

> 작성: 2026-06-12 · 상태: DRAFT (대화하며 발전시키는 살아있는 문서)
> 목적: Claude Code 세션이 이 문서를 읽고 각 트랙의 다음 작업을 이어갈 수 있게 한다.

## 불변 제약 (모든 트랙 공통)

- **배포 환경**: 회사 PC 기본 배포는 폐쇄망(런타임 외부 호출 불가). **기능 설계는 외부 API도 지원하도록 작성하고, 폐쇄망/개방망 전환은 config로 처리한다.** 의존성 추가 = conda-pack 번들 갱신 비용 → 신규 패키지는 근거와 함께 제안만.
- **개발 브리지**: Termux/홈PC에서 개발 → GitHub push → 회사 PC git pull. 회사 PC에는 개발 도구를 설치하지 않는다.
- **LLM**: 사내 OpenAI-compatible 엔드포인트 (`openai` 라이브러리 + base_url). 멀티모달 지원 여부 확인 필요 → ☐ 미확인
- **외부 서비스 Config 분리**: LLM(`LLM_*`)·SharePoint/M365(`GRAPH_*`)는 각각 독립 `.env` 블록. 폐쇄망 배포 시 내부 엔드포인트, 개발 환경(홈PC)에서는 외부 API 사용.
- **Obsidian**: urllib.request → localhost:27123 REST 직접 호출 유지.
- **GMP/GxP**: MES 데이터를 변경하는 자동화 경로에는 감사추적(누가/언제/무엇을) 필수.
- **출처 위생**: 오픈소스는 개념만 차용, 코드 복사 금지. claw-code 계열 코드는 어떤 형태로도 반입 금지 (개념 참조 시 본 문서에 출처 기록).

## 트랙 0 — 안정성/데이터무결성 핫픽스 (최우선, 모든 트랙 위)

> 2026-06-16 실사용 중 발견한 **차단성 버그 3 + 개선 3**. Architect/Skeptic/Pragmatist 3인 토론 2라운드 만장일치 합의.
> 승인 계획 원본: `~/.claude/plans/rosy-honking-sunrise.md`. 근본 원인은 코드로 확정(파일·라인 직접 확인).

### 이번 사이클 — 순수함수 TDD(RED→GREEN), Electron·외부의존 0

| # | 항목 | 파일·위치 | 규모 | 상태 |
|---|------|-----------|------|------|
| 1 | **P2 compaction replace-or-append** — 요약을 head 마지막 system content에 합쳐 단일-system 불변 보장 | `agent/core/compaction.py:77-79` | S | ✅ |
| 2 | **P1 저장필터** — 제어 메시지(넛지·계획승인·끼어들기) 영속화 차단 | `agent/core/transcript.py` + `server.py` | S~M | ✅ |
| 3 | **P1 표시측 과거호환필터** — 기존 오염 스레드도 표시에서 제외 | `agent/obsidian_session.py` | S | ✅ |
| 4 | **P3 설정 점검 + source 표시** — 모델 리스트 출처 UI 노출 | `.env.example` + `electron/renderer/chat.js` | S | ✅ |
| 5 | **P2부가: 윈도우/ratio 보수화** — `LLM_*_CONTEXT_TOKENS≈100k`, `COMPACT_RATIO 0.8→0.7` | `.env.example`·설정 | S | ✅ |
| 6 | **I1 .env 그룹핑·기본값·전문가섹션** | `.env.example` + `SETUP.md` | S | ✅ |

**근본 원인(확정):**
- **P2 (400 "System Message must be at the beginning")**: `compact_messages`가 `head + [system 요약] + tail`로 **두 번째 system 메시지** 생성 → 사내 vLLM 거부. `overflow.py` 2차 재시도도 동일 호출이라 동일 결함 반복. **수정 = 요약을 head 마지막 system content에 replace-or-append**(별도 system 안 만듦, 진입가드 불필요, overflow 자동 해소, tool 짝 I1 무영향).
- **P1 (대화 오염)**: `generate()`가 제어 메시지를 `role="user"`+`"[시스템]…"`로 주입 → `save_thread_messages`가 작업버퍼 전체 영속화 → 재진입 시 `get_thread_display_messages`가 system 요약은 걸러내고 남은 `[시스템]` user 라인만 표시. **근본 결함: 작업버퍼=영속기록=표시소스 동일 배열.** 수정 = **저장측+표시측 한 쌍 필수**(저장측만 고치면 이미 오염된 과거 Vault 스레드 미복구). 미래=마킹(`_ephemeral`), 과거=프리픽스 매칭.
- **P3 (모델 리스트)**: 버그 아님. `agent/llm.py list_available_models()`가 이미 `/v1/models`→`.env LLM_{PROFILE}_MODELS` 폴백을 양 프로파일 동일 처리 + `source` 반환. 폐쇄망 프리셋 미설정/오타 + UI 출처 미표시 체감 문제.

**구현 결과(2026-06-16):**
- `compact_messages()`는 요약을 첫 system 메시지에 병합해 사내 vLLM의 "system must be at beginning" 거부를 피한다.
- `agent/core/transcript.py`가 런타임 제어 메시지를 `_ephemeral`로 표시하고 저장/표시에서는 제거한다. 과거 `[시스템]`, `[사용자 끼어들기]` 오염 메시지도 표시/재저장 시 필터링한다.
- 미지 모델 기본 컨텍스트는 100k, `COMPACT_RATIO` 기본값은 0.7로 보수화했다. 모델 목록 source 표시는 기존 `chat.js` 구현을 유지한다.

### Track 1C follow-up status (2026-06-16)
> L2 seed 구현으로 작업버퍼(`agent-messages`)와 표시 transcript(`agent/transcripts/...jsonl`)를 분리했다.
> compaction 이후에도 새로 기록된 user/assistant 표시 대화와 compaction summary는 active/archive display·count·search에서 복원된다.
> RunLedger writer seed 구현으로 request_id 단위 JSONL 감사추적과 phase/role 이벤트 기록을 추가했다.
> **(2026-06-18)** 사용자 열린 엑셀 창과 실시간으로 호흡하는 Active COM 연동(`excel_active_set_cells`, `excel_active_get_range`)을 구현하여 실시간 Shared-State Interaction을 달성했다.

### 후속(선행조건 아님, 분리 트랙)
- **transcript 3계층 + 원문 무손실 + RunLedger** → 트랙 **1C** seed 구현, 계약 `docs/contracts/L2_message_invariants.md`.
- **I2 창 UX**(반투명 기본·비켜보기 확대·Codex식 테두리·ESC중지) → CLAUDE.md 백로그 **X**. 순수함수 검증 불가(Electron 수동확인). **작업권 회수·전역 ESC는 입력 가로채기 리스크 → 보안 검토 후.**
- **I3 Office365** → CLAUDE.md 백로그 **Y** + "Office 백엔드 확정" 대기. **회사 PC 선검증 필수**, 폐쇄망 폴백(로컬 다운로드→`office_com` 편집)을 1순위. **평문 자격증명 .env 저장은 GxP/보안 리스크 → DPAPI/자격증명관리자 검토 전 보류.**

## 트랙 1 — 개발 하네스 레벨업 (하네스 엔지니어링 + 루프)

**목표**: "대화하며 한 작업씩" → "스펙 작성 → 루프 실행 → diff 리뷰" 워크플로우로 전환.

**활성 스펙**: `docs/specs/development-harness.md`

**운영 가이드**: `docs/ORCHESTRATION_GUIDE.md`

### 1단계: 하네스 구조 도입 (레포만, 무위험) ✅ 2026-06-13 완료
- [x] `.claude/settings.json` 생성 — 권한 기본값(test/git), Stop·PostToolUse 훅
- [x] `.claude/agents/code-reviewer.md` — CLAUDE.md 규칙·L1 불변식·보안·툴 스키마 검토 서브에이전트
- [x] `.claude/skills/` — tdd·add-tool·loop-audit 3종
- [x] `.claude/rules/ecc/{common,python,typescript,web}` — Claude Code `ecc@ecc` 플러그인용 project-local rules. 플러그인은 rules를 자동 배포하지 않으므로 repo 표준으로 추적
- [x] `AGENTS.md` 루트 — 이미 존재 확인 (기존 파일 유지)
- 참고: ECC(everything-claude-code)는 전역 plugin path + project-local rules 방식으로 **선별 차용**한다. full/manual installer는 중복 skills/hooks 위험 때문에 사용하지 않는다.

### 1.5단계: Codex CLI critic 표면 정상화 ✅ 2026-06-13 확인
- [x] `cmd /c codex --version` → `codex-cli 0.139.0`
- [x] `cmd /c codex doctor` → 설치·인증·상태 DB·네트워크 정상, 경고는 `git --version` 탐지와 mixed auth 신호
- [x] read-only exec 기본형 확인: `cmd /c codex -a never exec -C D:\_Repositories\mes-agent -s read-only --ephemeral --ignore-user-config --ignore-rules "..."`
- [x] critic 실행 스크립트 추가: `scripts/harness/run-plan-critics.ps1`
- [x] 하네스 운영 인덱스와 작업 카드 템플릿 추가: `docs/harness/README.md`, `docs/harness/task-card-template.md`
- [x] 우선순위 기반 Phase 보고서 추가: `docs/harness/phase-report.md`
- [x] 첫 추천 작업 카드 추가: `docs/harness/cards/supervisor-phase1-reducer.md`
- [x] 기존 계획 수동 critic 리뷰 기록: `docs/harness/2026-06-13-existing-plan-review.md`
- [x] Claude Code CLI 인증 확인: `cmd /c claude auth status --text`에서 Claude Pro 로그인 확인
- [x] Claude Code smoke 확인: 승인된 샌드박스 외부 실행에서 `CLAUDE_EXEC_OK`
- [x] repo 문서 기반 critic 라운드 수행: 사용자 명시 승인 후 Codex Implementation Critic + Claude Risk/Test Critic 결과를 `docs/harness/2026-06-13-critic-round-1.md`에 통합
- [x] Claude 긴 Read critic 타임아웃 fallback 반영: `scripts/harness/run-plan-critics.ps1`가 120초 초과 시 timeout note를 남기고 종료
- [x] root 문서 정리: `REFACTOR_BRIEF.md` 본문을 `docs/REFACTOR_BRIEF.md`로 이동하고 root에는 pointer 유지

### 2단계: Ralph loop 시험 운전
- [ ] **먼저 설치된 `ralph-loop` 플러그인으로 시험**(세션 내 Stop 훅 반복 — 직접 만들 것 없음): `/ralph-loop "작업…완료 시 DONE" --completion-promise "DONE" --max-iterations N`, 종료 게이트=`.\test.ps1`. 감독형/대화형에 적합.
- [ ] (무인 자동이 필요할 때만) `scripts/ralph/` 구성 — ralph.sh + prompt.md + prd.json (snarktank/ralph 패턴 참고). 헤드리스 외부 `while` 루프, 호스트 머신 필요.
- [ ] 루프 호스트 결정: ☐ 홈 Windows PC (Git Bash/WSL) ☐ Mac Mini M4 (도입 후) ☐ Termux (단기 실험만)
- [ ] git worktree 격리 작업공간 (`../mes-agent-ralph`)
- [ ] 첫 실험: 작고 검증 가능한 작업 1개, 5회 반복 human-in-the-loop, pytest를 종료 게이트로
- 성공 기준: 사람 개입 없이 1개 작업이 테스트 통과 상태로 커밋됨

### 3단계: 확장 (조건부)
- [ ] Mac Mini 도입 후 cmux로 Claude Code ↔ Codex 병렬/교차 리뷰
- 보류: 제품 내 멀티에이전트는 단일 루프 안정화 + UI 관찰성 확보 후

**미해결 질문**: 루프 호스트 머신, Claude Code 요금제 한도 내 루프 비용

## 트랙 1B — 작업 감독 UX 격상

**목표**: 자동화가 실행되는 동안 사용자가 목표·현재 단계·근거·위험·승인 상태를 계속 감독할 수 있게 한다.

**활성 스펙**: `docs/specs/supervisor-console.md`
**제품 내부 하네스 스펙**: `docs/specs/product-agent-harness.md`

- [x] 우측 패널에 `감독` 탭 추가 (`감독 / 워크플로우 / 로그`)
- [x] 기존 SSE 이벤트를 감독 콘솔 상태로 모으는 프론트엔드 reducer 구현
- [x] 기본 실행 중 창 동작을 `자동 최소화`에서 `작게 비켜 보기 HUD`로 전환
- [x] 워크플로우 그래프 최초 표시가 화면 밖으로 나가지 않도록 fit-to-view 보장
- [ ] MES 검증·Office 작성·배포 자동화 기본 템플릿을 도메인별로 구체화
- [ ] 후속: `RunSnapshot`/`RunLedger` 영속 모델로 새로고침 후에도 실행 상태 복원

**우선순위**: 감독 탭 reducer와 HUD/fit-to-view 후속은 1차 구현 완료. 다음은 제품 내부 하네스 계약 정렬과 V-2 liveness spike.

## 트랙 1C — 제품 내부 에이전트 하네스

**목표**: mes-agent 자체가 Planner/Executor/Observer/Verifier/Safety/Memory/Reporter 역할 기반 루프로 업무를 수행하게 한다.

**활성 스펙**: `docs/specs/product-agent-harness.md`

- [x] 기존 `generate()` 루프에 phase/role 라벨을 도입
- [ ] RunSnapshot을 프론트엔드 감독 콘솔 상태와 연결
- [ ] Verifier 단계를 명시해 도구 실행 성공과 업무 검증 성공을 분리
- [x] RunLedger 영속화로 실행 증적과 감사추적 기반 마련
- [ ] MES 검증·Office 작성·배포 자동화 도메인 하네스 팩으로 확장

**우선순위**: 감독 콘솔 Phase 1과 함께 1단계(role/phase 라벨)부터 점진 도입.

## 트랙 2 — 상용급 격상 (명세 역설계)

**목표**: 잘 알려진 상용/오픈 서비스의 기능을 스펙으로 역설계하여 `docs/specs/`에 축적 → 트랙 1의 루프가 구현.

### 상용급 정의 (Definition of Done)
| 영역 | 기준 |
|------|------|
| 신뢰성 | 액티비티별 재시도/에러 정책(UiPath 차용), 실패 후 재개 |
| 관찰성 | 실행 이력·로그를 Electron UI에서 조회 |
| 안전 | 권한 티어, dry-run/plan 모드, GxP 감사추적 |
| 견고성 | auto-wait(Playwright 차용), 정의-실행상태 분리(Temporal/LangGraph 차용) |
| 패키징 | Electron .exe 배포, conda-pack 재현 가능 |

### 분석 대상 및 차용 후보
- **OpenHands**: event stream 아키텍처, condenser(컨텍스트 압축), agent delegation, 샌드박스 격리
- **OpenClaw**: heartbeat(자가 점검), cron(예약 작업), IM 채널 라우팅, 사용자별 세션/메모리 → 트랙 3과 연결
- **ECC / Claude Code 생태계**: hooks, skills, subagents, slash-command형 루프 → 트랙 1 개발 하네스 강화
- 기존 차용 확정(`docs/REFACTOR_BRIEF.md`): n8n 노드/커넥션 분리, UiPath 재시도, Temporal/LangGraph 상태 분리, Playwright auto-wait
- 기존 4대 갭과 매핑: safety gate / 컨텍스트 압축 / 조기 종료 / plan mode

### 작업 방식
1. 기능 1개 선정 → 원본 문서/스펙 학습 → `docs/specs/<기능명>.md` 작성 (해결하는 문제 / mes-agent 매핑 / 수용 기준)
2. 스펙을 Ralph loop 크기(검증 가능한 단일 작업)로 분해 → prd.json 등록
- [ ] 첫 스펙 후보 선정: ☐ 컨텍스트 압축(Observation Masking) ☐ 조기 종료(외부 검증 종료조건) ☐ 기타

## 트랙 3 — 단기 기술 과제

### 3a. Tesseract 제거 (이미지 인식 LLM/네이티브 전환)
- 현황: pytesseract는 실시간 화면 텍스트(버튼/좌표) 용도, 복잡한 이미지는 이미 멀티모달 방침
- [ ] pytesseract 호출 지점 전수 조사 → (a) 실시간 좌표/텍스트 (b) 문서 인식 분류
- [ ] **(a)의 1순위 대안: pywinauto 접근성 트리** — 대상이 Windows 네이티브 앱으로 확인됨. OCR 없이 텍스트+좌표를 API로 직접 획득 (빠르고 결정적, GxP 재현성 유리)
- [ ] (b)는 멀티모달 LLM 직행 (사내 LLM 멀티모달 지원 확인이 전제)
- [ ] `OCRProvider` 어댑터 인터페이스 도입 → config 플래그로 신구 전환/롤백
- 완료 기준: tesseract 바이너리·kor.traineddata·pytesseract가 설치 절차에서 제거, 기존 시나리오 회귀 테스트 통과

### 3b. 녹스(Knox) 메신저 업무 챗봇 (향후 과제 — 설계만)
- [ ] ADR 1편 작성: FastAPI 웹훅 수신, 사용자별 세션 관리(상태·권한 분리), 인증, GxP 감사추적
- [ ] 트랙 2의 OpenClaw IM 라우팅/세션 개념과 연결점 명시
- [ ] 조사 필요: 녹스 메신저 API 스펙, 사내 승인 절차
- 구현 착수 조건: 트랙 1·2로 단일 루프와 안전 장치가 안정화된 후

## 진행 규칙 (Claude Code 세션용)

1. 세션 시작 시 본 문서 + CLAUDE.md + `docs/REFACTOR_BRIEF.md`를 읽는다.
2. 계획 변경은 본 문서를 수정하고, 구현은 트랙별 Issue/prd.json 단위로만.
3. 코드 작성 전 discovery audit — README 추측 기반 작업 금지.
4. 미체크 항목 중 사람 결정이 필요한 것은 멈추고 질문한다.
