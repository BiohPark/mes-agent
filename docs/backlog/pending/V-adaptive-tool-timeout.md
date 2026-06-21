# 백로그 V — 적응형 도구 타임아웃 (무한 행 방지 + 작업 가시성) ⏱️

> 상태: ✅ 1단계 구현 완료 · 2단계 liveness spike·인루프 판단·디스패치 캡 버그수정(effective_cap) 완료 · 자동 백그라운드 디태치 구현 완료(ADR-0003)
> 동기: Excel 작업이 **3분+ 무한 펜딩**, 사용자는 무슨 일인지 알 수 없었다(`docs/errors/화면 캡처 2026-06-12 054918.png`).
> 거버넌스: 클린룸. 출처 = 본인 코드 + 일반 에이전트 지식 + openclaw(MIT)/LangGraph + **claw-code(MIT, 사용자 클리어 — 패턴만, 코드 복붙 금지)**.

## 문제 (재분석)

타임아웃 처리가 도구 계층 전반에서 **제각각·불일치**다:
- `process.py` `run_command`/`start_process` → subprocess `timeout=30` 자체 캡.
- `office_com.py` `_on_com_thread` → **타임아웃 없음 = 무한 행**(Excel `Workbooks.Open`이 보이지 않는 모달에서 무한 대기).
- `server.py generate()` 디스패치(`run_in_executor(run_tool)`) → **캡 없음** → 자체 캡 없는 도구 하나가 SSE 전체를 영구 정지.

핵심 결함: (1) 일부 도구 무한 행, (2) 디스패치 경계 통일 안전망 부재, (3) 진행/멈춤 가시성 0.

## 1단계 — 긴급수정 ✅ (구현 완료)

- **순수 모듈 `agent/core/timeouts.py`**: `tool_baseline`(도구별 작은 예상시간), `escalation_schedule`(누적 한계), `classify_timeout`(slow/stuck 구조화), `timeout_error_text`.
- **디스패치 통일 타임아웃 `server.py _run_tool_watched`**: 같은 in-flight 작업을 단계적 `asyncio.wait_for`로 더 기다리고, 가시 임계 초과 시 `TOOL_WAIT` SSE 내레이션, 캡 도달 시 구조화 오류(기존 error-step 경로 재사용).
- **office_com 자가복구**: `OFFICE_COM_TIMEOUT` 워치독 + **PID 스코프 킬**(사용자가 직접 연 Office 보호) + executor 재생성 + Open 대화상자 억제(`Notify=False` 등).
- **가시성(chat.js/css)**: 경과 타이머, "더 기다리는 중" 내레이션, 상태바 현재 도구, 중단 버튼 강조.

## 2단계 — 전체 적응형 (미착수, 본 에픽 핵심)

1. **진행도(liveness) 탐지 — 슬로우 vs 스턱 구분**
   - 신호: 자식 프로세스 CPU>0 / stdout 바이트 증가 / 창 응답성(Win UIA `IsHungAppWindow`) / 네트워크 활동.
   - 진행 신호 있으면 연장(`slow`), 2회 연속 정지면 조기 중단(`stuck`) — 캡까지 무의미하게 안 기다림.
2. **에이전트 인루프 판단**
   - 캡/스턱 시 구조화 결과(`failureClass`·`provenance`·추정원인·대안)를 **LLM에 tool 결과로 환류** →
     모델이 재시도(더 큰 timeout)/대안 경로(Excel COM→openpyxl)/사용자 질의를 **스스로 선택**.
   - "이번엔 시간 늘려 해본다 / 이렇게 해본다"를 모델이 텍스트로 사용자에게 설명(L1 루프 내레이션과 조화).
3. **자동 백그라운드 디태치**(claw-code 패턴 참고) — **구현 완료(ADR-0003)**
   - 정당하게 긴 작업(대용량 빌드·변환)은 SSE를 막지 않고 **백그라운드 작업으로 전환** → 진행 폴링/완료 알림.
   - `start_process`/`run_command`의 GUI·장기 프로세스를 "성공적으로 시작됨(미종료)"으로 분류해 행으로 오인하지 않음.
   - 설계: 도구가 즉시 "시작됨" placeholder로 I1을 충족(tool_calls 짝 보존, 절대 안 깨짐) → 실제 결과는
     백로그 Q/O가 이미 쓰는 인메모리 레지스트리 + 헤드리스 `generate()` 재호출 패턴으로 나중에 별도 턴
     전달. "반복 내 지연 폴링" 방식은 고아 tool_calls 위험으로 기각. 상세: `docs/adr/0003-adaptive-tool-timeout.md`
     "2단계 세부설계" 절.
4. **baseline 적응 학습**: 관측 p50/p90을 누적해 도구별 baseline을 점진 보정(콜드스타트=정적값).
5. **취소/정리**: 중단 버튼이 in-flight 작업을 실제로 끊도록(프로세스 트리 kill·COM PID kill 연계).

### 2단계 Spike — `run_command` liveness 분류 ✅

- `agent/core/timeouts.py`에 `LivenessObservation`과 `classify_liveness()`를 추가해 stdout/stderr 증가, 프로세스 생존 여부, elapsed, 무진행 카운트를 구조화한다.
- `agent/tools/process.py`의 `run_command` timeout 경로가 `TimeoutExpired`의 partial stdout/stderr를 관측해 `slow`/`stuck`을 반환한다.
- 기존 `timeout_error_text()` 접두와 `TOOL_WAIT` 이벤트 타입은 유지했다.
- 범위 밖으로 남긴 것: Office COM/프로세스 트리 kill, 백그라운드 작업 레지스트리, 새 SSE 이벤트, LLM 인루프 판단.

### 2단계 보완 — 디스패치 캡 버그수정 `effective_cap` ✅

- `_run_tool_watched`의 디스패치 캡이 도구가 요청한 `timeout` 인자를 무시하고 항상 고정 90s를 쓰던
  버그를 발견·수정했다. `agent/core/timeouts.py`에 `effective_cap(name, arguments)` 추가 —
  `TOOL_TIMEOUT_HARD_CEILING`(기본 300s)으로 무한 행 방지 원칙은 유지하면서 도구 자체 timeout을 존중.
- LLM이 시스템 추천 회복 옵션("timeout 늘려 재시도")을 따라도 디스패치 캡에 먼저 끊기던 문제 해결.
- 테스트: `tests/unit/test_timeouts.py`(6건 추가), `tests/unit/test_run_tool_watched.py`(신규).

## 핵심 파일
- 구현됨: `agent/core/timeouts.py`(`should_background` 등), `agent/server.py`(`_run_tool_watched`, `_background_watchdog`), `agent/tools/office_com.py`, `agent/core/events.py`(`TOOL_WAIT`), `electron/renderer/chat.js`·`style.css`.
- 2단계 일부 완료: `agent/core/timeouts.py`(run_command용 liveness·분류 확장 + `effective_cap` 디스패치 캡 버그수정), `agent/tools/process.py`(partial stdout/stderr 기반 timeout 구조화), `agent/server.py`(`_run_tool_watched`가 `effective_cap` 사용).
- 2단계 후속 예정: `agent/server.py`(인루프 환류), Office/COM 외부 관측.

## 확인 필요 (2단계)
1. 진행도 신호의 OS별 신뢰성(특히 COM STA 스레드가 막혔을 때 외부 관측만 가능).
2. 자동 백그라운드의 결과 회수 UX(폴링 vs 알림) + 비용.
3. 인루프 환류가 토큰/스텝 예산(백로그 M)에 주는 영향.

## 규모
2단계 = L(에픽). 1단계(긴급)는 본 라운드 완료.
