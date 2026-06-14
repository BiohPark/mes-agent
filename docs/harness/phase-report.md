# 개발 계획 Phase 보고서

> 목적: Codex CLI 정상화 이후 mes-agent 개발 계획을 우선순위 기반 Phase로 쪼개, 각 단계의 산출물과 게이트를 명확히 한다.

## 우선순위 원칙

1. **실행 표면 안정화 먼저**: Codex CLI, Claude Code, worktree, critic/worker 권한을 안정화한다.
2. **개발환경 하네스 먼저**: 제품 내부 multi-agent 런타임 구현보다, 개발 계획 품질 루프를 먼저 운영 가능하게 만든다.
3. **작게 닫히는 첫 성공 사례**: Task T 또는 Supervisor Console 중 하나를 작업 카드 단위로 끝낸다.
4. **제품 내부 하네스는 계약 먼저**: RunSnapshot/RunLedger는 GxP 감사추적과 맞닿으므로 계약 문서 후 구현한다.
5. **외부 패턴은 기능 계약만 차용**: 코드 반입 없이 스펙과 테스트로 재작성한다.

## Phase 0 — 실행 표면 정상화

상태: **완료에 가까움**

목표:

- Codex CLI를 로컬 agent로 사용할 수 있는지 검증한다.
- 계획 critic과 구현 worker의 sandbox/approval 기준을 분리한다.

완료 증거:

- `cmd /c codex --version` → `codex-cli 0.139.0`
- `cmd /c codex doctor` → 실패 없음
- `cmd /c claude auth status --text` → Claude Pro 로그인 확인
- `claude --version` → `2.1.168`
- Claude Code 전역 플러그인 `ecc@ecc`, `ralph-loop@claude-plugins-official` 활성화 확인
- ECC project-local rules `.claude/rules/ecc/{common,python,typescript,web}` 표준화
- 승인된 샌드박스 외부 실행에서 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke` →
  - `CODEX_EXEC_OK`
  - `CLAUDE_EXEC_OK` (`--safe-mode` 제거 후)
- `docs/harness/2026-06-13-plan-critic-readiness.md`
- `docs/harness/2026-06-14-ecc-rules-readiness.md`

남은 일:

- Codex Desktop 관리 셸 안에서는 Claude/Codex CLI agent 호출이 네트워크/파일 제한에 걸릴 수 있으므로, 실제 critic/worker 실행은 승인된 샌드박스 외부 실행으로 수행
- 이 PC에서는 PowerShell 실행 정책 때문에 `*.ps1` 직접 실행이 막힐 수 있으므로 `powershell -NoProfile -ExecutionPolicy Bypass -File ...`로 실행
- Claude Code 긴 Read critic은 타임아웃될 수 있으므로 짧은 Risk/Test Critic prompt 또는 Claude worker 작업에 우선 사용
- ECC full/manual installer는 사용하지 않고 plugin path + project-local rules만 유지

Gate:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke
```

## Phase 1 — 계획 품질 루프 운영화

상태: **진행 중**

목표:

- 모든 기능 개발을 작업 카드로 시작한다.
- 구현 전 Implementation Critic / Risk-Test Critic 결과를 통합한다.
- `dev-harness-*`, `product-harness-*`, `supervisor-*` prefix로 작업 층을 구분한다.

산출물:

- `docs/harness/task-card-template.md`
- `docs/harness/2026-06-13-existing-plan-review.md`
- `docs/harness/2026-06-13-critic-round-1.md`
- `docs/ORCHESTRATION_GUIDE.md` 표준 작업 흐름 갱신
- `docs/specs/development-harness.md` critic 단계 갱신

다음 작업:

1. Task T 또는 Supervisor Console 중 하나를 골라 작업 카드를 작성한다.
2. `spec` 파일이 대상 worktree에서 보이는지 확인한다.
3. Claude Code 토큰이 남아 있으면 Risk/Test Critic 또는 worker를 Claude 우선으로 실행한다.
4. Codex CLI는 잔여 토큰이 낮을 때 smoke 또는 보조 critic으로만 쓴다.

Gate:

- 작업 카드에 `scope.in`, `scope.out`, `files.owned`, `files.readonly`, `gates`, `external_send`가 있다.
- 작업 카드에 `files.owned`, `files.readonly`, `owners`, `base_branch`, `spec_synced`, `conflict_policy`, `test_dod`가 있다.
- critic 결과가 worker 지시에 반영됐다.

## Phase 2 — 첫 성공 사이클

상태: **진행 중**

목표:

- 하네스 루프가 실제 작은 작업 하나를 끝까지 닫는지 확인한다.

추천 후보:

| 후보 | 장점 | 리스크 |
|------|------|--------|
| `dev-harness-task-T` | 기존 문서가 첫 성공 대상으로 언급 | 실제 스펙/worktree 상태 확인 필요 |
| `supervisor-phase1-reducer` | 제품 UX 가치가 바로 보임 | frontend 테스트 기준을 먼저 구체화해야 함 |

