# L1 — 에이전트 실행 루프 계약서 (clean)

> **상태: G1·G2·G3·G4 전부 구현 완료(2026-06-10).** 본 계약서는 구현의 기준 명세로 보존한다.
> 대상: `agent/server.py`의 `generate()` 루프 개선.
> **출처(클린)**: ① mes-agent 본인 코드, ② 일반 에이전트 루프 지식,
> ③ openclaw(MIT)·LangGraph/Temporal 공개 패턴. **유출 소스 미사용.** (거버넌스: `docs/CLAW_PORT_PLAN.md`)
> 목표: 현 루프를 "강한 에이전트급 문제해결력"으로. 4개 격차(G1~G4) 해소.

---

## 0. 현재 구조 요약 (있는 것)

`generate(message, thread_id, task_type)` async 제너레이터, SSE 스트리밍.
`for _step in range(_MAX_STEPS=40)`: 컨텍스트 사용량 emit → 모델 스트리밍
(`client.chat.completions.create(tools=TOOLS, stream=True)`) → 텍스트/`tool_calls_raw`
누적·`finish_reason` 추적 → assistant 메시지 append → **종료 판정** → tool 디스패치
(`run_tool`) → `ask_user __confirm__` 처리 → workflow/RunState 동기화 → tool 메시지 append.

이미 충족: 스트리밍 tool-calling, 자동 디스커버리 레지스트리, 확인 팝업 골격
(`__confirm__`+`/confirm`+`asyncio.Event`), 정의/실행상태 분리, 단계별 재시도, Origin/토큰 보안.

---

## 1. 입력 / 출력 (계약, 현행 시그니처 유지)

- **입력**: `message:str`, `thread_id:str`, `task_type:str`.
- **출력(불변)**: SSE 이벤트 스트림. 기존 이벤트 계약 유지
  (`REQUEST_ID, CONTEXT_USAGE, AGENT_STATE{thinking|running|waiting|idle}, TEXT,
  TOOL_START, TOOL_DONE, CONFIRM, WORKFLOW_UPDATE, ERROR, DONE`).
- **신규 이벤트**(추가만, 제거 금지): `COMPACTION`(압축 발생 고지), `PLAN`(계획 표시),
  `APPROVAL_REQUEST`(위험 동작 승인 — `CONFIRM`을 일반화하거나 재사용).

## 2. 상태 모델 (정의 vs 실행상태 — C3 계승)

- **정의(불변)**: `TOOLS`(스키마), 시스템 프롬프트, `_MAX_STEPS`, `_CONTEXT_MAX_TOKENS`,
  `WorkflowDefinition`(nodes/connections). → 루프 내 재할당 금지.
- **실행상태(가변)**: `messages`(누적 대화), `_step`(턴 카운터), `request_id`,
  `WorkflowRunState`(`node_states`), 그리고 **신규**: `nudge_count`, `compaction_count`,
  `session_allowlist`(아래 §5). 각 회전 종료마다 일관되게 갱신.
- 메모: 회전 간 유지되는 핵심 가변은 `messages`·`_step`·`nudge_count`·`compaction_count`.
  나머지(텍스트/툴콜 버퍼)는 회전-로컬.

## 3. 루프 1회전 해부 (개선 후)

순서: **(a) 중단확인 → (b) compaction[G1] → (c) 사용량 emit → (d) 모델 스트리밍
→ (e) 종료/계속 판정[G2] → (f) 디스패치 전 안전 게이트[G3] → (g) 실행 → (h) 환류**.

(b)·(e)·(f)가 신규/강화 지점. 나머지는 현행 유지.

## 4. G1 — 컨텍스트 Compaction (신규, 최우선)

- **계약**: 모델 호출 직전, `_estimate_tokens(messages)`가 임계치
  (`_CONTEXT_MAX_TOKENS * COMPACT_RATIO`, 예 0.8 = 102k) 초과 시 압축한다.
- **전략(단계적, 새 의존성 없이)**:
  1. system 메시지(들)와 **최근 N턴**(예: 마지막 6 메시지)은 **항상 보존**.
  2. 그 사이 오래된 메시지를 **요약 메시지 1개로 대체**: 동일 로컬 LLM(`get_client`)에
     "지금까지의 진행/결정/미해결을 ≤500토큰으로 요약" 호출 → `{"role":"system",
     "content":"[이전 진행 요약]\n..."}` 로 치환.
  3. 요약조차 한도 초과면 가장 오래된 tool 결과부터 **잘라내기(truncate)**.
