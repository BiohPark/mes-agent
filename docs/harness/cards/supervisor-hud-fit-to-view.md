# 작업 카드 — supervisor-hud-fit-to-view

```yaml
task_id: supervisor-hud-fit-to-view
title: Supervisor HUD and workflow fit-to-view follow-up
layer: supervisor
spec: docs/specs/supervisor-console.md
branch: codex/supervisor-hud-fit-to-view
worktree: ../mes-agent-supervisor-hud
base_branch: master
owner: Claude Code 우선, 차단 시 Claude Code 셋업 원인분석
reviewer: Codex + code-reviewer
owners:
  worktree_setup: Codex Desktop
  merge: Codex Desktop
spec_synced: false
conflict_policy: "이 카드는 Electron renderer UX와 관련 문서만 소유한다. backend event/model/server 파일은 수정하지 않는다."
scope:
  in:
    - 실행 중 기본 busy mode를 "작게 비켜 보기 HUD" 방향으로 정리
    - 감독 탭의 현재 목표/단계/도구/승인/위험 상태가 실제 SSE 중 갱신되는지 확인
    - 워크플로우 그래프 최초 fit-to-view와 현재 실행 노드 강조를 검증
    - 스크린샷이 실패하는 PC에서는 Computer Use 접근성 트리 기반 확인을 공식 검증으로 기록
  out:
    - agent/server.py 변경
    - RunSnapshot/RunLedger 서버 영속화
    - 새 SSE 이벤트 타입 추가
    - 새 npm/pip/playwright 의존성 추가
files:
  owned:
    - electron/main.js
    - electron/preload.js
    - electron/renderer/hud.html
    - electron/renderer/hud.js
    - electron/renderer/chat.js
    - electron/renderer/workflow.js
    - electron/renderer/style.css
    - electron/renderer/index.html
    - docs/specs/supervisor-console.md
    - docs/harness/cards/supervisor-hud-fit-to-view.md
  readonly:
    - docs/harness/cards/supervisor-phase1-reducer.md
    - docs/ORCHESTRATION_GUIDE.md
  forbidden:
    - agent/server.py
    - agent/core/events.py
    - agent/workflow/model.py
    - package.json
gates:
  - cmd /c node --check electron\renderer\chat.js
  - cmd /c node --check electron\renderer\workflow.js
  - powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke
  - git diff --check
test_dod:
  unit: []
  integration: []
  smoke:
    - Claude Code L0 smoke 통과 또는 실패 분류/원인분석 기록
  invariant:
    - backend message history 조작 없음
    - tool-pair invariant 영향 없음
  offline:
    - 새 런타임 다운로드 없음
docs:
  update:
    - docs/specs/supervisor-console.md
    - docs/harness/phase-report.md
  not_required:
    - README.md
external_send: none
completion_promise: DONE
```

## Worker 지시

`docs/specs/supervisor-console.md` Phase 1 후속 중 HUD/fit-to-view 범위만 구현하라.
수정 가능 파일은 `electron/renderer/*`와 이 카드/관련 스펙 문서로 제한한다.
서버 이벤트, RunSnapshot/RunLedger, workflow model은 수정하지 마라.
새 의존성을 추가하지 마라.
마지막에는 `node --check`, 하네스 smoke, `git diff --check`, Electron 접근성 확인 결과를 요약하라.

Claude Code 실행이 막히면 Codex가 이 구현을 대신하지 않는다. 실패 분류, 재현 명령, stdout/stderr 위치, 다음 셋업 조치를 남기고 Claude Code 정상화 작업으로 전환한다.

## 구현 결과 — 2026-06-14

상태: **구현 완료**

- 기본 busy mode를 `hud`로 변경하고 헤더 메뉴에 `작게 비켜 보기`를 추가했다.
- 기존 협업 HUD 창을 `mode=agent` payload로 재사용해 실행 중 목표/단계/도구/경과/위험 상태를 표시한다.
- 작업 감독 HUD의 `자세히 보기`는 메인 창을 복원하고, 닫기 버튼은 현재 실행 중단 버튼을 호출한다.
- 워크플로우 그래프는 최초 렌더 fit-to-view를 유지하고, 실행/대기 노드가 바뀌면 현재 노드 쪽으로 뷰를 보정한다.
- 서버 이벤트, RunSnapshot/RunLedger 영속화, workflow model은 변경하지 않았다.
