# 작업 카드 — product-harness-contract-alignment

```yaml
task_id: product-harness-contract-alignment
title: Product harness RunSnapshot/RunLedger contract alignment
layer: product-harness
spec: docs/specs/product-agent-harness.md
branch: codex/product-harness-contract-alignment
worktree: ../mes-agent-product-harness-contract
base_branch: master
owner: Codex Desktop
reviewer: Codex + code-reviewer
spec_synced: true
conflict_policy: "이 카드는 구현 전 계약과 fixture만 소유한다. agent/server.py, event model, Electron runtime은 수정하지 않는다."
scope:
  in:
    - RunSnapshot과 RunLedger의 phase/role enum을 단일 기준으로 유지
    - 기존 SSE 이벤트를 1차 RunSnapshot으로 합성하는 mapping fixture 정의
    - 첫 구현 카드가 generate() 재작성 없이 phase/role 라벨부터 시작하도록 닫힌 지시 작성
  out:
    - agent/server.py 구현
    - 새 SSE 이벤트 타입 추가
    - RunLedger 저장소 선택 또는 영속화 구현
    - 별도 Planner/Executor/Verifier LLM 호출 분리
files:
  owned:
    - docs/contracts/product-harness-run-state.md
    - docs/contracts/run-ledger.md
    - docs/specs/product-agent-harness.md
    - docs/harness/cards/product-harness-contract-alignment.md
  readonly:
    - docs/specs/supervisor-console.md
    - electron/renderer/workflow.js
  forbidden:
    - agent/server.py
    - agent/core/events.py
    - agent/workflow/model.py
gates:
  - rg "waiting_approval|current_role" docs/specs docs/contracts
  - git diff --check
test_dod:
  unit: []
  integration: []
  smoke: []
  invariant:
    - tool-pair invariant 영향 없음
    - runtime behavior 변경 없음
  offline:
    - 새 npm/pip 다운로드 없음
docs:
  update:
    - docs/harness/phase-report.md
external_send: none
completion_promise: DONE
```

## Worker 지시

제품 내부 하네스의 첫 구현자가 enum과 필드명을 결정하지 않도록 `RunSnapshot`, `RunLedger`, `product-agent-harness.md`를 맞춰라. 기준 enum은 다음으로 고정한다.

- `phase`: `planning`, `executing`, `observing`, `verifying`, `waiting`, `reporting`, `done`, `error`
- `role`: `orchestrator`, `planner`, `executor`, `observer`, `verifier`, `safety`, `memory`, `reporter`

이 카드는 문서/fixture 전용이다. 런타임 코드는 수정하지 마라.
