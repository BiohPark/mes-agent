# ADR-0003 — 적응형 도구 타임아웃 (무한 행 방지 + 작업 가시성)

| 항목 | 내용 |
|------|------|
| **상태** | Accepted (1단계) / Proposed (2단계) — 2026-06-12 |
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
