# 제품 하네스 계약 — RunLedger

> 상태: writer seed 구현 완료 · 관련 스펙: `docs/specs/product-agent-harness.md`, `docs/specs/supervisor-console.md`

## 목적

`RunLedger`는 실행 중 발생한 중요한 상태 전이를 감사추적 가능한 사건 목록으로 남기는 원장이다. UI 최신 상태는 `RunSnapshot`이 담당하고, 원인 분석·증적·검증 리포트는 `RunLedger`를 기준으로 한다.

## 이벤트 범위

| 이벤트 | 기록 이유 |
|--------|-----------|
| `run_started` | 사용자 목표, thread, task type 시작점 |
| `phase_changed` | planning/executing/reviewing/waiting/done/error 전이 |
| `role_changed` | planner/executor/verifier 등 현재 책임 전이 |
| `tool_started` | 도구명, label, 핵심 인자 요약 |
| `tool_waited` | 장시간 작업 가시성, timeout escalation |
| `tool_finished` | 성공/실패, 결과 요약, 실패 분류 |
| `approval_requested` | 위험 작업 승인 질문과 분류 |
| `approval_resolved` | 승인/거부/timeout 결과 |
| `evidence_added` | 문서, 화면, 파일, 표, 로그 근거 |
| `run_finished` | 최종 상태, 산출물, 테스트/검증 요약 |

## 최소 필드

| 필드 | 의미 |
|------|------|
| `event_id` | 단조 증가 또는 UUID |
| `request_id` | 실행 식별자 |
| `thread_id` | 업무 스레드 |
| `timestamp` | 이벤트 발생 시각 |
| `event_type` | 위 이벤트 범위 중 하나 |
| `phase` | 이벤트 당시 phase: `planning`, `executing`, `observing`, `verifying`, `waiting`, `reporting`, `done`, `error` |
| `role` | 이벤트 당시 role: `orchestrator`, `planner`, `executor`, `observer`, `verifier`, `safety`, `memory`, `reporter` |
| `summary` | 사용자에게 보여줄 한 줄 요약 |
| `details` | 구조화 세부 정보 |
| `provenance` | 사용자 입력, 도구 결과, 시스템 판단 등 출처 |

## 불변식

- 비밀값, credential, 원문 대용량 로그는 기본 기록하지 않는다.
- 사용자가 승인/거부한 위험 작업은 반드시 별도 이벤트로 남긴다.
- tool 결과를 ledger에 남겨도 assistant/tool message 짝은 변경하지 않는다.
- ledger 저장 실패가 현재 실행을 깨뜨리면 안 되며, 실패 자체는 오류 요약으로 노출한다.

## 1차 구현 기준

- 초기 구현은 **append-only JSONL**을 사용한다.
- Vault markdown은 사람이 읽는 export/리포트 후속 경로로 분리한다.
- Supervisor UI는 최신 상태를 `RunSnapshot`으로 읽고, 상세 로그/증적 탭에서 `RunLedger`를 참조한다.

## 구현 결과 (2026-06-16)

- request_id 단위 구조화 RunLedger writer를 추가했다.
- 저장 경로는 `agent/run-ledgers/<task_type>/<thread_id>/<request_id>.jsonl`이다.
- `/threads/{task_type}/{thread_id}/ledger`는 구조화 RunLedger를 우선 반환하고 legacy workflow ledger를 하위 호환으로 함께 반환한다.
- `generate()`는 run/tool/approval/evidence/finish 이벤트를 phase/role과 함께 기록한다.

## 저장 전 기본 정책

- phase/role enum은 `RunSnapshot`과 동일하게 유지한다.
- 원문 tool result는 길이 제한 요약만 저장하고, 전체 원문은 기존 대화/로그 출처를 참조한다.
- `approval_requested`와 `approval_resolved`는 같은 `confirm_id`를 details에 남겨 감사추적에서 짝을 찾을 수 있게 한다.
- 저장 경로 기본값은 Vault 하위 `agent/run-ledgers/<task_type>/<thread_id>/<request_id>.jsonl`이다.
- 각 줄은 하나의 UTF-8 JSON object이며 append-only로 기록한다.
- 저장 실패는 현재 실행을 깨뜨리지 않고, 실패 요약만 감독 상태나 로그에 노출한다.
