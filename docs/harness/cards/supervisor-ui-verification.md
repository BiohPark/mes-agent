# 작업 카드 — supervisor-ui-verification

```yaml
task_id: supervisor-ui-verification
title: Supervisor UI verification and RunSnapshot labels
layer: supervisor
spec: docs/specs/supervisor-console.md
branch: codex/supervisor-ui-verification
worktree: current
base_branch: master
owner: Codex Desktop
reviewer: Codex
spec_synced: true
conflict_policy: "이 카드는 Electron renderer 감독 상태와 검증 fixture만 소유한다. backend event/model/server 파일은 수정하지 않는다."
scope:
  in:
    - 감독 탭/HUD가 기존 SSE 이벤트를 RunSnapshot phase/role로 안정 표시
    - reducer를 Node fixture로 검증할 수 있게 순수 모듈화
    - confirm, tool 실행, done, error 상태 전환 fixture 추가
  out:
    - agent/server.py 변경
    - 새 SSE 이벤트 타입 추가
    - RunLedger 영속화
    - 새 npm/pip 의존성 추가
files:
  owned:
    - electron/renderer/supervisor-state.js
    - electron/renderer/workflow.js
    - electron/renderer/chat.js
    - electron/renderer/index.html
    - tests/renderer/supervisor-state.test.js
    - tests/unit/test_supervisor_state_js.py
    - docs/specs/supervisor-console.md
    - docs/harness/cards/supervisor-ui-verification.md
  readonly:
    - agent/server.py
    - agent/core/events.py
gates:
  - node tests/renderer/supervisor-state.test.js
  - cmd /c node --check electron\renderer\chat.js
  - cmd /c node --check electron\renderer\workflow.js
  - pytest tests/unit/test_supervisor_state_js.py
  - git diff --check
test_dod:
  unit:
    - planning 상태: request/agent_state/workflow_update가 planner phase를 유지
    - executing/observing 상태: tool_start/tool_done 후 도구가 비워지고 근거가 남음
    - waiting 상태: confirm이 safety role과 risk를 표시
    - done/error 상태: 도구·승인 대기가 비워짐
  invariant:
    - backend message history 조작 없음
    - tool-pair invariant 영향 없음
  offline:
    - 새 npm/pip 다운로드 없음
completion_promise: DONE
```

## 구현 결과 — 2026-06-15

상태: **구현 완료**

- 감독 상태 reducer를 `electron/renderer/supervisor-state.js`로 분리해 renderer와 Node fixture가 같은 전이 로직을 사용한다.
- 기존 SSE 이벤트를 `planning/executing/observing/waiting/done/error` phase와 `planner/executor/observer/safety/orchestrator` role로 1차 매핑한다.
- 감독 탭은 현재 `phase · role`을 표시하고, HUD는 현재 단계 줄에 `phase/role`을 함께 보여준다.
- confirm, tool 실행, done, error 상태 전환을 `tests/renderer/supervisor-state.test.js`와 pytest wrapper로 검증한다.

## 후속 — Track 1C Verifier 전이 (2026-06-17~18)

- `tool_done` 처리에서 evidence 누적 ≥2이면 `phase=verifying`, `role=verifier`로 전이하는 로직을 `electron/renderer/supervisor-state.js`에 추가했다(이 카드가 owned로 선언한 파일 범위 내).
- 엣지 케이스(confirm/error 우선, 다음 tool_start로 복귀, 3회 이상 tool_done 시 verifying 유지라는 알려진 한계)를 `tests/renderer/supervisor-state.test.js` req-8~11로 고정했다.
- 계약 세부사항은 `docs/contracts/product-harness-run-state.md`의 "Verifier 조건 (Track 1C)" 절을 따른다.