권장 선택:

- 먼저 `supervisor-phase1-reducer`를 작업 카드로 만들고, 파일 범위를 `electron/renderer/*`로 제한한다.
- 제품 내부 하네스 서버 변경은 Phase 3으로 넘긴다.

진행 결과:

- `docs/harness/cards/supervisor-phase1-reducer.md` 작업 카드 작성
- 우측 패널 `감독` 탭 추가
- 기존 SSE 이벤트를 frontend reducer로 복사 전달
- 목표, 단계, 현재 도구, 경과 시간, 승인 대기, 근거 요약 표시 구현
- 서버 영속화, RunSnapshot/RunLedger, 새 이벤트 타입은 범위 밖으로 유지

Gate:

- 별도 worktree 존재 또는 현재 workspace에서 변경 범위 명시
- 지정 파일 범위만 변경
- 빠른 테스트 또는 DOM/reducer 검증 기준 존재
- 변경 결과를 `code-reviewer` 또는 Codex 리뷰로 검토

## Phase 3 — 제품 내부 하네스 계약

상태: **대기**

목표:

- `RunSnapshot`, `RunLedger`, role/phase 라벨 계약을 구현 전에 고정한다.

산출물:

- `docs/contracts/product-harness-run-state.md`
- `docs/contracts/run-ledger.md`
- `product-harness-phase-role` 작업 카드

Gate:

- Planner/Executor/Observer/Verifier/Safety/Memory/Reporter 역할별 입력/출력 정의
- 기존 `generate()` 루프를 갈아엎지 않는 phase/role 라벨 1차 범위 정의
- GxP 감사추적 필드 후보 정의

## Phase 4 — 감독 콘솔 Phase 1 구현

상태: **부분 완료**

목표:

- 제품 내부 하네스 상태를 사용자가 감독할 수 있는 UI 기반을 만든다.

범위:

- 우측 패널 `감독` 탭
- SSE 이벤트를 프론트엔드 상태로 모으는 reducer
- 현재 목표, 단계, 도구, 경과 시간, 승인 대기, 근거 요약 표시
- 기본 busy mode를 "작게 비켜 보기 HUD" 방향으로 정리

Gate:

- DOM 또는 reducer 단위 테스트 기준
- 워크플로우 그래프 최초 fit-to-view 유지
- 기존 채팅/워크플로우 기능 회귀 없음

남은 일:

- Electron 앱 수동 확인
- 가능하면 DOM/reducer 자동 테스트 도입
- 기본 busy mode를 "작게 비켜 보기 HUD"로 바꾸는 작업은 별도 카드로 분리

## Phase 5 — Ralph/Claude 반복 구현 루프

상태: **대기**

목표:

- Claude Code/Ralph 또는 Codex CLI worker가 작업 카드를 반복 수행하고, 테스트 통과까지 닫는 루프를 만든다.

착수 조건:

- Claude Code CLI smoke 통과
- worktree 준비
- 첫 작업 카드 완료
- 종료 게이트 명확화

Gate:

- 반복 실행 후 테스트 통과
- 완료 보고에 변경 파일, 테스트 결과, 사용자 확인 방법 포함
- diff review 통과

## 현재 최우선 Next Actions

1. P0 하네스 정합화 변경(`run-plan-critics.ps1`, ECC rules, 관련 문서)은 `ceef24b chore: normalize dev harness setup`으로 로컬 커밋 완료 상태다. 원격 push는 사용자 명시 승인 후 진행한다.
2. `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke`는 2026-06-14 기준 `CODEX_EXEC_OK`, `CLAUDE_EXEC_OK`로 통과했다. Claude Code의 `SessionEnd hook ... Hook cancelled` 경고는 smoke 실패가 아니라 전역 plugin hook 후속 점검 항목이다.
3. Supervisor Console Phase 1 reducer는 2026-06-14에 상태 초기화/대기 해제/객체 결과 처리 보정을 적용했고, Node VM reducer fixture와 기존 workflow 테스트 80개가 통과했다.
4. `docs/harness/cards/supervisor-phase1-reducer.md` 구현 결과는 Computer Use 접근성 트리로 실제 Electron `MES Agent` 창에서 확인했다. 스크린샷 캡처는 현재 PC에서 `SetIsBorderRequired failed: 해당 인터페이스를 지원하지 않습니다. (0x80004002)`로 실패하므로, 자동 UI 검증은 접근성 트리 기반으로 수행한다.
5. Supervisor Console Phase 1 자동 테스트는 새 npm 의존성 없이 `window.workflowPanel.getSupervisorState()`를 이용한 reducer fixture 방식으로 시작한다. 별도 DOM/Playwright 도입은 후속 카드에서 결정한다.
6. Claude Code/Ralph-loop는 Task T처럼 반복 테스트가 명확한 worker 카드부터 사용한다.
