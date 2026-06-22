# MES Agent Quality Evaluation Readiness (2026-06-23)

## Verdict

현재 프로젝트는 "컴퓨터 사용 agent가 사내 PC에서 품질 검토를 시작할 수 있는 기반"은 갖췄지만, GMP/SharePoint/MES 검증 시나리오를 end-to-end로 안정 측정하기에는 아직 보강이 필요하다.

즉시 가능한 범위:

- Electron/FastAPI agent 실행, 화면/브라우저/Office/Obsidian 조작
- Workflow/RunLedger 기반 작업 기록
- `syncade`/`unscript` domain harness 측정
- 로컬/동기화된 Office 문서의 COM 기반 Excel/Word/PPT 확인 및 일부 편집
- Obsidian RAG 기반 지식 검색/정리

아직 품질 검토의 핵심 리스크:

- SharePoint 문서를 "안정적으로 찾고 내려받고 다시 올리는" 전용 on-prem/사내 SharePoint 경로가 없다.
- Reviewer prompt는 read-only tool 사용을 말하지만 현재 `_reviewer_call()`은 실제 tools 배열을 전달하지 않는다. ADR-0004 G1 결정이 남아 있다.
- GMP/MES validation 전용 task type, prompt, fixture, 채점 기준은 기본 준비가 됐고, 회사 PC 실측이 남아 있다.
- Office365/SharePoint 로그인과 Edge UI 자동화는 회사 PC에서 확인해야 한다.
- 사용자 불편, 속도, false-pass를 정량화하는 실측 baseline이 아직 부족하다.

## Current Priority

우선순위 SSOT는 `docs/DEV_ROADMAP_2026-06.md`이다.

P0:

- Domain Harness Pack Phase 4 실측
- 회사 PC에서 `HARNESS_ENABLED=true`
- `syncade`/`unscript` 각각 harness ON/OFF 비교
- false pass, reviewer 효과, latency, 비용/토큰, 사용자 개입량 측정

P1:

- Harness mode N epic 지속 여부 결정
- V-2 timeout/liveness baseline 보강
- 감독 콘솔 domain template 보강

P3:

- Office/SharePoint backend path B/C/D
- Office365 login hardening
- 회사 PC B-0 체크리스트 검증 선행

## Evaluation Scenario: GMP Function Specification Coverage

목표 예시:

> SharePoint에 있는 GMP 기능명세서/요구사항 목록을 확인하고, 시스템 구현/업무 지식/Obsidian 기록에 반영되어 있는지 검증한다. 누락, 불일치, 승인 필요 지점을 도출하고 작업 기록을 Obsidian에 남긴다.

권장 실행 흐름:

1. 사용자에게 초기 질문
   - SharePoint 문서명/위치/URL
   - 검토 대상 시스템 또는 기능 범위
   - 결과물 형식: 보고서, backlog, Obsidian note, 수정 PR 여부
   - 쓰기 작업 허용 범위: read-only, 임시 파일 작성, SharePoint 업로드, Obsidian 기록

2. 문서 확보
   - 우선순위: 로컬 동기화/다운로드 파일 경로 확인
   - 대안: Edge로 SharePoint 열기 후 다운로드
   - 가능한 경우: Graph Excel REST
   - 임시 작업공간에 복사하고 파일 hash, 원본 URL, 다운로드 시각을 기록

3. Excel/Office 확인
   - COM 또는 OpenXML로 시트/표/대상 목록 파악
   - 기능 ID, 요구사항 ID, GMP/GxP 관련 컬럼, 승인 상태, 담당자, 비고 추출
   - 원본 수정은 하지 않고 분석 artifact를 별도로 생성

4. 지식 수집
   - Obsidian: 기존 기능명세, 개발 메모, 과거 검증 기록 검색
   - 사내 web: 접근 가능한 업무 시스템/문서 확인
   - 코드: 구현 지점, 테스트, 도구 MANIFEST, workflow template 확인
   - 모르는 항목은 `ask_user`로 명시 질문

