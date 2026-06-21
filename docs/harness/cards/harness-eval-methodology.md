# 작업 카드 — 하네스 ON/OFF 실측 평가 방법론

> 상태: 📋 방법론 확정 / 실행 대기(회사 PC) · 우선순위: P0(Phase 4) · 2026-06-19
> 관련: `docs/specs/domain-harness-pack.md`(Phase 4), `agent/harness/metrics.py`, ADR-0004

## 목적

Executor→Reviewer 하네스가 **실제로 가치를 내는지**(자기교정 효과 ≥ 비용 증가)를 데이터로
판정한다. 결과는 **P1 #2(백로그 N — Planner 역할 추가) GO/NO-GO** 의 직접 입력이다.

## 측정 지표

| 지표 | 출처 | 의미 |
|------|------|------|
| 작업 성공률 | 사람 판정(평가표) | 최종 결과가 의도대로인가 |
| 평균 라운드 / 재시도 수 | `/harness/metrics` `total_reviews`·`retries` | 검증 루프가 몇 번 도는가 |
| 자기교정율 | `/harness/metrics` `self_corrected` 비율 | 실패→재시도→성공으로 바뀐 비율(핵심) |
| 토큰 비용 | `/harness/metrics` `max_history_tokens` + Reviewer 호출 추정 | 하네스의 추가 비용 |
| 거짓 pass 빈도 | 사람 판정 vs `final_passed` | Reviewer가 실패를 통과로 오판한 횟수 |

## 절차

1. 대표 작업 세트 선정: syncade 배포 N건 + unscript 테스트 N건(권장 각 5~10건, 재현 가능한 것).
2. 각 작업을 **두 조건**으로 실행:
   - **OFF**: `HARNESS_ENABLED=false` (기존 단일 generate 경로)
   - **ON**: `HARNESS_ENABLED=true` (+ 업무타입 옵트인) · 측정 정확도를 위해 `HARNESS_MAX_ROUNDS=3`
     권장(마지막 라운드도 검증 기록됨 — 자기교정 관측 가능)
3. 각 실행 후 `GET /threads/{type}/{id}/harness/metrics`로 메트릭 수집 + 사람 평가표 1행 기록.
4. 조건별 집계해 위 지표 비교.

## GO / NO-GO 게이트 (N 에픽)

- **GO(Planner 역할 추가 검토)**: 자기교정율이 의미 있게 양수(예: ON에서 실패 작업의 ≥30%가 자기교정)
  **이고** 토큰 비용 증가가 허용 범위(예: 평균 +50% 이내).
- **NO-GO / 보류**: 자기교정 효과가 미미하거나 거짓 pass가 잦으면 → ADR-0004 G1(Reviewer 도구부여)
  먼저 적용 후 재측정, 또는 하네스 옵트인 범위 축소.

## 선행 조건

- Phase 1 계측 구현 완료(✅ `agent/harness/metrics.py` + `/harness/metrics` + ledger 영속화).
- 실행은 회사 PC(syncade/unscript 실대상 접근) 필요 → 본 카드는 방법론까지 확정, 실행은 대기.
