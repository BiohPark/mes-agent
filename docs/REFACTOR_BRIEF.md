# MES Agent — 리팩터링 브리프 (아키텍처 원칙·차용 패턴·불변식)

> 작성: 2026-06-13 · 성격: 안정적 기준 문서(자주 안 바뀜)
> **세션 시작 시 읽기**: `CLAUDE.md`(구현 상태) + `docs/TRANSFORMATION_PLAN.md`(활성 로드맵) + 본 문서.
> 이 문서는 "**어떤 외부 패턴을 왜 차용했고, 어떤 불변식을 지키는가**"를 기록한다. 로드맵·작업 목록은 여기 두지 않는다.

---

## 0. 문서 위치 (역할 분담)

| 문서 | 역할 | 변동성 |
|------|------|--------|
| `CLAUDE.md` | 구현 상태 SSOT(현재 상태 표·툴 수·자동 갱신 규칙) | 매 기능마다 갱신 |
| `docs/TRANSFORMATION_PLAN.md` | 활성 로드맵(트랙 1~3, 미체크 항목·결정 대기) | 대화하며 발전 |
| **`docs/REFACTOR_BRIEF.md` (본 문서)** | 아키텍처 원칙·차용 패턴·불변식 | 드물게 |
| `docs/adr/*` | 개별 결정 기록(ADR-0001~0003) | 결정마다 추가 |

---

## 1. 불변 제약 (모든 작업 공통 — TRANSFORMATION_PLAN 계승)

- **폐쇄망**: 런타임 외부 네트워크 호출 불가. 신규 의존성 = conda-pack 번들 갱신 비용 → 근거와 함께 제안만.
- **개발 브리지**: 홈/Termux 개발 → GitHub push → 회사 PC `git pull`. 회사 PC엔 개발도구 미설치.
- **LLM**: 사내 OpenAI 호환 엔드포인트(`openai` + `base_url`). 멀티모달 지원 여부 ☐ 미확인.
- **Obsidian**: `urllib`/REST(localhost:27123) 직접 호출. 직접 파일 glob/grep 금지(툴 경유).
- **GMP/GxP**: MES 데이터 변경 자동화 경로엔 감사추적(누가/언제/무엇을) 필수.
- **출처 위생**: §6 참조.

---

## 2. 차용 확정 패턴 (개념만 차용 — 코드 복사 금지)

상태는 **현재 코드 기준 사실만** 기재한다(과대표기 금지).

| 패턴 | 출처 | mes-agent 적용 | 상태 |
|------|------|----------------|------|
| 노드/커넥션 분리(데이터로서의 분기) | n8n | `WorkflowDefinition`(nodes+connections) — `agent/workflow/model.py` | ✅ ADR-0001 |
| 정의(불변)/실행상태(가변) 분리 | Temporal·LangGraph | `WorkflowDefinition` ↔ `WorkflowRunState`(`node_states`) | ✅ ADR-0001 |
| 액티비티 재시도·에러 정책 | UiPath | `WorkflowStep.max_retry` + 툴 실패 시 단계 error 자동 전환 | ✅ 부분 (`on_error` 정책 확장 여지) |
| auto-wait(명시적 대기) | Playwright | `screen.wait_for_image/text`(interval 노출) + 브라우저 자동 대기 | ✅ |
| 적응형 타임아웃·구조화 실패 결과 | claw-code(MIT, **패턴만**)·일반 | `agent/core/timeouts.py` + `server.py _run_tool_watched`(escalation·`classify_timeout`·`TOOL_WAIT`) | ✅ 1단계 (백로그 V·ADR-0003) |
| 컨텍스트 압축(condenser) | OpenHands·일반 | `agent/core/compaction.py`(G1) | ✅ |
| 이벤트 스트림(관측 가능성) | OpenHands | SSE 이벤트 상수 `agent/core/events.py` | ✅ 부분 |
| plan→승인→실행 | 일반(LangGraph·CC) | `agent_mode='plan'`(G4) | ✅ |

