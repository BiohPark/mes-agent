# 작업 카드 — task-T-docs-and-regression

```yaml
task_id: task-T-docs-and-regression
title: Task T docs and regression closure
layer: product-harness
spec: docs/specs/task-types-dynamic.md
branch: codex/task-T-docs-regression
worktree: ../mes-agent-task-T-docs
base_branch: master
owner: Codex Desktop
reviewer: Codex + code-reviewer
owners:
  worktree_setup: Codex Desktop
  merge: Codex Desktop
spec_synced: true
conflict_policy: "이 카드는 backend와 frontend 구현이 병합된 뒤 문서, 회귀 테스트, 수용 기준 추적만 소유한다."
scope:
  in:
    - `docs/specs/task-types-dynamic.md` 수용 기준 체크 상태 갱신
    - `docs/backlog/done/T-dynamic-task-types.md` 상태 갱신
    - `CLAUDE.md`, `CONTRIBUTING.md`의 tool count/tool list 반영 여부 확인
    - `.\test.ps1 ci`와 smoke 결과를 최종 기록
    - Computer Use 접근성 기반 sidebar 확인 결과 기록
  out:
    - backend 기능 구현
    - Electron sidebar 기능 구현
    - 신규 외부 critic 실행
files:
  owned:
    - docs/specs/task-types-dynamic.md
    - docs/backlog/done/T-dynamic-task-types.md
    - docs/harness/phase-report.md
    - CLAUDE.md
    - CONTRIBUTING.md
  readonly:
    - agent/tools/task_type.py
    - tests/smoke/test_tool_schemas.py
    - electron/renderer/chat.js
    - electron/renderer/index.html
  forbidden:
    - agent/server.py
    - agent/obsidian_session.py
gates:
  - .\test.ps1 ci
  - .\test.ps1 smoke
  - git diff --check
test_dod:
  unit: []
  integration: []
  smoke:
    - EXPECTED_TOOL_COUNT와 실제 registry count 일치 확인
  invariant:
    - tool-pair invariant 관련 backend 변경 없음
  offline:
    - 외부 모델 provider 전송 없음
docs:
  update:
    - docs/harness/phase-report.md
    - docs/specs/task-types-dynamic.md
    - docs/backlog/done/T-dynamic-task-types.md
external_send: none
completion_promise: DONE
```

## Worker 지시

Task T backend/frontend 카드가 끝난 뒤 문서와 회귀 게이트만 닫아라.
기능 코드는 수정하지 말고, 누락된 문서/테스트 상태만 정리한다.
Claude Code 사용량이 낮은 환경에서는 외부 critic을 실행하지 말고 로컬 테스트 증거를 우선한다.
