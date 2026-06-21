# ADR-0003 — 적응형 도구 타임아웃 (무한 행 방지 + 작업 가시성)

| 항목 | 내용 |
|------|------|
| **상태** | Accepted (1단계, 2단계 일부) / Proposed (2단계 — 자동 백그라운드 디태치) — 2026-06-12, 갱신 2026-06-18 |
| **결정자** | Bioh Park |
| **대상 파일** | `agent/core/timeouts.py`, `agent/server.py` `generate()`, `agent/tools/office_com.py` |
| **관련 ADR** | ADR-0002 (L1 루프 계약 — I1 짝보존·I4 DONE 마감 계승) |
| **관련 백로그** | `docs/backlog/pending/V-adaptive-tool-timeout.md` |

## 컨텍스트

Excel 작업이 **3분+ 무한 펜딩**되고 사용자는 진행 상황을 알 수 없었다. 조사 결과 근본 원인은 한 도구가 아니라
**도구 계층 전반의 타임아웃 불일치**였다: `office_com`은 타임아웃이 전혀 없어(`_on_com_thread.result()`) 무한 행에 빠질 수 있고,
`server.py`의 디스패치(`run_in_executor(run_tool)`)에도 통일된 캡이 없어 자체 캡 없는 도구 하나가 **SSE 스트림 전체를 영구 정지**시켰다.

## 결정

**1단계(긴급, Accepted)** — 무한 행을 구조적으로 제거하고 진행을 가시화한다.
- 순수 모듈 `agent/core/timeouts.py`(baseline·escalation·classify) + `server.py` 디스패치 통일 타임아웃(`_run_tool_watched`).
- 도구별 작은 baseline에서 시작 → 단계적 연장(같은 in-flight 작업을 더 대기) → 캡 도달 시 구조화 오류(`툴 실행 오류` 접두 → 기존 error-step/UI 경로 재사용).
- 길어지면 `TOOL_WAIT` SSE로 사용자에게 "더 기다리는 중" 내레이션 + 경과시간 + 중단 강조.
- `office_com`: `OFFICE_COM_TIMEOUT` 워치독 + **PID 스코프 킬**(사용자가 직접 연 Office 보호) + executor 재생성 + Open 대화상자 억제(`Notify=False`).

**2단계(Proposed)** — 진행도(liveness) 탐지로 slow/stuck 구분, 에이전트 인루프 판단(재시도/대안/질의), 자동 백그라운드 디태치. 상세 백로그 V.

## 불변조건 (ADR-0002 계승)

- I1: 타임아웃 결과도 반드시 짝 맞는 `tool` 메시지를 환류(API 짝 제약 유지).
- I4: 어떤 타임아웃 경로든 SSE는 마지막에 `DONE`으로 닫힌다(무한 펜딩 금지).
- 무인 자동 동작 아님: 타임아웃은 사용자에게 투명 고지(`TOOL_WAIT`/구조화 오류).

## 출처 (클린룸)

본인 코드 + 일반 에이전트 루프 지식 + openclaw(MIT)/LangGraph 공개 패턴
+ **claw-code(MIT — 사용자가 라이선스/클린룸 적합성 확인): 패턴만 참고(구조화·분류된 타임아웃 결과 `failureClass`/`provenance`, 장기 실행 자동 백그라운드 디태치).** 코드 복붙 없음.

## 결과

- 1단계 구현 + 테스트(`test_timeouts.py`·`test_office_com_timeout.py`·`TestToolTimeout`) 통과.
- 2단계는 백로그 V로 분리(진행도 탐지·인루프 판단·디태치).

## 2단계 세부설계 — 자동 백그라운드 디태치 (Phase 3, Proposed)

### 발견된 선결 버그 (Phase 2 보완, Accepted — 구현됨)

`_run_tool_watched`(`agent/server.py`)의 디스패치 캡은 도구가 스스로 요청한 `timeout` 인자와 무관하게 항상
`timeout_cap()`(기본 90s) 고정값을 썼다. `_TOOL_ALTERNATIVES["run_command"]`(`timeouts.py`)가 LLM에게
"timeout을 120으로 늘려 재시도"를 회복 옵션으로 추천하지만, 실제로 LLM이 그 추천을 따라도 디스패치 캡이
먼저 끊어 `progressed=False`로 잘못 분류했다. `effective_cap(name, arguments)`을 추가해 도구가 요청한
timeout을 존중하되 `TOOL_TIMEOUT_HARD_CEILING`(기본 300s)으로 무한 행 방지 원칙을 유지한다.