> 새 패턴을 차용하면 이 표 + 해당 ADR에 출처를 함께 기록한다(§6).

---

## 3. L1 루프 불변식 (ADR-0002 — 테스트 1급, `agent/server.py generate()`)

| 불변식 | 내용 |
|--------|------|
| **I1** | `tool_calls` 있는 assistant 메시지 뒤엔 반드시 짝 맞는 `tool` 결과 메시지(압축·타임아웃·거부 경로 모두 보존) |
| **I2** | `safe`가 아닌 모든 tool 실행은 디스패치 경로에서 승인 게이트를 거친다(모델 협조 비의존) |
| **I3** | `_MAX_STEPS`·`MAX_NUDGES`·`MAX_COMPACT` 상한 준수(무한 루프·비용 폭주 불가) |
| **I4** | 어떤 종료 경로(예외·타임아웃 포함)든 SSE는 마지막에 `DONE`으로 닫힌다 |
| **I5** | compaction은 system 및 최근 N턴을 보존한다 |

루프를 만질 땐 `/loop-audit` 스킬 + `docs/adr/0002-L1-loop-contract.md` 기준으로 검증.

---

## 4. 4대 갭 (G1~G4 — 해소 완료, ADR-0002)

- **G1** 컨텍스트 compaction · **G2** continuation nudge · **G3** 중앙 집중 안전 게이트 · **G4** plan 모드 — 전부 ✅(2026-06-10).
- 후속: 적응형 타임아웃(백로그 V·ADR-0003) 1단계 ✅, 컨텍스트 초과 자동처리(백로그 M) ✅.

---

## 5. 현재 우선순위 (상세는 `docs/TRANSFORMATION_PLAN.md`)

- **트랙 1 — 개발 하네스**: `.claude/`(설정·훅·`code-reviewer` 서브에이전트·`tdd`/`add-tool`/`loop-audit` 스킬) 도입 ✅. Claude Code 전역 `ecc@ecc` plugin + repo-local `.claude/rules/ecc/{common,python,typescript,web}`를 표준으로 사용한다. Ralph 반복은 설치된 `ralph-loop` 플러그인(세션 내) 우선, 헤드리스 `scripts/ralph/`는 무인 자동 필요 시.
- **트랙 2 — 상용급 역설계**: 기능을 `docs/specs/<기능>.md`로 명세(문제/매핑/수용 기준) → 작은 단위로 분해 → TDD 루프가 구현.
- **트랙 3 — 단기 과제**: Tesseract 제거(접근성 트리·멀티모달 전환), Knox 메신저 챗봇(설계만).

---

## 6. 출처 위생 (필수)

- 오픈소스는 **개념만 차용, 코드 복사 금지**. 차용 시 본 문서 §2 + 해당 ADR에 출처를 명시한다.
- **claw-code**: MIT 라이선스 사용자 확인 완료 — **패턴 참고 허용, 코드 복붙 금지**(ADR-0003).
- 그 외 출처는 라이선스·클린룸 적합성 확인 전까지 반입 금지. 의심되면 멈추고 질문.

---

## 7. 리팩터링 작업 규칙

1. **Discovery audit 먼저** — README/추측 기반 작업 금지. 실제 코드·테스트를 읽고 근본 원인을 규명한 뒤 손댄다.
2. **TDD** — 실패 테스트 → 구현 → green. unit/integration/smoke 3계층(`/tdd` 스킬).
3. **작은 PR 분할** — 되돌리기 어려운 결정(모델·계약)부터, 한 번에 한 관심사.
4. **CLAUDE.md 자동 갱신 규칙 준수** — 툴/워크플로우/UI/설정/의존성 변경 시 지정 파일 동반 수정.
5. **리뷰** — `code-reviewer` 서브에이전트로 diff를 규칙·불변식·보안·스키마 기준 검토 후 커밋.
6. **사람 결정 필요 항목**(호스트 머신·사내 LLM 멀티모달·백엔드 확정 등)은 멈추고 질문한다.