5. 계획 재수립 및 승인
   - 검토 범위와 제외 범위 선언
   - "확인됨 / 미확인 / 불일치 / 추가 질문 / 개발 필요"로 분류
   - mutate 작업 전에 승인 포인트를 만든다.

6. Loop engineering
   - 작은 batch 단위로 조사, 증거 수집, 계획 수정
   - 각 batch는 RunLedger/작업 로그에 남긴다.
   - harness ON/OFF 비교 시 같은 입력과 같은 fixture를 사용한다.

7. 결과 보고
   - requirement coverage matrix
   - 주요 결함/불일치
   - 사용자 불편과 속도 병목
   - 다음 개발 backlog

8. 지식화
   - Obsidian에 검토 노트 작성
   - 다음 agent가 이어받을 수 있게 원본 문서 위치, 임시 파일 위치, 판단 근거, 미해결 질문 기록

## Measurement Checklist

품질 검토 중 반드시 측정할 항목:

- 성공 여부: 목표 산출물이 실제로 만들어졌는가
- false pass: Reviewer가 잘못 통과시킨 항목이 있는가
- false block: 실제로 가능한 작업을 불필요하게 막았는가
- 사용자 개입 수: 질문/승인/오류 복구 횟수
- latency: 문서 확보, Excel 분석, 지식 수집, 보고서 생성 단계별 시간
- evidence quality: 각 판단이 문서/코드/Obsidian/화면 증거로 추적 가능한가
- safety: 원본 문서 수정, credential 노출, 위험 명령 차단 여부
- UX friction: 창 전환, 로그인, 다운로드, 파일 선택, 긴 대기에서 사용자가 불편하지 않았는가

## Recommended Backlog Additions

P0-prep:

- 회사 PC B-0 체크리스트 문서화: SharePoint 접근, Edge 로그인, Office COM, Obsidian Local REST API, `HARNESS_ENABLED=true`, `WF_POLL_INTERVAL`, 모델 profile.
- GMP/MES validation task type 추가: prompt, workflow template, read-only default, approval gate. ✅
- 샘플 기능명세서 fixture 작성: 민감정보 없는 CSV로 requirement coverage 테스트 가능하게 구성. ✅
- 평가 명령/절차 고정: harness ON/OFF 반복 수, 입력 prompt, 지표 수집 endpoint, 결과 저장 위치. ✅
- 회사 PC B-0 체크리스트와 GMP 평가 절차 문서화. ✅

P1:

- ADR-0004 G1 결정 후 Reviewer read-only tool bundle 구현.
- SharePoint on-prem/local-sync/download/upload 경로를 하나의 `office_locate_or_download` 계층으로 정리.
- RunLedger artifact manifest 추가: 다운로드 파일 hash, 임시 파일, 보고서, Obsidian note link. ✅

P2/P3:

- Office365 login/session hardening.
- 사내 web 탐색 fallback과 사용자 확인 UI 개선.
- 장시간 PC 제어 중 HUD/중단/진행률 UX 실측 및 개선.

## Prep Fixes Applied In This Pass

- Workflow SSE file watcher now compares mtime, size, and a short content digest so same-second edits are not missed on Windows.
- JS fixture tests now resolve a usable Node executable from `NODE_EXE`, PATH, nvm `.env`, or the bundled Codex runtime before skipping.
- `test.ps1` now resolves the configured conda Python from `.env`/`.env.example` and keeps pytest temp files under workspace `.tmp`.
- `AGENTS.md`, `CLAUDE.md`, and `README.md` were updated to reflect the current test scale and fingerprint-based file watcher.

## Notes On CLI Delegation

The user approved active use of Claude Code and agy. In the current Codex shell, `agy` is not on PATH; the project delegation doc also records that agy's headless mode was unreliable as of 2026-06-22. Use Claude Code/Codex delegation first, and use agy only after confirming the local `agy.exe` can produce stable headless output.