- **불변조건**: 압축은 `tool_calls` ↔ `tool`(tool_call_id) **짝을 깨면 안 된다**
  (OpenAI API 제약). 짝 단위로만 제거/요약. assistant(tool_calls) 없이 떠도는
  tool 메시지가 생기지 않게 한다.
- **출력**: 압축 시 `COMPACTION` SSE로 사용자 고지(투명성).
- **한도**: `compaction_count`로 무한 압축 루프 방지(상한 도달 시 `prompt_too_long`류 종료).

## 5. G3 — 중앙 집중 안전 게이트 = APPROVE1 (신규, 강제)

> 철학: **막지 않는다, 게이팅한다.** PowerShell·bash·sqlplus 자유 사용,
> 위험한 것만 실행 전 반드시 확인. **모델 협조에 의존하지 않고 디스패치 경로에서 강제.**

- **위치**: §3(f) — `run_tool` 호출 **직전**, 모든 tool_call에 대해 루프가 직접 호출.
  (현재처럼 툴 내부 자율 호출 ❌ → 루프 레벨 강제 ✅)
- **판정**: `agent/tools/_safety.py`를 확장한 `classify_risk(tool_name, args) -> 'safe'|'mutate'|'destructive'`.
  - 기존 `is_dangerous_command`/`is_protected_path` 재사용 → `destructive`.
  - 읽기성(SELECT·Get-*·read_*·screen 조회) → `safe`.
  - 그 외/모호 → **기본 `mutate`(확인)**. ← fail-safe: 모르는 건 묻는다.
- **동작**:
  - `safe` → 즉시 실행.
  - `mutate`/`destructive` → 기존 `__confirm__` 메커니즘 재사용해 `APPROVAL_REQUEST`
    (또는 `CONFIRM`) emit → `asyncio.Event` 대기. `destructive`는 **명령 전문 강조 + 기본 포커스 '아니오'**.
  - 응답 3-택: **예**(이번만) / **항상**(패턴을 `session_allowlist`에 추가→이후 `safe`) / **아니오**(거부, 사유 → tool 결과로 환류).
- **무인 fallback**: 사용자 미연결(헤드리스/배치)일 때 `mutate`+ 는 `defer`(보류) 또는
  `deny`(거부) — 설정값. **무인 자동 승인 금지.**
- **불변조건**: 거부/타임아웃도 반드시 짝 맞는 `tool` 결과 메시지를 환류해 API 짝 제약 유지.
- **감사**: 모든 판정·응답을 세션 로그에 기록.

## 6. G2 — 종료/계속 판정 (강화)

- **종료(현행 유지)**: `stop_flag` / 예외 / `_MAX_STEPS` 도달(`for-else`).
- **개선 — continuation nudge**: 모델이 `finish_reason != "tool_calls"`로 멈췄을 때
  **즉시 종료하지 않고** 판정:
  - `nudge_count < MAX_NUDGES`(예 2) **그리고** 직전 응답이 "작업 완료"가 아닌
    중간 상태로 보이면 → `{"role":"user","content":"[시스템] 작업이 끝나지 않았다.
    중단 사유가 없으면 계속 진행하라."}` 주입 후 **루프 계속**, `nudge_count++`.
  - 완료로 판단되거나 nudge 한도 소진 → 정상 종료(현행 `idle`+`DONE`).
- **불변조건**: `MAX_NUDGES` 상한으로 무한루프 방지. nudge는 텍스트-only stop에만,
  tool_call이 있으면 적용 안 함(원래 계속됨).

## 7. G4 — 계획/진행추적 = PLAN1 (모드 선택)

- **모드 설정**: `agent_mode = 'auto' | 'plan'`(요청 파라미터 또는 설정).
  - `auto`(기본·현행): 계획 없이 바로 실행, 위험 동작만 §5 팝업.
  - `plan`: task 받으면 **먼저 계획만 생성** — 첫 모델 호출을 "실행 말고 단계 목록(JSON)만
    내라"로 제약 → `WorkflowDefinition`(nodes/connections)으로 적재 → `PLAN` SSE로 표시 →
    사용자 승인 후 실행 루프 진입. 실행 중 각 단계 `WorkflowRunState`로 추적(이미 있는 동기화 재사용).
