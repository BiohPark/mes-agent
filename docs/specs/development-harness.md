# 스펙 — Codex + Claude Code 병행 개발 하네스

> 상태: 설계 확정 대상 · 범위: 개발환경/작업 절차 · 제품 런타임 변경 없음
> 목적: 사용자가 원하는 업무자동화 봇을 안정적으로 키우기 위해, Codex와 Claude Code를 병행 개발 파트너로 운영하는 표준 루프를 정의한다.

## 해결하는 문제

현재 mes-agent는 기능이 빠르게 늘었지만, 작업 흐름이 쉽게 흩어진다.

- 어떤 스펙을 어느 브랜치/worktree에서 구현 중인지 놓치기 쉽다.
- Claude/Ralph가 이전 지시를 기억한 채 새 작업과 섞을 수 있다.
- “완료”의 기준이 테스트, 리뷰, 커밋, 사용자 가이드까지 일관되지 않다.
- ECC, OpenHands, OpenClaw 같은 좋은 패턴을 즉흥적으로 들여오면 출처·범위·안전성이 흐려질 수 있다.

이 스펙은 개발환경을 “대화형 구현”에서 **스펙 기반 병행 개발 루프**로 바꾸기 위한 운영 계약이다.

## 목표

1. Codex와 Claude Code가 같은 스펙을 보고 역할을 나눠 작업한다.
2. Ralph loop 또는 유사 루프가 작은 작업을 끝까지 반복 수행한다.
3. 작업은 항상 격리된 branch/worktree에서 진행한다.
4. 완료 기준은 테스트, 리뷰, 문서, 커밋까지 포함한다.
5. 좋은 오픈소스 패턴은 코드 복사가 아니라 “기능 계약 → 스펙 → 테스트 → 우리 코드 구현”으로 차용한다.
6. 작업 완료 후 사용자가 다음에 어떻게 쓰고 검증할지 알 수 있는 짧은 가이드가 남는다.

## 비목표

- 이번 스펙은 제품 내부 multi-agent 런타임을 구현하지 않는다.
- ECC, OpenHands, OpenClaw를 통째로 설치하거나 소스코드를 반입하지 않는다.
- CI/CD, GitHub PR 자동화 전체를 한 번에 완성하지 않는다.
- 회사 폐쇄망 PC에 새 개발 도구 설치를 전제로 하지 않는다.

## 역할

| 역할 | 책임 |
|------|------|
| 사용자 | 제품 방향, 우선순위, 위험 작업 승인 |
| Codex | 설계 정리, 백로그 분해, 리뷰, 작업 흐름 복구, 보조 구현 |
| Claude Code | worktree 안에서 주 구현, 테스트 작성, 로컬 검증 |
| Ralph loop | Claude Code 반복 실행, 종료 조건까지 자동 재시도 |
| code-reviewer | L1 루프 불변식, 보안 게이트, 툴 스키마, 문서 갱신 누락 검토 |
| 테스트 하네스 | `.\test.ps1`, unit/integration/smoke 게이트 실행 |

## 표준 작업 루프

### 0. 세션 오리엔테이션

세션 시작 시 다음 문서를 읽는다.

- `CLAUDE.md`
- `REFACTOR_BRIEF.md`
- `docs/TRANSFORMATION_PLAN.md`
- 현재 작업 스펙(예: `docs/specs/task-types-dynamic.md`)

### 1. 작업 카드 확정

모든 루프 작업은 짧은 작업 카드로 시작한다.

```yaml
task_id: task-T
title: 동적 업무 타입 관리
spec: docs/specs/task-types-dynamic.md
branch: ralph/task-T
worktree: ../mes-agent-ralph
scope:
  in:
    - TASK_CONFIGS를 get_task_configs()로 동적화
    - task_type_create/remove 도구 추가
    - /task-config API와 사이드바 렌더링 동적화
    - 지정 unit/integration/smoke 테스트 추가
  out:
    - 시스템 프롬프트 인라인 편집 UI
    - 업무 타입 순서 재정렬
    - 도메인별 워크플로우 자동 생성
gates:
  - tests/unit/test_task_type_tools.py
  - tests/integration/test_task_config_api.py
  - tests/smoke/test_tool_schemas.py
  - .\test.ps1 ci
completion_promise: DONE
```

