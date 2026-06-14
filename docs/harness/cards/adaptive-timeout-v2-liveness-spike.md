# 작업 카드 — adaptive-timeout-v2-liveness-spike

```yaml
task_id: adaptive-timeout-v2-liveness-spike
title: Adaptive timeout V2 liveness spike
layer: product-harness
spec: docs/backlog/pending/V-adaptive-tool-timeout.md
branch: codex/adaptive-timeout-v2-liveness
worktree: ../mes-agent-timeout-v2
base_branch: master
owner: Codex Desktop
reviewer: Codex + code-reviewer
spec_synced: true
conflict_policy: "이 카드는 순수 timeout 분류와 run_command 계열 적용만 소유한다. Office COM kill, background registry, server event type 추가는 후속 카드다."
scope:
  in:
    - agent/core/timeouts.py에 liveness observation과 slow/stuck 분류 순수 로직 추가
    - process.run_command 관측 가능한 신호(stdout 증가, process alive, elapsed)를 구조화 결과에 반영
    - timeout 결과를 기존 TOOL_WAIT/structured error 흐름과 호환되게 설계
    - targeted unit tests 추가
  out:
    - Office COM PID kill 정책 변경
    - 백그라운드 작업 레지스트리 구현
    - 새 SSE 이벤트 타입 추가
    - LLM 별도 호출 또는 multi-agent 역할 분리
files:
  owned:
    - agent/core/timeouts.py
    - agent/tools/process.py
    - tests/unit/test_timeouts.py
    - tests/unit/test_process_liveness.py
    - docs/backlog/pending/V-adaptive-tool-timeout.md
    - docs/harness/cards/adaptive-timeout-v2-liveness-spike.md
  readonly:
    - agent/server.py
    - agent/core/events.py
  forbidden:
    - electron/renderer/chat.js
    - agent/tools/office_com.py
gates:
  - .\test.ps1 unit
  - git diff --check
test_dod:
  unit:
    - slow 분류: 진행 신호가 있으면 stuck이 아니라 slow
    - stuck 분류: 연속 무진행 관측이면 stuck
    - structured timeout result가 기존 timeout_error_text와 호환
  integration: []
  smoke: []
  invariant:
    - 기존 TOOL_WAIT 이벤트 타입 유지
    - tool-pair invariant 영향 없음
  offline:
    - 새 npm/pip 다운로드 없음
docs:
  update:
    - docs/backlog/pending/V-adaptive-tool-timeout.md
    - docs/harness/phase-report.md
external_send: none
completion_promise: DONE
```

## Worker 지시

V-2 전체 에픽을 한 번에 구현하지 말고 liveness spike만 닫아라. 첫 적용 대상은 `run_command`처럼 진행 신호를 안전하게 관측할 수 있는 경로다. COM/Office, 백그라운드 디태치, LLM 인루프 판단은 이 카드에서 구현하지 말고 후속 카드로 남겨라.

## 구현 결과 — 2026-06-14

상태: **구현 완료**

변경 요약:

- `LivenessObservation`과 `classify_liveness()`를 추가해 stdout/stderr 증가, process alive, elapsed, no-progress count를 구조화했다.
- `run_command` timeout 경로가 partial stdout/stderr를 기반으로 `slow` 또는 `stuck`을 반환한다.
- 기존 정상 완료 JSON shape와 `timeout_error_text()`의 `툴 실행 오류` 접두는 유지했다.
- Office COM, background registry, 새 SSE 이벤트, LLM 인루프 판단은 후속 카드로 남겼다.

검증 결과:

- `C:\Users\1600X\anaconda3\envs\mes-agent\python.exe -m pytest tests\unit\test_timeouts.py -q`: 13 passed
- `C:\Users\1600X\anaconda3\envs\mes-agent\python.exe -m pytest tests\unit\test_timeouts.py tests\unit\test_process_liveness.py tests\unit\test_safety.py -q --basetemp=.tmp\pytest -p no:cacheprovider`: 30 passed
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1 unit`: 현재 Codex 관리 셸에서 bare `python.exe` 접근 차단으로 실행 실패. conda env Python 직접 호출로 대체 검증했다.
