# 리팩터링 플레이북 — MES Agent

> 버전: v1.0 | 작성일: 2026-06-07 | 근거: CODEBASE_AUDIT.md + ADR-0001
> 브리프 §8 우선순위 원칙: 가장 비싼 결정 먼저 설계, 그다음 신뢰성, 그다음 갭 분석

---

## Phase 0 — 기반 정비 (완료 ✅)

> 이미 완료됨. 플레이북의 전제 조건.

- TDD 인프라 (98개 테스트, pytest, conftest 격리)
- 워크플로우 편집 6종 툴
- 에이전트 상태 바 + 중단 버튼
- 기본 관측 가능성 (SSE 9종 이벤트)

---

## Phase 1 — 워크플로우 모델 진화 (가장 비싸고 중요)

> **근거:** ADR-0001. 되돌리기 어려운 결정이므로 첫 번째. 범위는 모델 계층만, UI 변경 없음.

### 목표 (성과)
- 조건 분기를 데이터로 표현할 수 있는 그래프 모델 존재
- 정의(불변)와 실행 상태(가변)가 분리됨
- 기존 선형 워크플로우가 자동 마이그레이션으로 깨지지 않음

### 범위
**포함:**
- `agent/workflow/model.py` — `WorkflowDefinition`, `WorkflowNode`, `WorkflowConnection`, `WorkflowRunState` 도입. 기존 `Workflow`·`WorkflowStep` 병행 유지.
- `agent/workflow/storage.py` — 포맷 감지(steps 키 존재 → 구 형식), 자동 마이그레이션 로직 추가
- `agent/tools/workflow.py` — 6종 툴 backwards-compatible 확장 (steps 파라미터 계속 받되 내부에서 nodes+connections로 변환)
- `agent/server.py` — `generate()` 루프에서 `WorkflowRunState`를 메모리 dict로 관리 (정의 파일 분리)
- `tests/unit/test_workflow_model.py`, `test_workflow_storage.py` — 신규 모델 커버리지 추가

**제외:**
- UI 변경 (우측 패널은 Phase 3에서)
- connections 편집 툴 (Phase 3에서)
- RunState 영속화 (Phase 2 이후)

### 영향받는 파일
```
agent/workflow/model.py      ← 데이터클래스 추가
agent/workflow/storage.py    ← 마이그레이션·감지 로직
agent/tools/workflow.py      ← 툴 인터페이스 확장
agent/server.py              ← RunState 메모리 관리
tests/unit/test_workflow_model.py
tests/unit/test_workflow_storage.py
```

### 수용 기준 (테스트로 검증)
- [ ] `WorkflowDefinition.from_dict(old_linear_dict)` → 자동 마이그레이션 성공
- [ ] 마이그레이션 후 `to_dict()` → 구 형식 클라이언트가 여전히 읽을 수 있음 (하위 호환)
- [ ] 조건 분기 2갈래(from_output=1,2)를 가진 WorkflowDefinition 직렬화/역직렬화 왕복 성공
- [ ] `workflow_set_step` 호출 시 WorkflowDefinition 파일이 변경되지 않고 RunState만 변경됨
- [ ] 기존 `tests/` 98개 전부 계속 통과

### 회사 PC 수동 검증 포인트
- 앱 실행 후 기존 general 스레드 열기 → 워크플로우 패널에 단계가 정상 표시되는지
- 에이전트에게 작업 지시 → workflow_set_step이 호출되고 패널 상태 갱신되는지

### 새 의존성
없음 (표준 라이브러리·dataclasses만 사용)

### 예상 PR 분할
- PR 1-A: 새 데이터클래스 + 마이그레이션 유틸 (코드만, 기존 경로 유지)
- PR 1-B: storage 마이그레이션 연결 + 툴 확장
- PR 1-C: server.py RunState 분리

---

## Phase 2 — 신뢰성·관측 가능성 개선

> **근거:** P3. 범위 명확하고 아키텍처 변경 없어 빠른 가치.

### 목표 (성과)
- 툴 실패 시 워크플로우 단계 error 상태 자동 표시
- 재시도 가능한 단계 실행
- 실패가 사용자에게 명확히 보임

### 범위
**포함:**
- `agent/server.py` — 툴 실행 후 결과가 error 패턴이면 해당 단계 status를 자동으로 "error"로 갱신. 재시도 로직(retry 횟수 읽기).
- `agent/workflow/model.py` (Phase 1 이후) — `WorkflowNode.retry`, `on_error` 필드 활성화
- `electron/renderer/workflow.js` — error 상태 단계에 재시도 버튼 표시
- `tests/integration/test_server_chat.py` — 툴 실패 시 WORKFLOW_UPDATE에 error 상태 포함 검증

**제외:**
- 재시도 정책 UI 편집 (Phase 3로)
- 이메일/알림 발송

### 영향받는 파일
```
agent/server.py                        ← error 자동 감지·갱신 로직
electron/renderer/workflow.js          ← 재시도 버튼 UI
tests/integration/test_server_chat.py  ← 실패 시나리오 테스트
```

