# 작업 카드 — supervisor-phase1-reducer

```yaml
task_id: supervisor-phase1-reducer
title: 감독 콘솔 Phase 1 상태 reducer 설계
layer: supervisor
spec: docs/specs/supervisor-console.md
branch: codex/supervisor-phase1-reducer
worktree: ../mes-agent-supervisor-phase1
base_branch: master
owner: Codex CLI 또는 Claude Code
reviewer: Codex + code-reviewer
owners:
  worktree_setup: Codex Desktop
  merge: Codex Desktop
spec_synced: true
conflict_policy: "이 카드는 Electron renderer와 관련 문서만 소유한다. 서버/모델 파일은 동시에 다른 worker가 맡을 수 있지만 이 카드에서는 수정하지 않는다."
scope:
  in:
    - 기존 SSE 이벤트를 감독 콘솔 상태로 모으는 frontend reducer 계약 정의
    - 현재 목표, 현재 단계, 현재 도구, 경과 시간, 승인 대기, 근거 요약 상태 필드 정의
    - reducer 입력 이벤트 fixture와 기대 상태를 문서 또는 테스트로 고정
    - Electron renderer 파일 소유 범위와 후속 구현 게이트 정의
  out:
    - agent/server.py 런타임 역할 분리
    - RunSnapshot/RunLedger 서버 영속화
    - 새 외부 프레임워크 또는 npm 의존성 추가
    - 제품 내부 Planner/Executor/Verifier 호출 분리
files:
  owned:
    - electron/renderer/chat.js
    - electron/renderer/workflow.js
    - electron/renderer/style.css
    - electron/renderer/index.html
    - docs/specs/supervisor-console.md
    - docs/harness/cards/supervisor-phase1-reducer.md
  readonly:
    - docs/ORCHESTRATION_GUIDE.md
    - docs/specs/development-harness.md
  allowed:
    - electron/renderer/chat.js
    - electron/renderer/workflow.js
    - electron/renderer/style.css
    - electron/renderer/index.html
    - docs/specs/supervisor-console.md
    - docs/harness/cards/supervisor-phase1-reducer.md
  forbidden:
    - agent/server.py
    - agent/core/events.py
    - agent/workflow/model.py
    - package.json
gates:
  - powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke
  - git diff --check
  - 수동 DOM/reducer 검증 기준을 작업 결과에 명시
test_dod:
  unit: []
  integration: []
  smoke:
    - powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke
  invariant:
    - 새 backend message history 조작 없음
    - tool-pair invariant 영향 없음
  offline:
    - 새 npm/pip/playwright 다운로드 없음
docs:
  update:
    - docs/specs/supervisor-console.md
    - docs/harness/phase-report.md
  not_required:
    - README.md
    - CONTRIBUTING.md
external_send: false
completion_promise: DONE
```

## Worker 지시 초안

```text
docs/specs/supervisor-console.md Phase 1 중 "기존 SSE 이벤트를 감독 콘솔 상태로 모으는 frontend reducer"만 설계/구현하라.
수정 범위는 electron/renderer/chat.js, workflow.js, style.css, index.html 및 관련 문서로 제한한다.
agent/server.py, agent/core/events.py, workflow model은 수정하지 마라.
새 npm 의존성은 추가하지 마라.
현재 목표, 단계, 도구, 경과 시간, 승인 대기, 근거 요약이 한 상태 객체로 모이도록 한다.
테스트 스크립트가 없으면 reducer 입력 fixture와 기대 상태를 문서에 명시하고, 후속 테스트 도입 지점을 적어라.
마지막에는 git diff --check와 Codex CLI smoke 결과, 사용자 확인 방법을 요약하라.
모든 게이트가 통과하면 DONE을 출력하라.
```

## Critic 메모

- Implementation Critic: 서버 역할 분리와 UI reducer를 한 worker에게 섞지 않는 것이 핵심이다.
- Risk/Test Critic: 현재 `package.json`에 frontend test script가 없으므로, 첫 작업의 중요한 산출물은 reducer 테스트 기준을 명시하는 것이다.
- 외부 전송은 기본 false다. 실제 Codex CLI/Claude critic에 문서를 보낼 때만 사용자 승인 후 true로 바꾼다.

## 구현 결과 — 2026-06-13

상태: **구현 완료, 수동 UI 확인 대기**

변경 파일:

- `electron/renderer/index.html`: 우측 패널 첫 탭으로 `감독` 탭과 DOM 슬롯 추가
- `electron/renderer/workflow.js`: 기존 SSE 이벤트를 감독 상태로 모으는 reducer와 `window.workflowPanel.handleEvent()` 공개
- `electron/renderer/chat.js`: `handleEvent()` 진입 시 감독 reducer에 이벤트 복사 전달
- `electron/renderer/style.css`: 감독 패널 카드/상태/근거/오류 표시 스타일 추가

Reducer 입력 fixture:

```json
[
  { "request_id": "req-1" },
  { "type": "workflow_update", "workflow": { "title": "MES 검증", "steps": [{ "id": "a", "title": "문서 수집", "status": "done" }, { "id": "b", "title": "화면 확인", "status": "running" }] } },
  { "type": "tool_start", "tool": "vision_capture", "label": "화면 캡처" },
  { "type": "tool_done", "tool": "vision_capture", "result": "캡처 완료" },
  { "type": "confirm", "question": "배포 명령을 실행할까요?", "risk": "destructive", "command": "deploy-prod" },
  { "type": "done" }
]
```

기대 상태:

- `goal`: `MES 검증`
- `step`: `1/2 · 화면 확인`
- `tool_start` 이후 `currentToolLabel`: `화면 캡처`, elapsed timer 증가
- `tool_done` 이후 근거 요약에 `vision_capture: 캡처 완료`
- `confirm` 이후 `agentState`: `waiting`, `approvalText`: 승인 질문, `risk`: `destructive`
- `done` 이후 `agentState`: `idle`, 승인 대기 해제, 현재 도구 비움

수동 확인 방법:

1. Electron 앱에서 우측 패널 첫 탭이 `감독`으로 보이는지 확인한다.
2. 자동화 실행 중 `workflow_update`, `tool_start`, `tool_done`, `confirm`, `done` 이벤트가 들어올 때 감독 탭의 목표/단계/도구/승인/근거가 갱신되는지 확인한다.
3. 워크플로우/로그 탭의 기존 표시가 유지되는지 확인한다.
