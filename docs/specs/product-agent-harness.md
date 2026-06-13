# 스펙 — 제품 내부 에이전트 하네스

> 상태: 설계 확정 대상 · 범위: mes-agent 런타임 아키텍처 · 구현 전
> 목적: 개발환경 하네스와 별개로, mes-agent 제품 자체가 업무를 수행할 때 역할 기반 협업과 루프로 안정 실행되도록 한다.

## 구분

이 문서는 **제품 내부 하네스**를 다룬다.

| 구분 | 목적 | 적용 위치 |
|------|------|----------|
| 개발환경 하네스 | Codex/Claude/Ralph가 mes-agent를 잘 개발하게 함 | repo, worktree, Claude Code, Codex Desktop |
| 제품 내부 하네스 | mes-agent가 사용자의 업무를 안전하고 검증 가능하게 수행하게 함 | `agent/server.py`, workflow, tools, memory, Electron UX |
| 감독 콘솔 UX | 제품 내부 하네스의 상태를 사용자가 볼 수 있게 함 | `electron/renderer/*`, HUD |

관련 문서:

- 개발환경 하네스: `docs/specs/development-harness.md`
- 운영 가이드: `docs/ORCHESTRATION_GUIDE.md`
- 감독 UX: `docs/specs/supervisor-console.md`

## 해결하는 문제

현재 mes-agent는 단일 `generate()` 루프 중심으로 동작한다. 이미 plan mode, workflow, safety gate, compaction, memory, SSE 이벤트가 있지만, 역할이 명시적으로 분리되어 있지는 않다.

이 때문에 다음 문제가 생길 수 있다.

- 계획 수립, 도구 실행, 결과 검증, 위험 판단이 한 루프 안에 섞인다.
- 복잡한 MES/Office/배포 업무에서 “누가 무엇을 판단했는지” 추적하기 어렵다.
- 자동화 실패 후 재시도, 검증, 에스컬레이션 기준이 업무별로 흐려진다.
- 사용자 입장에서는 에이전트가 왜 그 행동을 하는지 감독하기 어렵다.

제품 내부 하네스는 mes-agent 안에 **역할 기반 실행 구조**를 도입해 이 문제를 해결한다.

## 목표

1. 업무 실행을 역할별로 나눈다.
2. 각 역할은 명확한 입력/출력 계약을 가진다.
3. 실행은 `plan → approve → execute → observe → verify → retry/escalate → report` 루프로 진행한다.
4. 모든 중요한 판단은 RunLedger에 남긴다.
5. MES 데이터 변경, 배포, 문서 저장 같은 위험 작업은 Safety Officer 경로를 거친다.
6. 감독 콘솔은 내부 하네스 상태를 실시간으로 보여준다.

## 비목표

- 첫 단계에서 독립 프로세스나 완전한 multi-agent runtime을 만들지 않는다.
- 모든 역할을 별도 LLM 호출로 즉시 분리하지 않는다.
- 기존 `generate()` 루프를 한 번에 갈아엎지 않는다.
- 기존 workflow/tools/safety/memory 자산을 버리지 않는다.

1차 목표는 **역할 계약과 상태 모델을 도입하고, 기존 루프 안에서 점진적으로 역할을 분리**하는 것이다.

## 역할 모델

### Planner

사용자 목표를 실행 가능한 작업 계획으로 바꾼다.

입력:

- 사용자 요청
- 현재 task_type/thread_id
- 관련 memory/context
- 기존 workflow/template

출력:

- 작업 목표
- 단계 목록
- 필요한 근거
- 예상 위험
- 승인 필요 여부

기존 연결:

- plan mode
- `workflow_init`
- task-specific system prompt

### Executor

승인된 단계에 따라 도구를 실행한다.

입력:

- 현재 단계
- 사용할 도구 후보
- Safety Officer 승인 결과

출력:

- tool_start/tool_done 이벤트
- 도구 결과
- 실패/타임아웃 정보
- evidence 후보

기존 연결:

- `run_tool`
- adaptive timeout
- tool safety gate

### Observer

실행 중 화면, 문서, 파일, 도구 결과를 관찰하고 상태를 요약한다.

입력:

- screenshot/vision
- OCR/UI Automation 결과
- Office 문서 읽기 결과
- tool result

출력:

- 현재 상태 요약
- 근거 항목
- 이상 징후

기존 연결:

- `vision.py`
- `screen.py`
- `document.py`
- `ui_automation.py`
- SSE `vision_capture`

### Verifier

