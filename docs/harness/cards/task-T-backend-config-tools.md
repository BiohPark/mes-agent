# 작업 카드 — task-T-backend-config-tools

```yaml
task_id: task-T-backend-config-tools
title: Task T backend config and task type tools
layer: product-harness
spec: docs/specs/task-types-dynamic.md
branch: codex/task-T-backend-config-tools
worktree: ../mes-agent-task-T-backend
base_branch: master
owner: Codex Desktop
reviewer: Codex + code-reviewer
owners:
  worktree_setup: Codex Desktop
  merge: Codex Desktop
spec_synced: true
conflict_policy: "이 카드는 backend config, task type tools, task-config API, 관련 backend tests만 소유한다. Electron sidebar 렌더링은 별도 카드에서 수행한다."
scope:
  in:
    - `agent/obsidian_session.py`의 `TASK_CONFIGS`를 `_DEFAULT_TASK_CONFIGS` + `get_task_configs()`로 동적화
    - Vault `agent/task_types.json` 오버레이 읽기/쓰기 helper 추가
    - `agent/server.py`의 `TASK_CONFIGS` import/조회 제거 및 `/task-config` 동적화
    - 신규 `agent/tools/task_type.py`에 `task_type_create`, `task_type_remove` 2종 추가
    - unit/integration/smoke 테스트 추가 또는 갱신
  out:
    - Electron sidebar 동적 렌더링
    - 업무 타입 순서 재정렬
    - 시스템 프롬프트 UI 편집
    - 업무 타입별 워크플로우 템플릿 자동 생성
files:
  owned:
    - agent/obsidian_session.py
    - agent/server.py
    - agent/tools/task_type.py
    - tests/unit/test_task_type_tools.py
    - tests/integration/test_task_config_api.py
    - tests/smoke/test_tool_schemas.py
    - CLAUDE.md
  readonly:
    - docs/specs/task-types-dynamic.md
    - docs/backlog/done/T-dynamic-task-types.md
    - CONTRIBUTING.md
    - agent/tools/_safety.py
    - agent/tools/__init__.py
  forbidden:
    - electron/renderer/index.html
    - electron/renderer/chat.js
    - electron/renderer/style.css
gates:
  - C:\Users\1600X\anaconda3\envs\mes-agent\python.exe -m pytest tests/unit/test_task_type_tools.py tests/integration/test_task_config_api.py tests/smoke/test_tool_schemas.py -q --tb=short
  - .\test.ps1 ci
  - git diff --check
test_dod:
  unit:
    - `task_type_create`: 중복 이름 거부, 새 이름 Vault 저장
    - `task_type_remove`: 기본 5타입 삭제 거부, 커스텀 타입 삭제
    - `get_task_configs()`: Vault 없음 기본값, Vault 있음 머지
  integration:
    - `GET /task-config`: 기본 5타입 반환
    - Vault 커스텀 타입 추가 후 기본 + 커스텀 반환
  smoke:
    - `tests/smoke/test_tool_schemas.py::EXPECTED_TOOL_COUNT`를 신규 툴 2개만큼 갱신
  invariant:
    - `agent/server.py generate()` message history와 tool-pair invariant 변경 없음
  offline:
    - 런타임 pip/npm/playwright 다운로드 없음
docs:
  update:
    - CLAUDE.md
  not_required:
    - README.md
external_send: none
completion_promise: DONE
```

## Worker 지시

`docs/specs/task-types-dynamic.md` 중 backend config/tool/API 범위만 구현하라.
Electron renderer 파일은 수정하지 마라.
새 도구 추가 시 `MANIFEST`를 사용하고, 자동 registry를 수동 편집하지 마라.
`TASK_CONFIGS` 이름은 공개 import로 유지하지 말고 호출부를 `get_task_configs()`로 교체하라.
마지막에는 지정된 pytest 묶음, 가능하면 `.\test.ps1 ci`, `git diff --check` 결과를 요약하라.
