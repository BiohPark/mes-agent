# MES Agent 개발 오케스트레이션 가이드

> 대상: 사용자(오케스트레이터), Codex, Claude Code, Ralph loop, 리뷰/조사 에이전트
> 목적: Codex Desktop, Claude Code, ECC 계열 패턴, Ralph loop, Codex sub-agent/worktree를 섞어 상용급 업무 자동화 봇을 지속적으로 개발하는 운영법을 고정한다.

## 한 줄 원칙

**Codex Desktop을 관제탑으로 두고, 작은 구현 작업은 Claude Code/Ralph 또는 Codex worktree worker에게 맡긴다. 모든 작업은 스펙, worktree, 테스트, 리뷰, 커밋 기준으로 닫는다.**

이 원칙은 고정된 도구 서열이 아니다. Codex가 항상 상급자이고 Claude가 항상 하급자라는 뜻이 아니다. 작업 성격에 따라 가장 잘 맞는 실행 표면을 고르는 운영 모델이다.

## 최종 목표

우리가 만들고 있는 제품은 단순 챗봇이 아니라 **MES/Office/배포 업무를 검증 가능한 절차로 실행하는 업무자동화 에이전트**다.

최종 제품이 잘해야 하는 일:

- MES 시스템 명세서 대비 검증 및 테스트
- Office 문서 작성 자동화
- 배포 자동화
- 실행 증적, 감사추적, 검증 리포트 생성
- 폐쇄망/회사 PC 환경에서 안정 실행
- 사용자가 자동화 과정을 감독할 수 있는 UX 제공

개발 하네스의 목표는 이 제품을 더 빠르고 안전하게 키우는 것이다.

## 지휘석은 어디인가

### 기본 지휘석: Codex Desktop

현재 단계의 기본 지휘석은 Codex Desktop이다.

Codex Desktop이 맡는 일:

- 전체 방향과 우선순위 정리
- 백로그와 스펙 작성
- 여러 작업 thread/worktree 관리
- sub-agent 병렬 조사/리뷰
- Claude/Ralph 결과 통합 판단
- 사용자에게 다음 액션과 사용 가이드 제공

Codex Desktop이 좋은 이유:

- 긴 문맥과 설계 대화를 유지하기 좋다.
- 로컬 workspace, git 상태, 문서, 브라우저 시각화, thread/worktree를 같이 다루기 좋다.
- 여러 에이전트를 “무엇을 맡길지” 판단하는 관제 업무에 적합하다.

### 구현 엔진: Claude Code + ECC/Ralph

Claude Code는 작은 스펙을 반복 구현하는 실행 엔진으로 적합하다.

Claude Code가 맡기 좋은 일:

- 스펙 하나를 읽고 테스트 우선 구현
- 실패 테스트 수정 반복
- Ralph loop로 자동 반복
- `.claude/skills`, `.claude/agents`, hooks 기반 완료 게이트
- ECC 패턴을 적용한 개발 루프 강화

### 보조 구현/검토 엔진: Codex worktree thread

Codex Desktop 안에서도 별도 thread와 worktree를 만들 수 있다.

Codex worktree가 맡기 좋은 일:

- Claude와 병렬로 다른 파일 영역 구현
- UI/문서/테스트처럼 소유 범위가 분리되는 작업
- Codex sub-agent 결과를 반영하는 작은 patch
- Claude가 막힌 작업의 대안 구현

### 조사/리뷰 엔진: sub-agent

Codex sub-agent는 병렬 조사와 리뷰에 적합하다.

sub-agent가 맡기 좋은 일:

- 특정 코드 영역 구조 조사
- OpenHands/OpenClaw/ECC 패턴 비교
- 스펙 누락 위험 점검
- 변경 diff 리뷰
- 테스트 누락 후보 탐색

단, 같은 파일을 여러 worker가 동시에 수정하게 맡기지 않는다.

## 역할 편성

처음부터 많은 에이전트를 돌리지 않는다. 기본 편성은 3개면 충분하다.

| 역할 | 기본 도구 | 책임 |
|------|----------|------|
| Orchestrator | Codex Desktop 현재 thread | 목표, 스펙, 분해, 통합 판단 |
| Worker | Claude/Ralph 또는 Codex worktree | 작은 스펙 구현 |
| Reviewer | Codex sub-agent 또는 Claude `code-reviewer` | 결함, 테스트, 보안, 문서 누락 검토 |

확장 편성:

| 역할 | 기본 도구 | 책임 |
|------|----------|------|
| Research Scout | Codex explorer sub-agent | 외부 패턴과 코드베이스 조사 |
| UX Auditor | Codex/Claude reviewer | 감독 콘솔, 워크플로우, HUD 품질 검토 |
| Harness Maintainer | Claude Code + ECC hooks/skills | 반복 개발 환경과 완료 게이트 유지 |
| Domain Specialist | 별도 worker | MES 검증, Office 작성, 배포 자동화 도메인별 구현 |

