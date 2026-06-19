# P0 세부 개발계획 — 도메인 하네스 팩 (Domain Harness Pack)

> 작성: 2026-06-19 · 상태: 🚧 v1 완료 → v2 계획 · 우선순위: **P0 (최우선)**
> 기준: `docs/DEV_ROADMAP_2026-06.md`, `docs/contracts/harness-poc-v1.md`,
> `docs/backlog/pending/N-harness-mode.md`, `docs/adr/0002-L1-loop-contract.md`

## 1. Context — 왜 지금 이 작업인가

하네스 인프라(Executor→Reviewer PoC, RunLedger, Verifier 라벨, 감독 콘솔, 동적
업무타입)는 거의 완성됐다. 그러나 **인프라가 실제 MES 업무 버티컬에 아직 연결되지
않았다.** v1(`c61ce1e`)에서 `syncade` 한 버티컬만 자기검증 옵트인했고, 그것도
다음 한계 때문에 "켜져 있어도 실효가 약한" 상태다.

이 계획의 목표: **(A) 하네스가 실제로 가치를 내는지 측정 가능하게 만들고, (B) Reviewer가
진짜 검증을 하도록 충실도를 올리고, (C) 차단요인 없는 2번째 버티컬로 확장**한다.
측정 데이터는 P1 #2(N 에픽 — Planner 역할 추가 여부) 의사결정의 직접 입력이 된다.

## 2. 현재 구현 정밀 진단 (코드 확인 결과)

| # | 갭 | 위치 | 영향 |
|---|----|------|------|
| G1 | **Reviewer가 도구 없이 텍스트만으로 판결** — 계약 §2.2는 읽기전용 도구 검증을 명시하나 I2(`tools` 미전송)와 충돌. 실제로는 이력 텍스트만 봄 | `agent/server.py:443 _reviewer_call` | 배포·테스트 결과를 실측정 못 함 → 거짓 pass 위험 |
| G2 | **멀티모달(화면 캡처) 이력 폐기** — `isinstance(content, str)` 필터로 vision capture가 Reviewer 입력에서 제거됨 | `agent/server.py:456-459` | 화면 기반 검증 불가 |
| G3 | **라운드/판결 미계측** — `harness_round`는 SSE only, RunLedger 미기록 | `agent/server.py:510,521` | 실측(라운드 수·재시도 효과·비용) 불가 |
| G4 | **버티컬 1개(syncade)만 옵트인** | `agent/obsidian_session.py:117` | 가치 일반화 미검증 |
| G5 | **A/B 평가 수단 부재** | — | 하네스 ON/OFF 효과 비교 불가 → N 에픽 결정 근거 빈약 |

핵심 자산(재사용): `run_harness`(`agent/harness/orchestrator.py`, 순수·FakeLLM 테스트),
`_harness_generate`/`_should_use_harness`(server.py), `LedgerEntry`+`append_ledger`
(`agent/workflow/model.py:249`·`storage.py:349`), `select_tools`(역할별 도구 제한),
업무타입 헬퍼(`task_type_harness_enabled`/`task_type_verify_prompt`).

## 3. 불변 제약 (계약 준수)

- **I1 도구 짝 보존** · **I4 항상 DONE** · **I5 generate() 무수정** · **I6 기본 off**(`HARNESS_ENABLED`)
  는 `docs/contracts/harness-poc-v1.md` 그대로 유지.
- I2(Reviewer tools 미전송)는 **Phase 2에서 계약 개정** 대상 — 변경 시 ADR + contract bump.
- 폐쇄망: 신규 의존성 0. 측정은 기존 LLM 토큰 추정(`agent/core/tokens.py`) 재사용.
- GxP: 검증 라운드·판결은 감사추적(RunLedger)에 남긴다.

---

## 4. 단계별 개발계획

### Phase 1 — 하네스 실측 계측 (관찰성) · 규모 M · **차단요인 無**

