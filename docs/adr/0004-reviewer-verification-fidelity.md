# ADR-0004 — 하네스 Reviewer 검증 충실도

| 항목 | 내용 |
|------|------|
| **상태** | Accepted (G2 멀티모달) / Proposed (G1 도구부여 — Phase 1 실측 후 결정) — 2026-06-19 |
| **결정자** | Bioh Park |
| **대상 파일** | `agent/server.py` `_reviewer_call`, `agent/harness/roles.py`, `docs/contracts/harness-poc-v1.md` |
| **관련 ADR** | ADR-0002 (L1 루프 계약 — I1 짝보존·I4 DONE 계승) |
| **관련 문서** | `docs/specs/domain-harness-pack.md`(Phase 2), `docs/backlog/pending/N-harness-mode.md` |

## 컨텍스트

도메인 하네스 팩 v1에서 Executor→Reviewer 자기검증을 업무타입 단위로 옵트인했다(syncade·unscript).
그러나 현재 Reviewer(`_reviewer_call`)는 다음 두 한계로 **실효 검증을 못 한다**:

- **G1**: Reviewer는 도구 없이(I2 — tools 미전송) 대화 이력 텍스트만 보고 판결한다. 계약 §2.2가 명시한
  "읽기 전용 도구로 결과 확인"이 실제로는 일어나지 않아, 배포 서비스 기동·테스트 결과처럼
  **외부 상태를 직접 확인해야 하는 검증**을 수행할 수 없다 → 거짓 pass 위험.
- **G2**: `_reviewer_call`이 `isinstance(content, str)`로 필터링해 **화면 캡처(멀티모달 image_url)를 폐기**한다.
  화면 기반 검증(UI 일치·오류 팝업 확인)이 원천 불가.

## 결정

### G2 — 멀티모달 이력 전달 (Accepted, 구현됨)

`_reviewer_call`이 user/assistant 메시지의 list content(image_url 블록)를 버리지 않고 Reviewer에 전달한다.
비용·안전을 위해 `prune_images`(기존 G1 compaction 자산 재사용)로 **최신 `HARNESS_REVIEWER_IMAGES`개(기본 2)** 만
남기고 과거 이미지는 텍스트 자리표시자로 강등한다. `HARNESS_REVIEWER_IMAGES=0`이면 모든 이미지를 강등 →
**멀티모달 미지원 LLM의 안전 폴백**(텍스트 전용 Reviewer). I2(tools 미전송) 불변, I1 무영향(이미지는 user 메시지).

### G1 — Reviewer 읽기전용 도구 부여 (Proposed, Phase 1 실측 후)

두 선택지:

- **선택지 A (권장)**: Reviewer에 `REVIEWER.allowed_modules`(`ocr·screen·process·document·obsidian_rag`)
  서브셋만 부여하고 `classify_risk`로 쓰기/파괴 도구를 구조적 차단. tool_calls↔tool 짝은 **별도의 짧은
  읽기전용 미니 루프**로 처리해 I1 보존. 계약 §5 **I2를 "Reviewer는 읽기전용 모듈만 사용"으로 완화**.
  진짜 검증이 가능해지나 라운드당 LLM 호출·토큰 비용 증가.
- **선택지 B**: I2 유지(tools 미전송) + Executor가 완료 시 **구조화된 검증 증거**를 자기보고하고 Reviewer가
  그 텍스트를 평가. 단순하나 Executor 자기보고에 의존 → 충실도 한계.

**미결 — 결정 게이트**: A의 비용이 정당한지는 Phase 1 계측(`/harness/metrics`: 자기교정율·라운드·토큰)을
syncade/unscript 실사용으로 확보한 뒤 판단한다. 비용 대비 자기교정 효과가 임계 이상이면 A 구현,
아니면 B 또는 현행 유지. **I2 계약 변경은 본 ADR이 Accepted로 승격될 때 contract 버전 bump와 함께 반영한다.**

## 불변 제약

- I1 도구 짝 보존 · I4 항상 DONE · I5 generate() 무수정 · I6 기본 off(`HARNESS_ENABLED`)는 유지.
- 신규 의존성 0(폐쇄망). 멀티모달 미지원 환경은 `HARNESS_REVIEWER_IMAGES=0`으로 텍스트 폴백.

## 결과

- G2: 화면 캡처 기반 검증이 가능해짐(syncade 배포 화면·unscript UI 검증). 비용은 prune로 상한.
- G1: 설계·게이트 확정. 실측 데이터가 모이면 본 ADR을 갱신해 A/B/현행 중 택일.