- **진행추적**: 기존 `workflow_*` 도구·`set_node_status`·`WORKFLOW_UPDATE` 그대로 활용.
- 우선순위: G1·G2·G3 다음. (있는 workflow 인프라 위에 모드 스위치만 얹는 수준)

## 8. C2 — 재시도(현행 유지·일반화)

- 현재 "워크플로 step `max_retry` 기반 재시도"는 유지.
- 일반화: step이 없는 일반 실행에도 활동별 기본 재시도 정책(횟수·백오프) 적용 옵션.
- 회복 한도는 무한루프 방지 불변조건으로 보존.

## 9. 실패 모드 정리

| 상황 | 처리 |
|---|---|
| 모델 호출 예외 | 현행 `except` → `ERROR`+`idle`+`DONE`. (선택: 1회 재시도 후 실패) |
| 잘못된 tool args(JSON) | `run_tool` 예외 → 오류 문자열을 tool 결과로 환류(모델 자기수정 유도). 현행 유지. |
| 컨텍스트 초과 | §4 compaction 시도 → 실패 시 종료. |
| 위험 동작 무인 | §5 fallback(defer/deny). |
| 짝 안 맞는 tool_result | **금지**. compaction/거부/abort 모든 경로에서 짝 보존(불변조건). |

## 10. 불변조건 (테스트 1급 대상)

- I1. 매 회전 후 `messages`의 `tool_calls`↔`tool` 짝이 항상 정합.
- I2. `safe`가 아닌 모든 tool 실행은 승인 이벤트를 거친다(디스패치 경로에서 강제).
- I3. `_step ≤ _MAX_STEPS`, `nudge_count ≤ MAX_NUDGES`, `compaction_count ≤ MAX_COMPACT` (무한루프 불가).
- I4. SSE는 어떤 종료 경로든 마지막에 `DONE`(또는 `ERROR`→`DONE`)으로 닫힌다.
- I5. compaction은 system 및 최근 N턴을 보존한다.

## 11. 우선순위 / 페이즈 C(TDD) 진입 순서

1. **G3 안전 게이트(APPROVE1)** — 위험 직접 통제, 가장 시급. (I2) ✅ **완료(2026-06-10)**
   - `classify_risk()`(`_safety.py`) + `generate()` 디스패치 직전 강제 + 기존 CONFIRM 팝업 재사용(예/항상/아니오) + 세션 허용목록 + 타임아웃=거부.
   - 테스트: `tests/unit/test_safety.py`(classify_risk), `tests/integration/test_server_chat.py::TestSafetyGate`(거부·승인·항상·safe무확인·타임아웃). 전체 374 passed.
2. **G1 compaction** — 긴 작업 천장 제거. (I1·I5) ✅ **완료(2026-06-10)**
   - `agent/core/compaction.py`(`compact_messages`, 짝보존) + `server.generate()` 루프 진입부 배선 + `_summarize_history`(비스트리밍 요약, 주입식) + `COMPACTION` 이벤트 + `MAX_COMPACT=3`.
   - 테스트: `tests/unit/test_compaction.py`(7), `tests/integration/test_server_chat.py::TestCompaction`(2). 전체 383 passed.
3. **G2 continuation nudge** — 조급한 종료 해소. (I3) ✅ **완료(2026-06-10)**
   - `server.generate()` 종료 분기: 도구 사용 도중(`tool_rounds>0`) 텍스트 조기종료 시 `MAX_NUDGES=2` 내 '계속' 주입. 잡담·되묻기(`?`)·사용자중단 제외.
   - 테스트: `tests/integration/test_server_chat.py::TestContinuationNudge`(4). 전체 387 passed.
4. **G4 plan 모드(PLAN1)** — 다단계 견고성. (있는 인프라 재사용) ✅ **완료(2026-06-10)**
   - `agent_mode='plan'`: 계획 단계 실행도구 차단 + 계획완료 시 `plan_approval` CONFIRM → 승인 후 `plan_phase=False`로 실행. 기존 workflow_*·패널·`_resolve_confirm` 재사용. 헤더 토글.
   - 테스트: `tests/integration/test_server_chat.py::TestPlanMode`(3). 전체 390 passed.

> **L1 루프 강화 트랙 완료** — G3·G1·G2·G4 모두 ✅. (계약서 §5·§4·§6·§7 충족)

각 항목: 불변조건 → 실패 테스트 먼저 → 최소 구현. `agent/server.py`의 `generate()`와
`agent/tools/_safety.py` 중심, 새 의존성 없이.
