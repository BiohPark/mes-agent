# 하네스 작업 카드 템플릿

작업 하나는 스펙 하나와 worktree 하나로 닫는다. 구현 worker에게 넘기기 전에 이 카드를 채운다.

```yaml
task_id: dev-harness-example
title: 짧은 작업명
layer: dev-harness # dev-harness | product-harness | supervisor
spec: docs/specs/example.md
branch: codex/example
worktree: ../mes-agent-example
base_branch: master
owner: Codex CLI | Claude Code | Ralph loop | Codex Desktop
reviewer: Codex + code-reviewer
owners:
  worktree_setup: Codex Desktop
  merge: Codex Desktop
spec_synced: false
conflict_policy: "한 worker는 files.owned만 수정한다. files.readonly는 참고만 한다. 같은 파일은 동시에 두 worker에게 배정하지 않는다."
scope:
  in:
    - 구현할 동작 1
    - 구현할 동작 2
  out:
    - 이번 작업에서 하지 않을 동작 1
    - 이번 작업에서 하지 않을 동작 2
files:
  owned:
    - path/or/module.py
  readonly:
    - docs/specs/example.md
  forbidden:
    - unrelated/path
gates:
  - .\test.ps1 ci
test_dod:
  unit: []
  integration: []
  smoke:
    - tests/smoke/test_tool_schemas.py # 툴 수 변경 시 EXPECTED_TOOL_COUNT 갱신
  invariant:
    - tool-pair invariant 테스트 필요 여부: no
  offline:
    - 런타임 pip/npm/playwright 다운로드 없음
docs:
  update:
    - docs/TRANSFORMATION_PLAN.md
  not_required:
    - README.md
external_send: false
completion_promise: DONE
```

## Critic 체크리스트

Implementation Critic:

- `scope.in`은 한 worker가 끝낼 만큼 작은가
- `scope.out`이 범위 확장을 막는가
- `files.owned`, `files.readonly`, `files.forbidden`이 worker 간 충돌을 피하는가
- `owners.worktree_setup`, `owners.merge`, `base_branch`, `spec_synced`, `conflict_policy`가 비어 있지 않은가
- 새 의존성이나 외부 도구가 폐쇄망 반입 비용을 만들지 않는가
- worker 지시가 읽을 문서, 구현 범위, 금지 범위, 반복 테스트, 최종 게이트, 완료 문구를 포함하는가

Risk/Test Critic:

- L1 루프 불변식, safety gate, `DONE` 종료에 영향을 주는가
- 테스트가 성공/실패를 판정할 만큼 구체적인가
- `test_dod`가 unit/integration/smoke/invariant/offline 기준을 포함하는가
- 툴/설정/워크플로우 변경 시 문서와 smoke count 갱신이 포함됐는가
- 히스토리 조작, compaction, vision, 끼어들기 작업은 tool-pair invariant 테스트를 착수 게이트로 갖는가
- RunLedger/RunSnapshot 같은 감사추적 모델은 계약 문서가 먼저 있는가
- 외부 모델 provider로 보낼 문서와 승인 여부가 명시됐는가

## Worker 지시 형태

```text
<spec> 명세대로 구현하라.
구현 범위는 <scope.in>으로 제한한다.
범위 밖 기능(<scope.out>)은 만들지 마라.
수정 가능 파일은 <files.owned>로 제한한다.
읽기 전용 참고 파일은 <files.readonly>이며 수정하지 마라.
매 반복마다 <gates 중 빠른 테스트>를 실행하라.
마지막에는 <최종 gate>를 실행하고 결과를 요약하라.
모든 게이트가 통과하면 DONE을 출력하라.
```
