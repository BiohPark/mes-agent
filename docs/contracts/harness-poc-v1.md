# 하네스 PoC v1 계약 (Executor + Reviewer 2역할)

> 버전: 1.0 · 작성: 2026-06-14  
> 상태: 🟡 PoC — 가치 검증 후 정식 에픽화(백로그 N)  
> 참조: `docs/backlog/pending/N-harness-mode.md`, `docs/adr/0002-L1-loop-contract.md`

---

## 1. 목적

단일 `generate()` 루프가 실수(잘못된 경로·값·미완료)를 저질렀을 때
**자동 자기교정 성공률**을 높인다.
Executor(실행)→ Reviewer(검증)→ (선택적 재실행) 루프로 검증한다.

---

## 2. 역할 정의

### 2.1 Executor

| 항목 | 값 |
|------|-----|
| 이름 | `executor` |
| 도구 서브셋 | 전체 (`select_tools` 기본) |
| system suffix | "당신은 실행자입니다. 주어진 목표를 도구를 사용해 완수하세요." |
| 구현 | 기존 `generate()` 루프 그대로 (system에 suffix만 추가) |
| 출력 | 기존 SSE 이벤트 스트림 전체 |

### 2.2 Reviewer

| 항목 | 값 |
|------|-----|
| 이름 | `reviewer` |
| 도구 서브셋 | 읽기 전용 모듈만 (`ocr`, `screen`, `process`, `document`, `obsidian_rag`) |
| system suffix | JSON 판결 형식 지정 프롬프트 (아래 참조) |
| 구현 | **단발 비스트리밍 LLM 호출** — tool_calls 없음 |
| 출력 | `{"passed": true}` 또는 `{"passed": false, "feedback": "수정 지침"}` |

Reviewer system suffix:
```
당신은 검증자입니다. 읽기 전용 도구(OCR·파일 읽기·시스템 조회)로 결과를 확인하고
정확히 완수됐으면 {"passed": true}를,
문제가 있으면 {"passed": false, "feedback": "구체적인 수정 지침"}을 JSON으로만 반환하세요.
다른 텍스트는 일절 출력하지 마세요.
```

---

## 3. 오케스트레이션 불변식

| 불변식 | 설명 |
|--------|------|
| **I1 도구 짝** | generate() 내부 `tool_calls ↔ tool` 짝 보존 — 기존 L1 계약 그대로 |
| **I2 Reviewer 무실행** | Reviewer LLM 호출에는 tools 배열을 전송하지 않음 (tool_calls 구조적 차단) |
| **I3 라운드 상한** | `MAX_ROUNDS=2` (초기 + 재시도 1회). 무한루프 불가 |
| **I4 항상 DONE** | 하네스 종료 시 DONE 이벤트 보장 (중단·예외 포함) |
| **I5 generate() 무수정** | 하네스는 generate()를 호출하는 래퍼. generate() 루프 코드 변경 없음 |
| **I6 기본 비활성** | `HARNESS_ENABLED=false`(기본). 기존 경로 완전 무영향 |

---

## 4. 판결 파싱 규칙

1. 응답에서 첫 번째 `{...}` JSON 블록을 찾는다.
2. `passed` 필드가 `true`이면 → `ReviewVerdict(passed=True)`.
3. `passed`가 명시적으로 `false`이고 `feedback`이 있으면 → `ReviewVerdict(passed=False, feedback=...)`.
4. 파싱 실패(JSON 없음, 구조 이상) → **안전 폴백 `passed=True`** (Reviewer 오작동으로 Executor 재시작 방지).

---

## 5. SSE 이벤트

| 이벤트 타입 | 페이로드 | 시점 |
|-------------|---------|------|
| 기존 이벤트 전부 | 변경 없음 | Executor 실행 중 |
| `harness_round` | `{round: N, phase: "reviewing"}` | Reviewer 호출 직전 |
| `harness_round` | `{round: N, phase: "retrying", feedback: "..."}` | Executor 재시작 직전 |

---

## 6. 활성화 조건 (도메인 하네스 팩 v1, 2026-06-19)

`server._should_use_harness(harness_mode, task_type)`가 결정:

```
HARNESS_ENABLED(전역) AND task_type 존재
  AND ( /chat 요청의 harness_mode 플래그 OR 업무타입 설정의 harness 옵트인 )
```

- **업무타입 단위 옵트인**: 업무 config(`_DEFAULT_TASK_CONFIGS` / Vault 오버레이)에
  `harness: true`면 명시 플래그 없이도 하네스 경로. 첫 버티컬 = `syncade`(배포 검증).
- **도메인 검증 프롬프트**: config의 `verify_prompt`가 있으면 Reviewer suffix에 주입
  (`_reviewer_call(history, verify_prompt)`). 없으면 기존 기본 검증 프롬프트.
- **Reviewer 멀티모달(Phase 2 G2, 2026-06-19)**: `_reviewer_call`이 화면 캡처(image_url)를
  `prune_images`로 최신 `HARNESS_REVIEWER_IMAGES`개(기본 2)만 전달. `0`이면 전부 텍스트
  자리표시자로 강등 — 멀티모달 미지원 LLM 안전 폴백. I2(tools 미전송) 불변.
- **실측 계측(Phase 1 G3, 2026-06-19)**: `_harness_generate`가 매 Reviewer 판결을
  RunLedger(`harness_round`, detail=JSON)에 영속화. 측정을 위해 **마지막 라운드도 검증을
  기록**(재시도는 하지 않음). `agent/harness/metrics.summarize_harness_runs`가 집계,
  `GET /threads/{type}/{id}/harness/metrics` 노출. G1(Reviewer 도구부여) 결정은 ADR-0004.

### 비활성화 조건(하네스 건너뜀)

- `HARNESS_ENABLED` 환경변수가 `"true"`가 아닌 경우 → 옵트인·플래그 무관하게 항상 우회(I6)
- `harness_mode=false`(기본)이고 업무타입도 `harness` 옵트인이 아닌 경우
- `thread_id`/`task_type`이 비어 있는 경우
- Reviewer LLM 호출 타임아웃 → passed=True 폴백(안전)

---

## 7. 검증 기준(PoC 통과)

- [ ] `test_harness_roles.py` 전체 통과
- [ ] `test_harness_orchestrator.py` 전체 통과 (FakeLLM, 네트워크 없음)
- [ ] `test_task_type_harness.py` 전체 통과 (업무타입 옵트인 스키마·헬퍼)
- [ ] `test_harness_optin.py` 전체 통과 (`_should_use_harness` 라우팅)
- [ ] `test_harness_metrics.py` 전체 통과 (실측 집계, Phase 1)
- [ ] `test_harness_ledger.py` 전체 통과 (라운드 RunLedger 영속화 + /metrics, Phase 1)
- [ ] `test_reviewer_call.py` 전체 통과 (멀티모달 전달·I2·폴백, Phase 2 G2)
- [ ] 기존 단위 테스트 회귀 없음
- [ ] `HARNESS_ENABLED=false`(기본) 시 `/chat` 경로 무영향 확인
