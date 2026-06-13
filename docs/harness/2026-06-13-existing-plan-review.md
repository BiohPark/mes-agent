# 2026-06-13 기존 계획 수동 critic 리뷰

## 리뷰 대상

- `docs/specs/development-harness.md`
- `docs/ORCHESTRATION_GUIDE.md`
- `docs/specs/product-agent-harness.md`
- `docs/specs/supervisor-console.md`
- `docs/backlog/pending/N-harness-mode.md`
- `docs/TRANSFORMATION_PLAN.md`

외부 모델 provider로 repo 문서 전송이 차단되어, 이번 리뷰는 Codex Desktop 현재 세션에서 수동 critic으로 수행했다. 실제 Codex CLI + Claude Code 독립 critic 라운드는 사용자 승인 후 `scripts/harness/run-plan-critics.ps1 -AllowExternalSend`를 샌드박스 외부 실행으로 수행한다.

## Implementation Critic Findings

[RISK] 개발환경 하네스와 제품 내부 하네스가 모두 "multi-agent/harness"라는 이름을 쓰지만 실행 표면이 다르다.
개발환경 하네스는 Codex/Claude/Ralph가 repo를 개발하는 루프이고, 제품 내부 하네스는 `agent/server.py` 런타임 역할 분리다. 문서상 구분은 있지만, 작업 카드 이름에 `dev-harness` 또는 `product-harness` 같은 prefix를 강제하지 않으면 worker가 서로 다른 층을 섞을 수 있다.

[RISK] 첫 성공 사이클이 아직 Task T에 묶여 있는데, 현재 마스터 플랜에는 Task T의 실제 스펙 파일 존재/브랜치/worktree 준비 상태가 완료 조건으로 연결되어 있지 않다.
Ralph loop 시험 전 `spec visible in worktree`를 자동/수동 체크하는 짧은 준비 명령이 필요하다.

[SUGGESTION] Codex CLI는 critic과 worker 실행형을 분리한 것이 맞다.
critic은 `read-only + ignore-user-config + ignore-rules + ephemeral`, worker는 별도 worktree에서만 `workspace-write`로 제한하는 현재 문서 방향을 유지한다.

[SUGGESTION] 감독 콘솔 Phase 1과 제품 내부 하네스 Phase 1은 함께 진행하되, 파일 소유 범위를 나누는 편이 안전하다.
예: 제품 내부 하네스는 `agent/server.py`, `agent/core/events.py` 중심, 감독 콘솔은 `electron/renderer/*` 중심. 같은 worker에게 양쪽을 한 번에 맡기면 범위가 커진다.

## Risk/Test Critic Findings

[RESOLVED] 실제 멀티엔지니어 critic 라운드는 수행됐다.
Codex CLI와 Claude Code smoke는 승인된 샌드박스 외부 실행에서 통과했다. 사용자가 외부 전송을 승인한 뒤 Codex Implementation Critic과 Claude Risk/Test Critic 결과를 `docs/harness/2026-06-13-critic-round-1.md`에 통합했다. Claude 긴 Read critic은 타임아웃될 수 있어 짧은 Risk/Test Critic fallback을 공식 경로로 둔다.

[RISK] 제품 내부 하네스의 RunLedger/RunSnapshot은 GxP 감사추적과 맞닿아 있으므로, 구현 전 계약 문서가 필요하다.
`docs/backlog/pending/N-harness-mode.md`가 말한 `docs/contracts/` 우선 원칙을 제품 내부 하네스 Phase 1 수용 기준에도 연결해야 한다.

[RISK] supervisor-console Phase 1의 테스트 기준이 "Playwright 또는 DOM 단위 테스트 기준 정의"로만 남아 있다.
구현 worker에게 넘기기 전에는 최소 DOM 상태 reducer 테스트, SSE 이벤트 fixture, HUD 표시 조건 중 무엇을 gate로 삼을지 정해야 한다.

[SUGGESTION] 외부 모델로 critic을 돌리는 경우, 완료 보고에는 반드시 다음을 남긴다.
- 어떤 문서를 보냈는지
- 어떤 모델/CLI를 사용했는지
- read-only였는지 workspace-write였는지
- 결과 저장 경로
- 차단/로그인/권한 실패 여부

## 정리된 다음 순서

1. `scripts/harness/run-plan-critics.ps1 -Smoke`로 Codex CLI/Claude Code 최소 실행을 반복 검증한다.
2. Claude Code 실행은 `--bare` 없이 OAuth 로그인 경로를 사용한다.
3. 다음 작업 카드는 critic round 1에서 추가된 ownership/conflict/test_dod 필드를 채운 뒤 worker에게 넘긴다.
4. Task T 또는 Supervisor Console 중 하나를 골라 작업 카드에 `dev-harness`/`product-harness` 층을 명시한다.
5. worker 시작 전 `spec visible in worktree`, `scope.in/out`, `gates`, `docs/contracts 필요 여부`를 점검한다.