작업 결과가 목표와 명세를 만족하는지 확인한다.

입력:

- Planner의 목표/수용 기준
- Executor 결과
- Observer 근거
- 도메인별 검증 규칙

출력:

- pass/fail
- 누락 항목
- 재시도 필요 여부
- 사용자 보고용 검증 요약

도메인 예:

- MES 명세서 검증: 요구사항별 테스트 결과 확인
- Office 문서 작성: 구조/서식/필수 항목 확인
- 배포 자동화: 버전/로그/사후 확인

### Safety Officer

위험 작업을 분류하고 승인/차단 흐름을 강제한다.

입력:

- 도구 이름
- 도구 인자
- 현재 task_type
- 대상 시스템/파일/문서
- 위험도 힌트

출력:

- safe/mutate/destructive
- 승인 요청 문구
- 차단 사유
- 감사추적 이벤트

기존 연결:

- `agent/tools/_safety.py`
- confirm SSE
- plan mode 승인

### Memory/Context Manager

긴 실행의 문맥, 장기기억, 압축 요약, 증적 링크를 관리한다.

입력:

- 대화 이력
- tool 결과
- workflow state
- memory store

출력:

- 현재 목표 요약
- 압축된 context
- 근거 링크
- 장기기억 후보

기존 연결:

- `agent/core/compaction.py`
- `agent/memory.py`
- `obsidian_session.py`

### Reporter

작업 완료 후 사람이 이해할 수 있는 보고서를 만든다.

입력:

- RunLedger
- 검증 결과
- 근거 목록
- 사용자 요청

출력:

- 완료 요약
- 검증 결과
- 실패/주의 사항
- 생성/수정 파일
- 다음 행동 가이드

## 실행 루프

기본 루프:

```text
사용자 요청
  → Planner: 목표와 단계 생성
  → Safety Officer: 위험 사전 분류
  → 사용자 승인(필요 시)
  → Executor: 단계별 도구 실행
  → Observer: 화면/문서/결과 관찰
  → Verifier: 목표 대비 검증
  → 실패 시 retry/escalate
  → Reporter: 결과 보고 및 증적 저장
```

루프 원칙:

- Planner는 실제 변경 작업을 실행하지 않는다.
- Executor는 Safety Officer를 우회하지 않는다.
- Verifier는 Executor의 성공 메시지만 믿지 않고 근거를 확인한다.
- Reporter는 성공/실패/부분완료를 구분한다.
- 모든 단계는 감독 콘솔에 보일 수 있어야 한다.

## 상태 모델

### RunSnapshot

현재 실행 상태의 최신 스냅샷이다. UI 복원과 HUD 표시용이다.

예상 필드:

```json
{
  "request_id": "req-...",
  "task_type": "syncade",
  "thread_id": "20260613-001",
  "goal": "MES 명세서 대비 검증",
  "mode": "auto|plan",
  "phase": "planning|waiting_approval|executing|verifying|reporting|done|error",
  "current_role": "Planner|Executor|Verifier",
  "current_step_id": "step-2",
  "current_tool": "read_word",
  "elapsed_ms": 12000,
  "risk": "safe|mutate|destructive",
  "needs_user": false
}
```

### RunLedger

실행 중 발생한 중요한 사건의 append-only 기록이다.

기록 대상:

- 계획 생성
- 승인 요청/응답
- 도구 실행 시작/종료
- 위험 분류
- 화면/문서 근거
- 검증 결과
- 재시도/실패/에스컬레이션
- 최종 보고

RunLedger는 감사추적과 완료 보고의 원천이 된다.

### Evidence

근거 항목이다.

예상 종류:

- Office 문서 경로와 추출 섹션
- 화면 캡처
- OCR/UIA 결과
- 배포 로그
- MES 화면 상태
- 생성된 검증 리포트
- Obsidian 노트 링크

## 기존 코드와의 매핑

| 기존 자산 | 제품 내부 하네스 역할 |
|----------|----------------------|
| `agent/server.py generate()` | 초기 오케스트레이터/루프 호스트 |
| plan mode | Planner 1차 구현 |
| `workflow_*` tools | Planner/Executor 간 작업 지도 |
| `_safety.py` | Safety Officer 핵심 |
| `run_tool` | Executor 핵심 |
| `compaction.py` | Memory/Context Manager |
| `memory.py` | Memory/Context Manager |
| `events.py` SSE | RunLedger/RunSnapshot 이벤트 원천 |
| `workflow/storage.py` | 단계 정의와 실행 상태 저장 |
| `document.py`, `office_com.py` | Observer/Executor 도구 |
| `vision.py`, `screen.py`, `ui_automation.py` | Observer 도구 |
| `supervisor-console.md` | 하네스 상태를 보여주는 UX |

