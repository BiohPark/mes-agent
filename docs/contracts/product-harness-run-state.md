# 제품 하네스 계약 — RunSnapshot

> 상태: 초안 · 구현 전 계약 · 관련 스펙: `docs/specs/product-agent-harness.md`, `docs/specs/supervisor-console.md`

## 목적

`RunSnapshot`은 현재 실행을 사용자가 감독할 수 있게 하는 최신 상태 뷰다. 서버 재시작/스레드 전환 후 완전 복구까지 보장하는 원장 모델이 아니라, UI가 "지금 무엇을 하는지"를 안정적으로 표시하기 위한 읽기 모델이다.

## 최소 필드

| 필드 | 의미 |
|------|------|
| `request_id` | 현재 실행 식별자 |
| `thread_id` | 연결된 대화/업무 스레드 |
| `task_type` | MES, Office, deploy 등 업무 타입 |
| `agent_mode` | `auto` 또는 `plan` |
| `phase` | `planning`, `executing`, `reviewing`, `waiting`, `done`, `error` |
| `role` | `orchestrator`, `planner`, `executor`, `reviewer`, `safety`, `reporter` 중 현재 주 역할 |
| `goal` | 사용자가 요청한 현재 목표 요약 |
| `current_step` | 현재 워크플로우 단계 제목/번호 |
| `current_tool` | 실행 중인 도구명과 사용자용 label |
| `risk` | `none`, `write`, `destructive`, `credential`, `unknown` |
| `approval` | 승인 대기 질문, confirm id, 위험 사유 |
| `evidence` | 최근 근거 요약 목록 |
| `started_at` / `updated_at` | 표시와 stale 판정용 시각 |

## 불변식

- `RunSnapshot`은 OpenAI message history를 대체하거나 수정하지 않는다.
- tool-pair invariant 보존은 기존 `generate()` 루프 책임으로 유지한다.
- 감사추적 원본은 `RunLedger`이며, `RunSnapshot`은 최신 상태 캐시다.
- 새 필드 추가는 하위 호환 기본값을 가져야 한다.

## 1차 구현 기준

- 기존 SSE 이벤트를 모아 snapshot을 만들 수 있어야 한다.
- `confirm` 이벤트가 있으면 `phase=waiting`과 `approval`이 채워져야 한다.
- `done`/`error` 이후 현재 도구와 승인 대기는 비워야 한다.
- 서버 영속화는 별도 카드에서 구현한다.