작업 카드의 `spec` 파일은 반드시 대상 worktree에서 볼 수 있어야 한다. 이번에 발생한 혼선처럼 스펙이 메인 worktree에만 있으면 루프를 시작하지 않는다.

### 2. worktree 준비

- 큰 작업은 항상 별도 worktree에서 진행한다.
- 브랜치명은 작업 주체와 작업명을 드러내게 짓는다. 예: `ralph/task-T`, `codex/supervisor-console`.
- `master`와 worktree 브랜치 차이가 없는 상태인지 확인한 뒤 시작한다.
- 이미 진행 중인 변경이 있으면 새 루프 지시 전에 `git status`를 먼저 사용자에게 보고한다.

### 3. 루프 실행

Ralph loop 지시는 다음 내용을 포함한다.

- 읽을 문서
- 구현 범위
- 금지 범위
- 반복마다 실행할 테스트
- 최종 게이트
- 완료 문구

예:

```text
docs/specs/task-types-dynamic.md 명세대로 구현하라.
범위 밖 기능은 만들지 마라.
매 반복마다 지정 unit test를 실행하고, 마지막에는 .\test.ps1 ci와 smoke tool count를 확인하라.
모든 게이트가 통과하면 DONE을 출력하라.
```

### 4. 리뷰

구현 완료 후 다음 순서로 확인한다.

1. Claude Code 자체 요약
2. `code-reviewer` 서브에이전트 검토
3. Codex 리뷰 또는 사용자 리뷰
4. 발견된 문제 수정

리뷰는 칭찬보다 결함 탐지를 우선한다.

### 5. 커밋과 가이드

커밋 전 체크리스트:

- 테스트 결과가 명시되어 있다.
- 관련 문서가 갱신됐다.
- 툴 수 변경 시 smoke 기대값이 맞다.
- 새 설정/의존성이 있으면 `.env.example`, `SETUP.md`가 갱신됐다.
- 사용자에게 “어떻게 써보면 되는지” 짧은 사용 가이드가 있다.

## 오픈소스 체리피킹 규칙

ECC, OpenHands, OpenClaw 등은 다음 순서로만 반영한다.

1. 원본 기능의 문제 해결 방식을 요약한다.
2. 라이선스와 반입 가능성을 확인한다.
3. 코드를 복사하지 않고 기능 계약을 우리 말로 다시 쓴다.
4. `docs/specs/`에 mes-agent용 스펙을 작성한다.
5. 테스트를 먼저 정의한다.
6. 우리 코드 스타일과 폐쇄망 제약에 맞춰 구현한다.

### 1차 차용 후보

| 출처 | 차용 후보 | mes-agent 적용 방향 |
|------|----------|--------------------|
| ECC/Claude Code 생태계 | hooks, skills, subagents, slash-command형 루프 | `.claude/`, `.agents/`, `.codex/` 구성 강화 |
| OpenHands | event stream, Agent Canvas, context condenser, delegation, observability | 감독 콘솔, 실행 이벤트 타임라인, 역할 분리 설계 |
| OpenClaw | local-first gateway, session routing, live canvas, sandbox 기본값 | 폐쇄망 친화 실행, 작업 세션 라우팅, HUD/감독 화면 |

## 첫 적용 순서

1. **Task T 성공 사이클**: `docs/specs/task-types-dynamic.md`를 기준으로 Ralph loop 첫 정상 완료를 만든다.
2. **감독 콘솔 1차 개편**: `docs/specs/supervisor-console.md`를 기준으로 UX 가시성을 높인다.
3. **도메인 첫 end-to-end**: MES 검증, Office 작성, 배포 자동화 중 하나를 골라 실제 업무 흐름을 만든다.

## 수용 기준

- [ ] 작업 카드가 없으면 loop 작업을 시작하지 않는다.
- [ ] 대상 worktree에서 스펙 파일이 보이는지 확인한다.
- [ ] 루프 완료는 테스트 통과와 리뷰 통과를 포함한다.
- [ ] 구현 결과에는 사용자용 확인/사용 가이드가 포함된다.
- [ ] 오픈소스 차용은 기능 계약과 출처 기록을 남긴다.
- [ ] Task T가 이 하네스의 첫 성공 사례로 완료된다.
