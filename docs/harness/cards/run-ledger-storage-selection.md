# 작업 카드 — run-ledger-storage-selection

```yaml
task_id: run-ledger-storage-selection
title: RunLedger storage selection
layer: product-harness
spec: docs/contracts/run-ledger.md
branch: codex/run-ledger-storage-selection
worktree: current
base_branch: master
owner: Codex Desktop
reviewer: Codex
spec_synced: true
conflict_policy: "이 카드는 RunLedger 저장 방식 결정과 다음 구현 지시만 소유한다. runtime 저장 코드는 수정하지 않는다."
scope:
  in:
    - JSONL vs Vault markdown 저장 방식 선택
    - append-only 저장 실패 정책 확정
    - 후속 구현 카드의 닫힌 지시 작성
  out:
    - agent/server.py 변경
    - RunLedger writer 구현
    - Supervisor UI ledger 탭 구현
    - 기존 대화 history 또는 tool message 변경
files:
  owned:
    - docs/contracts/run-ledger.md
    - docs/harness/cards/run-ledger-storage-selection.md
    - docs/harness/phase-report.md
  readonly:
    - docs/contracts/product-harness-run-state.md
    - docs/specs/product-agent-harness.md
    - agent/obsidian_session.py
    - agent/server.py
gates:
  - rg "JSONL|append-only|저장 실패" docs/contracts/run-ledger.md docs/harness/cards/run-ledger-storage-selection.md
  - git diff --check
test_dod:
  unit: []
  invariant:
    - runtime behavior 변경 없음
    - tool-pair invariant 영향 없음
  offline:
    - 새 npm/pip 다운로드 없음
completion_promise: DONE
```

## 결정

1차 RunLedger 저장소는 **append-only JSONL**로 선택한다.

이유:

- 이벤트별 구조화 필드(`event_id`, `request_id`, `phase`, `role`, `details`)를 손실 없이 저장하기 쉽다.
- append-only 쓰기와 라인 단위 복구가 단순해 실행 중 장애에 강하다.
- Vault markdown은 사람이 읽기 좋지만, phase/role 필터링과 UI 타임라인 재구성에는 추가 파싱 비용이 든다.

## 후속 구현 지시

- 저장 경로는 Vault 하위 `agent/run-ledgers/<task_type>/<thread_id>/<request_id>.jsonl`을 기본값으로 한다.
- 각 줄은 하나의 UTF-8 JSON object이며, 쓰기 실패는 현재 실행을 중단하지 않는다.
- 저장 실패 시 supervisor 상태에는 짧은 오류 요약만 노출하고, message history/tool-pair invariant는 건드리지 않는다.
- 원문 tool result와 credential은 저장하지 않고 길이 제한 summary와 provenance만 남긴다.
- markdown export가 필요하면 JSONL 원장을 원천으로 삼는 별도 후속 카드에서 구현한다.

## 구현 결과 — 2026-06-15

상태: **결정 완료**

- RunLedger 1차 저장 방식을 append-only JSONL로 고정했다.
- Vault markdown은 사람이 읽는 export/리포트 후속 경로로 분리했다.
- runtime writer 구현은 별도 카드로 남겼다.