> 목적: "하네스가 가치 있나?"를 데이터로 답할 수 있게 만든다. 모든 후속 결정의 토대.

**1.1 RunLedger에 하네스 라운드 영속화**
- `_harness_generate`의 `reviewing`/`retrying` 전이 직후 `append_ledger`로 기록:
  `LedgerEntry(event="harness_round", phase="verifying", detail={round, verdict_passed, feedback_len, exec_token_est})`.
- 토큰 추정은 `agent/core/tokens.py`의 기존 추정기로 Executor 라운드 입출력 길이를 합산.
- 파일: `agent/server.py`(`_harness_generate`), 재사용 `agent/workflow/storage.py:append_ledger`.

**1.2 하네스 세션 요약 메트릭**
- `GET /threads/{type}/{id}/harness/metrics` — ledger에서 `harness_round` 엔트리를 집계:
  총 라운드, 재시도 횟수, 최종 verdict, 라운드별 토큰 추정, "재시도가 pass로 이어졌나" 플래그.
- 순수 집계 함수 `summarize_harness_runs(entries)` → `agent/harness/metrics.py`(신규, IO 없음, TDD).

**1.3 테스트 (TDD)**
- `tests/unit/test_harness_metrics.py` — `summarize_harness_runs` 입출력(라운드 0/1/2, 폴백 pass, 손상 엔트리 skip).
- `tests/integration/test_harness_ledger.py` — `_harness_generate`(FakeLLM)가 ledger에 라운드를 남기는지.

**산출물**: 회사 PC에서 syncade를 돌리면 `harness/metrics`로 라운드·비용·재시도효과가 즉시 보인다.

---

### Phase 2 — Reviewer 검증 충실도 (G1·G2 해결) · 규모 M · 일부 설계결정 선행

> 목적: Reviewer가 "텍스트 추론"이 아니라 "읽기전용 도구로 실제 확인"하게 한다.

**2.1 설계결정 (ADR 선행)** — `docs/adr/0004-reviewer-verification-fidelity.md`
- 선택지 A: **Reviewer에 읽기전용 도구 서브셋 부여**(계약 §2.2 의도대로). I2를 "Reviewer는
  읽기전용 모듈만"으로 **완화** — `select_tools`를 `REVIEWER.allowed_modules`로 제한하고
  `classify_risk`로 쓰기/파괴 도구를 구조적 차단. tool_calls 짝은 별도 미니 루프로 I1 보존.
- 선택지 B: I2 유지(tools 미전송) + **Executor가 검증 증거를 구조화 산출**(완료 시 자기보고
  형식)을 Reviewer가 평가. 단순하나 Executor 자기보고 신뢰 한계.
- **권장: A** (진짜 검증 가치 > 복잡도). 단 비용↑(M 토큰 예산 연계) → Phase 1 계측으로 사후 검토.

**2.2 멀티모달 이력 전달(G2)**
- `_reviewer_call`이 vision capture 블록을 버리지 않고 최신 N개를 Reviewer 입력에 포함
  (M2 `prune_images` 패턴 재사용, `agent/tools/vision.py`/`agent/core` 참조). 멀티모달 미지원
  LLM이면 자동 텍스트 자리표시자 폴백.

**2.3 테스트**
- `tests/unit/test_reviewer_tools.py` — Reviewer 도구 서브셋이 읽기전용으로 제한되는지(쓰기 도구 차단),
  멀티모달 폴백, 타임아웃 시 passed=True 안전 폴백 유지.

> ⚠ 선행: 2.1 ADR 승인 후 착수. 계약(`harness-poc-v1.md`) I2 문구 개정 + 버전 bump.

---

### Phase 3 — 2번째 버티컬: Unscript 옵트인 (G4) · 규모 S · **차단요인 無**

> 목적: 하네스 가치를 도메인 1개에 의존하지 않게 일반화. unscript는 **테스트 도메인**이라
> 검증 도구(`compare_screenshots`·`capture_screen_ocr`)가 자연스럽고 회사 정보 불필요.