## 단계별 도입 계획

### Phase 1 — 역할 라벨과 스냅샷

- 기존 `generate()` 루프에 내부 phase/role 라벨을 도입한다.
- SSE 이벤트를 RunSnapshot 형태로 프론트엔드에서 합성한다.
- 감독 콘솔은 현재 role, phase, step, tool, risk를 표시한다.
- 별도 LLM 호출 분리는 하지 않는다.

### Phase 2 — Verifier 분리

- 도구 실행 후 결과 검증 단계를 명시한다.
- workflow 단계 완료는 Executor 결과가 아니라 Verifier 판단으로 확정한다.
- MES/Office/배포 도메인별 검증 규칙을 작은 함수/프롬프트로 분리한다.

### Phase 3 — RunLedger 영속화

- request_id 단위 append-only ledger를 저장한다.
- 스레드 전환/새로고침 후에도 실행 상태와 근거를 복원한다.
- 완료 보고서는 RunLedger를 기반으로 생성한다.

### Phase 4 — Planner/Executor/Verifier 호출 분리

- 역할별 system prompt와 도구 subset을 분리한다.
- 복잡한 작업에서 Planner, Executor, Verifier를 별도 LLM 호출 또는 서브루프로 실행한다.
- 단순 작업은 기존 단일 루프 경로를 유지한다.

### Phase 5 — 도메인 하네스 팩

- MES 검증 하네스
- Office 문서 작성 하네스
- 배포 자동화 하네스

각 팩은 다음을 가진다.

- 기본 workflow template
- 위험 작업 정책
- 검증 기준
- 증적 저장 규칙
- 완료 보고 형식

## 감독 콘솔과의 관계

감독 콘솔은 제품 내부 하네스의 UI다.

| 내부 하네스 정보 | 감독 콘솔 표시 |
|-----------------|----------------|
| goal | 현재 목표 |
| phase | 상단 상태 배지 |
| current_role | 현재 담당 역할 |
| current_step_id | 워크플로우 현재 노드 |
| current_tool | 실행 중 도구와 경과 시간 |
| risk | 위험/승인 카드 |
| evidence | 근거 탭 |
| verifier result | 검증 결과 카드 |
| ledger | 실행 타임라인/로그 |

따라서 `docs/specs/supervisor-console.md`는 이 스펙의 UX 구현 파트로 본다.

## 도메인 적용 예시

### MES 명세서 대비 검증

```text
Planner: 명세서에서 요구사항과 테스트 항목을 추출
Safety Officer: MES 변경 가능 작업을 사전 분류
Executor: 문서/화면/로그를 읽고 필요한 자동화 수행
Observer: MES 화면 상태와 Office 문서 근거 수집
Verifier: 요구사항별 pass/fail 확인
Reporter: 검증 리포트와 증적 목록 생성
```

### Office 문서 작성 자동화

```text
Planner: 문서 구조와 필수 섹션 설계
Executor: Word/Excel/PPT 도구로 작성
Observer: 작성된 문서 내용과 서식 확인
Verifier: 필수 항목/표/검토의견 반영 여부 확인
Reporter: 문서 경로와 변경 요약 제공
```

### 배포 자동화

```text
Planner: 배포 단계와 rollback 확인점 정의
Safety Officer: 배포/삭제/변경 명령 승인 요청
Executor: 배포 명령 또는 UI 자동화 실행
Observer: 로그와 화면 상태 관찰
Verifier: 버전/서비스 상태/결과 로그 확인
Reporter: 배포 결과와 증적 저장
```

## 수용 기준

- [ ] 개발환경 하네스와 제품 내부 하네스가 문서상 명확히 구분된다.
- [ ] mes-agent 내부 역할이 Planner/Executor/Observer/Verifier/Safety/Memory/Reporter로 정의된다.
- [ ] 기존 코드 자산이 각 역할에 매핑된다.
- [ ] 첫 구현은 기존 `generate()`를 갈아엎지 않고 phase/role 라벨부터 시작한다.
- [ ] 감독 콘솔은 제품 내부 하네스의 UI로 연결된다.
- [ ] RunSnapshot과 RunLedger의 목적이 구분된다.
- [ ] MES/Office/배포 도메인별 적용 방향이 제시된다.

