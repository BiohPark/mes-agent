# 작업 카드 — task-T-frontend-sidebar

```yaml
task_id: task-T-frontend-sidebar
title: Task T frontend dynamic sidebar
layer: product-harness
spec: docs/specs/task-types-dynamic.md
branch: codex/task-T-frontend-sidebar
worktree: ../mes-agent-task-T-frontend
base_branch: master
owner: Codex Desktop
reviewer: Codex + code-reviewer
owners:
  worktree_setup: Codex Desktop
  merge: Codex Desktop
spec_synced: true
conflict_policy: "이 카드는 backend 동적 API가 병합된 뒤 Electron sidebar 렌더링만 소유한다. backend config/tool 파일은 읽기 전용이다."
scope:
  in:
    - `electron/renderer/index.html`의 하드코딩 task group을 `task-groups-container`로 교체
    - `electron/renderer/chat.js`에서 `/task-config` 기반 `renderTaskGroups()` 추가
    - `initWhenReady()`에서 기존 thread load 전에 task group 렌더링
    - 기존 `data-task` 기반 sidebar 동작 유지
    - Computer Use 접근성 트리로 기본 내장 타입 sidebar 노출 확인
  out:
    - backend `get_task_configs()` 구현
    - 신규 task type tool 구현
    - 업무 타입 순서 재정렬 UI
    - 시스템 프롬프트 편집 UI
files:
  owned:
    - electron/renderer/index.html
    - electron/renderer/chat.js
    - docs/harness/cards/task-T-frontend-sidebar.md
  readonly:
    - docs/specs/task-types-dynamic.md
    - agent/server.py
    - agent/obsidian_session.py
  forbidden:
    - agent/tools/task_type.py
    - tests/smoke/test_tool_schemas.py
gates:
  - cmd /c node --check electron\renderer\chat.js
  - Computer Use accessibility check for `task-groups-container` rendered groups
  - git diff --check
test_dod:
  unit: []
  integration: []
  smoke: []
  invariant:
    - backend message history 조작 없음
  offline:
    - 새 npm/pip/playwright 다운로드 없음
docs:
  update:
    - docs/harness/cards/task-T-frontend-sidebar.md
  not_required:
    - CLAUDE.md
external_send: none
completion_promise: DONE
```

## Worker 지시

`docs/specs/task-types-dynamic.md` 중 Electron sidebar 동적 렌더링 범위만 구현하라.
backend 카드가 완료된 상태를 전제로 `/task-config` 응답을 사용한다.
하드코딩 업무 그룹은 제거하되 기존 sidebar 접기/펼치기, thread list, search 동작을 깨지 않게 하라.
마지막에는 `node --check`, Computer Use 접근성 확인, `git diff --check` 결과를 요약하라.