## ECC는 어떻게 쓸 것인가

Everything Claude Code v2 같은 ECC 계열 도구는 추천한다. 다만 **Codex에 그대로 꽂는 도구**라기보다, 먼저 Claude Code 하네스를 강화하는 재료로 본다.

적용 원칙:

1. ECC를 통째로 반입하지 않는다.
2. 기능을 분류한다.
3. Claude Code 전용인 것은 `.claude/`에 둔다.
4. Codex에도 유용한 개념은 `.codex/`, sub-agent, thread/worktree 운영법으로 미러링한다.
5. 공통 계약은 `AGENTS.md`, `CLAUDE.md`, `docs/specs/`, `docs/TRANSFORMATION_PLAN.md`에 둔다.

분류 기준:

| ECC 요소 | 적용 위치 | 판단 |
|----------|-----------|------|
| hooks | `.claude/settings.json`, 가능하면 Codex hooks 대응 | 테스트/리뷰 자동화에 유용 |
| skills | `.claude/skills`, `.agents/skills`, Codex skill 대응 | 반복 작업 절차화에 유용 |
| subagents | `.claude/agents`, Codex sub-agent 역할 정의 | 리뷰/조사/도메인 분리에 유용 |
| slash commands | Claude Code/Ralph 지시 템플릿 | 작업 카드 실행에 유용 |
| prompt packs | 스펙/가이드로 재작성 | 원문 직접 복사 금지 |
| 외부 의존 도구 | 별도 검토 | 폐쇄망 반입 비용 확인 필요 |

## 오픈소스 체리피킹 규칙

OpenHands, OpenClaw, ECC 등은 좋은 아이디어를 빠르게 흡수하기 위해 본다. 하지만 코드를 바로 복사하지 않는다.

반영 절차:

1. 어떤 문제를 해결하는 기능인지 요약한다.
2. mes-agent에 같은 문제가 있는지 확인한다.
3. 기능 계약을 우리 말로 쓴다.
4. `docs/specs/`에 스펙으로 고정한다.
5. 테스트 기준을 먼저 정한다.
6. 우리 코드 스타일과 폐쇄망 제약에 맞춰 구현한다.
7. 출처와 차용 이유를 `REFACTOR_BRIEF.md` 또는 관련 ADR에 기록한다.

1차 차용 후보:

| 출처 | 후보 | mes-agent 적용 |
|------|------|----------------|
| OpenHands | Agent Canvas | 감독 콘솔 UX |
| OpenHands | event stream / observability | 실행 타임라인, 로그, 상태 패널 |
| OpenHands | context condenser | 긴 실행 이력 요약 |
| OpenHands | delegation | 제품 내부 planner/executor/reviewer 후속 설계 |
| OpenClaw | live canvas | HUD와 작업 감독 화면 |
| OpenClaw | local-first/session routing | 폐쇄망 세션 운영 |
| ECC | hooks/skills/subagents | 개발 하네스 자동화 |

## 표준 작업 흐름

### 1. 오케스트레이터가 작업 카드를 만든다

작업 카드는 다음 내용을 가져야 한다.

```yaml
task_id: task-T
title: 동적 업무 타입 관리
spec: docs/specs/task-types-dynamic.md
branch: ralph/task-T
worktree: ../mes-agent-ralph
owner: Claude/Ralph
reviewer: Codex + code-reviewer
gates:
  - tests/unit/test_task_type_tools.py
  - tests/integration/test_task_config_api.py
  - tests/smoke/test_tool_schemas.py
  - .\test.ps1 ci
completion_promise: DONE
```

### 2. 작업 표면을 고른다

| 작업 성격 | 추천 실행 표면 |
|-----------|----------------|
| 백로그/설계/스펙 | Codex Desktop |
| 작은 구현 + 반복 테스트 | Claude Code + Ralph |
| 병렬 구현 | Codex worktree thread 또는 Claude 별도 worktree |
| 코드 구조 조사 | Codex explorer sub-agent |
| diff 리뷰 | Codex reviewer 또는 Claude `code-reviewer` |
| 정기 점검/리마인드 | Codex automation |
| UI 시각 비교 | Codex Desktop + 브라우저/시각화 |

### 3. worktree를 확인한다

루프 시작 전 필수 확인:

- 대상 worktree가 존재하는가
- 대상 브랜치가 맞는가
- 스펙 파일이 그 worktree에 존재하는가
- 이전 지시 파일이 남아 있지 않은가
- `git status`가 예상 범위 안인가

