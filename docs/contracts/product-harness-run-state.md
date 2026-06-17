# 제품 하네스 계약 — RunSnapshot

> 상태: Phase 1(라벨) 구현 확정 · 실제 검증 로직(Phase 2)은 미착수 · 관련 스펙: `docs/specs/product-agent-harness.md`, `docs/specs/supervisor-console.md`

## 목적

`RunSnapshot`은 현재 실행을 사용자가 감독할 수 있게 하는 최신 상태 뷰다. 서버 재시작/스레드 전환 후 완전 복구까지 보장하는 원장 모델이 아니라, UI가 "지금 무엇을 하는지"를 안정적으로 표시하기 위한 읽기 모델이다.

## 최소 필드

| 필드 | 의미 |
|------|------|
| `request_id` | 현재 실행 식별자 |
| `thread_id` | 연결된 대화/업무 스레드 |
| `task_type` | MES, Office, deploy 등 업무 타입 |
| `agent_mode` | `auto` 또는 `plan` |
| `phase` | `planning`, `executing`, `observing`, `verifying`, `waiting`, `reporting`, `done`, `error` |
| `role` | `orchestrator`, `planner`, `executor`, `observer`, `verifier`, `safety`, `memory`, `reporter` 중 현재 주 역할 |
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

## Verifier 조건 (Track 1C)

`verifying`/`verifier`는 실제 LLM 기반 검증이 아니라 **근거 누적량 기반 라벨 휴리스틱**이다.

- **진입**: `tool_done` 처리 시 `evidence.length >= 2`이면 `phase=verifying`, `role=verifier`로 전이한다 (`electron/renderer/supervisor-state.js`의 `tool_done` 케이스).
- **이탈**: 다음 `tool_start`가 발생하면 즉시 `executing`/`executor`로 복귀한다. `confirm`/`done`/`error`는 현재 phase와 무관하게 항상 우선한다(승인·종료·오류가 검증 표시보다 먼저 보여야 한다).
- **알려진 한계**: evidence는 세션 내에서 절대 줄어들지 않는다(`appendEvidence()`가 최근 5개만 유지할 뿐 리셋하지 않음). 따라서 **3번째 이후 모든 `tool_done`에서도 `verifying`이 유지**된다 — "결과를 다시 확인 중"이 아니라 "최소 2회 근거가 쌓였다"는 근사 신호로 해석해야 한다.
- **Phase 2와의 경계**: 실제 pass/fail 판정, 명세 대비 검증, 별도 LLM 호출은 `docs/specs/product-agent-harness.md`의 "Phase 2 — Verifier 분리"에서 다룬다. 이 계약은 **표시 라벨 동작만** 보장하며 검증 정확도를 보장하지 않는다.
- **검증**: `tests/renderer/supervisor-state.test.js` req-8(confirm 우선)·req-9(error 우선)·req-10(tool_start 복귀)·req-11(evidence 한계).

## Enum 기준

초기 구현은 별도 multi-agent 호출을 만들지 않고 기존 루프 이벤트를 아래처럼 매핑한다.

| 입력 신호 | phase | role |
|----------|-------|------|
| plan 생성/승인 전 | `planning` | `planner` |
| tool 실행 중 | `executing` | `executor` |
| 화면/문서/로그 근거 수집 | `observing` | `observer` |
| 결과 확인 단계 | `verifying` | `verifier` |
| confirm/사용자 입력 대기 | `waiting` | `safety` |
| 최종 요약 작성 | `reporting` | `reporter` |
| 종료 | `done` | `orchestrator` |
| 오류 | `error` | `orchestrator` |

## 알려진 격차

- `reporting`/`reporter`는 위 Enum 표에 정의되어 있으나 `electron/renderer/supervisor-state.js` reducer에는 아직 매핑 로직이 없다(최종 요약 작성 단계 미구현). 새 SSE 이벤트나 reducer 케이스가 추가되기 전까지 이 라벨은 코드에서 도달 불가능하다. 별도 작업 카드 필요.