- `agent/obsidian_session.py`의 `unscript` config에 추가:
  - `"harness": True`
  - `"verify_prompt"`: "테스트 실행 결과를 읽기전용 도구로 점검하라: 기대 화면과 실제 화면이
    일치하는지 compare_screenshots/OCR로 확인하고, 통과/실패 케이스를 명확히 구분하라.
    불일치 시 어떤 케이스가 왜 실패했는지 피드백하라."
- 테스트: `tests/unit/test_task_type_harness.py`에 unscript 옵트인 케이스 추가.
- 문서: `CLAUDE.md` 현재상태 표 + 본 스펙 "버티컬" 목록 갱신.

---

### Phase 4 — 실측 평가 방법론 + 실행 (P1 #2 입력) · 규모 S(방법론) / 실행은 회사PC

> 목적: 하네스 ON/OFF를 같은 작업에 비교해 N 에픽(Planner 추가) 결정 근거를 만든다(G5).

**4.1 평가 방법론 문서** — `docs/harness/cards/harness-eval-methodology.md`
- 측정 지표: ① 작업 성공률(사람 판정) ② 평균 라운드/재시도 ③ 토큰·시간 비용 ④ 재시도가
  실패→성공으로 바꾼 비율(자기교정 효과) ⑤ 거짓 pass(폴백) 빈도.
- 절차: 대표 syncade/unscript 작업 N개를 `HARNESS_ENABLED` ON/OFF로 각각 실행 →
  Phase 1 `harness/metrics` + 사람 평가표 기록.
- 종료 게이트(N 에픽 GO/NO-GO): 자기교정 효과 ≥ 임계치 & 비용 증가 허용범위.

**4.2 실행** — 회사 PC(`HARNESS_ENABLED=true`)에서 방법론대로 데이터 수집. (실행만 환경 의존,
계측·방법론은 Phase 1·4.1에서 미리 완성되어 있음.)

---

## 5. 의존성·순서

```
Phase 1 (계측, 무차단) ─┬─→ Phase 4.1 (방법론) ─→ Phase 4.2 (회사PC 실행) ─→ N 에픽 결정(P1 #2)
                        │
Phase 3 (unscript, 무차단) ┘
Phase 2 (Reviewer 충실도) ── ADR 0004 선행 ── (Phase 1 비용 데이터 참고)
```

**권장 착수 순서**: Phase 1 → Phase 3 → (ADR 0004) Phase 2 → Phase 4. 1·3은 즉시
착수 가능(폐쇄망/회사정보 무관). 2는 ADR 승인 후. 4.2만 회사 PC 필요.

## 6. 검증 방법 (전체)

- 단위/통합: `test_harness_metrics`·`test_harness_ledger`·`test_reviewer_tools`·
  `test_task_type_harness`(unscript) + 기존 하네스 회귀(`test_harness_optin`·
  `test_harness_orchestrator`·`test_harness_roles`) 전체 통과. `.\test.ps1`.
- I6 회귀: `HARNESS_ENABLED=false`(기본)에서 `/chat` 경로 무영향 재확인.
- 수동(회사 PC): syncade/unscript 스레드에서 `harness_round` SSE 뱃지 표시 + `harness/metrics`
  응답 + RunLedger에 verifying 엔트리 적재 확인.

## 7. 문서 업데이트 (CLAUDE.md 규칙)

- 새 엔드포인트(`/harness/metrics`)·새 모듈(`agent/harness/metrics.py`) → `CLAUDE.md` 현재상태 표.
- 계약 개정(Phase 2) → `docs/contracts/harness-poc-v1.md` 버전 bump + `docs/adr/0004-*`.
- 버티컬 추가(Phase 3) → `CLAUDE.md` + 본 스펙 §4.3.
- 완료 시 `docs/DEV_ROADMAP_2026-06.md` P0 #1 상태 갱신.