### 수용 기준
- [ ] mock 툴이 예외를 던졌을 때 SSE WORKFLOW_UPDATE에 해당 단계 status="error" 포함
- [ ] UI에서 error 단계에 "재시도" 버튼 표시 → 클릭 시 해당 단계부터 에이전트 재시작
- [ ] 재시도 횟수 초과 시 단계가 "error"로 고정되고 루프 종료

### 새 의존성
없음

### 예상 PR 분할
- PR 2-A: server.py error 자동 감지
- PR 2-B: 재시도 로직 + UI 버튼

---

## Phase 3 — 워크플로우 편집 UX + 분기 표현

> **근거:** Phase 1 모델이 확정된 뒤에만 착수. UI와 툴을 함께 확장.

### 목표 (성과)
- 사용자가 편집 모드에서 단계를 분기로 연결할 수 있음
- 에이전트가 조건 분기 결정을 SSE로 알림

### 범위
**포함:**
- `electron/renderer/workflow.js` — 분기 표시(선 연결), 분기 노드 편집
- `electron/renderer/index.html` — 분기 편집 UI 요소
- `agent/tools/workflow.py` — `workflow_add_connection`, `workflow_remove_connection` 툴 추가
- `tests/smoke/test_tool_schemas.py` — EXPECTED_TOOL_COUNT 업데이트

**제외:**
- Obsidian Canvas 통합 (별도 스파이크)
- 비주얼 그래프 편집기 전체 구현 (단계적)

### 새 의존성
검토 필요 (그래프 렌더링 라이브러리 — 폐쇄망 비용 고려. 우선 SVG 직접 구현 시도).

### 예상 PR 분할
- PR 3-A: 툴 2종(add_connection, remove_connection) + 테스트
- PR 3-B: 분기 시각화 (SVG 선 연결)
- PR 3-C: 분기 편집 인터랙션

---

## Phase 4 — Obsidian 단일 소스화 (P1-b)

> **근거:** Phase 1·3 완료 후. 가장 복잡, 별도 스파이크 필요.

### 목표 (성과)
- 사람이 Obsidian에서 워크플로우 정의를 편집하면 에이전트가 다음 실행 시 반영
- 에이전트가 상태를 갱신해도 정의 파일을 덮어쓰지 않음 (C3 보장)

### 핵심 설계 질문 (이 Phase 착수 전 스파이크로 결정)
- 파일 변경 감지: polling vs inotify(Linux) vs `watchdog` 라이브러리 (폐쇄망 비용)
- 직렬화: 현재 JSON vs YAML frontmatter + 마크다운 body (사람 편집성 ↑)
- RunState 영속화: 메모리(휘발) → 별도 JSON 파일로 이전

### 새 의존성 후보
- `watchdog` — 파일 시스템 이벤트 감시 (폐쇄망 whl 이전 필요)

### 예상 PR 분할
- PR 4-A: RunState 영속화
- PR 4-B: 파일 변경 감지·재로드
- PR 4-C: 직렬화 포맷 이전 (JSON → YAML frontmatter, 마이그레이션 포함)

---

## Phase 5 — 자생적 구현 갭 분석 선별 개선 (P2)

> **근거:** 브리프 §8 — "분석 결과 중 비용 대비 효과 높은 항목만."

### 감사 결과 식별된 갭

| 항목 | 현재 | 상용 기준 | 비용/효과 |
|------|------|----------|-----------|
| 접근성(a11y) 타겟 | 좌표+이미지+OCR | pywinauto/UIA | 높음/낮음 — 스킵 |
| auto-wait | 없음(수동 sleep) | Playwright식 대기 | 중간/높음 — 검토 |
| 변화 감지 polling | 없음 | 능동 watch | 중간/중간 — Phase 4와 묶음 |
| 멀티모달 비전 | 없음 | LLM vision | 높음/높음 — 별도 스파이크 |

### Phase 5 범위
- `tools/screen.py` — wait_for_image·wait_for_text에 polling 간격·timeout 파라미터 명시화
- `tools/desktop.py` — mouse_click 후 안정화 대기 옵션 추가
- 멀티모달 비전은 LLM 비전 API 지원 확인 후 별도 Phase

---

## 비목표 재확인 (브리프 §3에서)

이 플레이북 어디에도 포함되지 않는 것:
- 87종 툴 일괄 재작성
- Obsidian REST → MCP 교체 (이득 증명 전)
- Electron → Tauri 교체
- Syncade·Knox 실연동
- 빅뱅 릴리스 (모든 Phase는 독립 PR)

---

## 실행 체크리스트 (Phase 착수 전 매번)

- [ ] 해당 Phase의 모든 수용 기준이 테스트 코드로 먼저 작성됨 (TDD)
- [ ] 기존 98개 테스트가 통과함
- [ ] 새 의존성의 오프라인 설치 경로 확인됨
- [ ] 브리프 §7 원칙 7개 재검토
- [ ] 되돌리기 어려운 결정은 ADR로 기록됨