이번에 겪은 혼선의 원인:

- `ralph/task-T` 브랜치는 있었지만 새 커밋이 없었다.
- 실제 Task T 스펙은 메인 worktree에만 untracked로 있었다.
- Ralph 로컬 지시는 과거 OCRProvider 작업을 가리키고 있었다.

따라서 앞으로는 **스펙이 대상 worktree에 보이지 않으면 루프를 시작하지 않는다.**

### 4. Worker에게 명령한다

Claude/Ralph 지시 예:

```text
docs/specs/task-types-dynamic.md 명세대로 구현하라.
범위 밖 기능은 만들지 마라.
매 반복마다 unit gate를 실행하고, 마지막에는 .\test.ps1 ci와 smoke tool count를 확인하라.
변경 파일과 테스트 결과를 요약하라.
모든 게이트가 통과하면 DONE을 출력하라.
```

Codex worktree worker 지시 예:

```text
이 worktree에서 docs/specs/supervisor-console.md Phase 1 중 프론트엔드 상태 reducer만 구현하라.
수정 범위는 electron/renderer/chat.js, workflow.js, style.css로 제한한다.
다른 worker의 변경을 되돌리지 말고, 충돌이 있으면 보고하라.
테스트/검증 방법을 마지막에 적어라.
```

### 5. Reviewer가 검토한다

리뷰 기준:

- 스펙 범위 준수
- 테스트 추가/통과
- L1 루프 불변식 영향
- safety gate 우회 없음
- 툴 수 변경 시 smoke count 반영
- `.env.example`, `SETUP.md`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md` 갱신 필요 여부
- 사용자에게 쓸 수 있는 가이드가 있는지

### 6. 오케스트레이터가 통합한다

오케스트레이터는 다음을 결정한다.

- merge/commit 가능 여부
- 추가 수정 필요 여부
- 다음 작업 카드
- 사용자에게 설명할 사용법
- 백로그/로드맵 갱신 여부

## 첫 실행 계획

가장 먼저 할 일은 **Task T를 하네스 첫 성공 사이클로 만드는 것**이다.

순서:

1. `docs/specs/task-types-dynamic.md`를 커밋 또는 `ralph/task-T` worktree에 반영한다.
2. Ralph 로컬 지시를 OCRProvider가 아니라 Task T로 갱신한다.
3. Claude/Ralph가 구현한다.
4. 지정 테스트를 통과시킨다.
5. `code-reviewer`와 Codex가 리뷰한다.
6. 사용자가 확인할 수 있는 짧은 가이드를 남긴다.
7. 완료되면 이 흐름을 `docs/specs/development-harness.md`의 첫 성공 사례로 체크한다.

그 다음 작업은 **작업 감독 콘솔 UX Phase 1**이다.

## 좋은 운영 습관

- 작업 하나는 스펙 하나로 닫는다.
- 스펙 없이 loop를 시작하지 않는다.
- 같은 파일을 여러 worker에게 동시에 맡기지 않는다.
- “조사”와 “구현”을 섞지 않는다.
- 오픈소스는 기능 계약만 차용한다.
- 완료 보고에는 테스트 결과와 사용자 확인 방법을 포함한다.
- 막히면 더 많은 에이전트를 늘리기보다 작업 단위를 줄인다.

## 사용자용 빠른 판단표

| 지금 하고 싶은 일 | 어디서 시작할까 |
|------------------|----------------|
| 방향 잡기, 백로그 정리 | Codex Desktop |
| 작은 기능 구현 | Claude Code/Ralph 또는 Codex worktree |
| 구현 여러 개 병렬화 | Codex Desktop에서 worktree thread 분리 |
| 코드 구조만 빨리 파악 | Codex explorer sub-agent |
| 리뷰만 맡기기 | Codex reviewer sub-agent 또는 Claude `code-reviewer` |
| ECC 적용 검토 | Codex Desktop에서 분석 후 `.claude/`에 선별 반영 |
| OpenHands/OpenClaw 기능 차용 | 스펙 작성 후 별도 작업 카드 |
| 정기 자동 점검 | Codex automation |

## 현재 결론

- 명령의 기본 출발점은 Codex Desktop이다.
- Claude Code/ECC/Ralph는 작은 반복 구현 엔진으로 적극 쓴다.
- Codex worktree와 sub-agent는 병렬 조사/리뷰/보조 구현에 쓴다.
- 에이전트 수는 처음부터 많이 늘리지 않고, Orchestrator + Worker + Reviewer 3역할로 첫 성공 사이클을 만든다.
- 첫 성공 대상은 Task T, 다음 UX 대상은 Supervisor Console이다.