### 검토한 설계: 반복 내 지연 폴링 (Rejected)

도구 1개의 `tool_done`을 같은 `for tc in tool_calls_raw` 반복에서 건너뛰고, 다음 외부 반복 최상단
(`_pending_messages` 드레인 지점, server.py 약 625줄)에서 완료를 폴링해 늦게 append하는 방식을 검토했다.

**기각 이유**: 다음 LLM 호출(`client.chat.completions.create()`)은 직전 반복에서 보낸 모든
`tool_calls`에 대응하는 `tool` 메시지가 이미 채워져 있다고 가정한다(I1). 백그라운드 작업이 바로 다음
반복 시작 전까지 끝나지 않으면 **고아 `tool_calls`**가 발생해 다음 LLM 호출이 깨진다. "기다리는 시점을
한 번 더 미루는 것"일 뿐 진짜 백그라운드가 아니며, 완료 타이밍을 보장할 수 없어 I1을 깰 위험이 있다.

### 채택 설계: 즉시 ack + 기존 인프라로 지연 전달 (Proposed)

I1을 절대 깨지 않는다 — 백그라운드로 보낼 도구도 **같은 반복 안에서 즉시 tool 메시지를 채운다**. 단,
내용은 실제 결과가 아니라 "시작됨" placeholder다. 실제 결과는 **나중에 별도 턴으로** 전달한다.

1. **즉시 ack(I1 무위험)**: 도구가 `should_background(name, arguments)`(신규, timeouts.py)에 해당하면
   `_run_tool_watched`가 결과를 기다리지 않고 즉시
   `{"background": true, "task_id": "...", "message": "백그라운드로 시작됨, 완료되면 알려드립니다"}`를
   `tool` 메시지로 반환한다. LLM은 이걸 보고 "백그라운드로 처리 중"이라고 사용자에게 안내하거나 다른
   작업을 계속할 수 있다.
2. **레지스트리**: 실제 작업은 기존 `office_com.py` `_on_com_thread` 같은 전용 executor에 제출된 채로
   신규 모듈 레벨 dict `_background_tasks: dict[str, dict]`(task_id → {future, task_type, thread_id,
   tool, started_at})에 등록한다(`_pending_messages`/`_pending_confirms`와 동일한 인메모리 패턴).
3. **지연 전달(완전히 기존 인프라 재사용)**: 신규 워치독 루프(`_background_watchdog`,
   `_control_loop`(server.py 1434줄)와 동일한 구조의 `asyncio.sleep` 폴링)가 완료된 task를 찾으면
   해당 `task_type`/`thread_id`가 **현재 활성 실행 중이 아닐 때만**(`_active_threads` 신규 set으로 추적)
   `generate(f"[배경 작업 완료] {tool}: {결과요약}", task_type, thread_id, auto_confirm="deny")`를
   헤드리스로 호출한다 — 백로그 O의 `_run_remote_command`/`_process_inbox_once`(server.py 1384·1403줄)가
   이미 검증한 정확히 같은 패턴(무인 환경 위험작업 자동거부 포함). 활성 중이면 다음 틱까지 대기(재시도) —
   끼어들기 큐에 직접 합치는 최적화는 후속으로 미룬다.
4. **알려진 제약(Proposed 단계에서 의도적으로 남김)**: 서버 재시작 시 `_background_tasks`는 인메모리라
   소실된다(RunLedger 영속화는 후속 카드). 동시에 같은 thread가 활성/백그라운드 완료 둘 다인 경우의
   대기·재시도 백오프 정책은 구현 카드에서 구체화한다.

### 파일럿 도구 (구현 카드에서 사용할 후보)

`read_excel`(순수 파일 I/O, 외부 의존성 0, 안전) — COM/브라우저 등 외부 진행도 신호가 없는 도구로 확대
하는 건 별도 후속.
