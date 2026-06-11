# 백로그 M — 컨텍스트 허용량(토큰) 초과 자동 처리 / 이미지 토큰 다이어트 🧮

> 상태: ✅ 완료 (2026-06-11, M1~M5) · 발단: `gpt-5.4-nano`로 `capture_screen` 이미지 주입 중 컨텍스트 초과 실패 목격

## 목표

이미지·텍스트가 누적돼 컨텍스트 허용량을 초과해도 **"전면 실패" 없이** 항상 `DONE`으로 마감한다.
표준 에이전트 관행대로 **선제 이미지 다이어트 → 이미지 eviction → 정확한 토큰 추정 → 400 점진적 복구 →
모델별 컨텍스트 예산**의 5단 방어를 둔다.

**사용자 결정**: 이미지 전략 = **적응형**(평상시 고품질, 임계 근접 시에만 다운스케일/detail 강등),
범위 = **전체 다층(M1~M5)**.

## 설계 원칙 #0 — 모델 무관(model-agnostic) [필수 요구사항]

> gpt-5.4-nano는 "처음 터진" 케이스일 뿐 특정 모델 버그가 아니다. **어떤 모델로 바꿔도** 동작해야 한다.

- **M4가 진짜 백스톱이고 완전 모델 무관**: 추정(M3)·예산(M5)이 틀려도, 런타임에 "컨텍스트 초과" 응답이
  오면 prune→compact→재시도로 **실제 실패를 복구**한다. M1·M3·M5는 *선제 타이밍*용, M4는 *실패 시 복구*용 — 이중 방어.
- **M4 에러 탐지는 프로바이더 교차로 견고하게**: OpenAI `BadRequestError`(400)·`context_length_exceeded`뿐 아니라
  사내/타 프로바이더의 다양한 문구(`maximum context`/`too many tokens`/`reduce the length`/`input is too long` 등)를
  **상태코드 + 부분문자열 다중 매칭**으로 잡는다. **그리고 문구를 못 알아봐도**: 같은 요청이 4xx로 반복 실패하면
  마지막 수단으로 일단 shed&retry(보수적). 즉 "인식 못 한 새 모델"도 안전 측으로 떨어진다.
- **M5 미지의 모델 = 보수적 폴백**: 모델→윈도우 맵에 없으면 작은 보수값(예: 32k)으로 잡아 일찍 compaction.
  과대(128k 가정)보다 과소가 안전 — 과소면 좀 더 자주 압축할 뿐, 과대면 초과 실패. M4가 최종 보증.
- **`detail` 필드는 OpenAI vision 전용**: 미지원 엔드포인트 대비 `VISION_DETAIL=off`면 필드 자체를 빼는 스위치 둠.
  미설정 시 잉여 필드로 두어도 대개 무해.
- **검증**: M4 통합 테스트를 **여러 에러 문구 변형**(OpenAI/사내/미인식)으로 파라미터화해 모두 `DONE` 마감 확인.

## 발단 (현황의 구멍)

- **이미지 비용이 구조적으로 최악**: `capture_screen`이 PNG(무압축) + 원본 해상도 + `detail:"high"` 고정
  주입 (`agent/tools/vision.py:91-108`, 주입부 `agent/server.py:705-712`). 다운스케일·압축·detail 조절 없음.
- **토큰 추정 부정확**: `_estimate_tokens`가 이미지를 무조건 ~1000토큰 고정으로 셈
  (`agent/server.py:160-179`). 실제 타일링 비용·detail과 어긋나 compaction 타이밍이 빗나감.
- **이미지 제거 정책 부재**: compaction(`agent/core/compaction.py:43-78`)은 텍스트 중간만 요약,
  최근 `COMPACT_KEEP_RECENT=8`턴의 이미지는 그대로 둠. 캡처 누적 시 이미지 줄일 수단 없음.
- **400 복구 없음**: LLM 호출(`server.py:418`)이 전용 try/except 없이 전역 catch(`server.py:720-724`)로
  떨어져, `context_length_exceeded`(400)면 **채팅 전면 실패로 종료** — 커밋 `bf5f288`(tools 128 한계)과 동류.
- **모델별 컨텍스트 무시**: `_CONTEXT_MAX_TOKENS=128_000` 하드코딩(`server.py:203`). nano급은 더 작을 수 있음.

## 업계 표준 해법 (조사)

| 기법 | 출처/관행 | 적용점 |
|------|-----------|--------|
| 이미지 다운스케일(긴 변 캡) | Anthropic ~1568px / OpenAI 짧은 변 768px 타일 | `vision.py` PIL `thumbnail` |
| JPEG 압축 | 스크린샷 PNG 대비 ~5–10x 작음 | `vision.py` `save(fmt, quality)` |
| `detail: low/high/auto` | OpenAI vision: low=고정 85토큰, high=타일 합산 | 주입부 detail 동적화 |
| 이미지 eviction(최신 N개만) | Claude Code·computer-use류: 과거 스크린샷→텍스트 자리표시자 | 새 `prune_images()` |
| 정확 토큰 카운트(타일링 공식) | OpenAI 이미지 토큰 = 타일 수×비용+base | `_estimate_tokens` 교체 |
| 400 점진적 복구(progressive shedding) | LangChain/AutoGPT류 retry-on-context-error | 호출 주변 전용 try/except |
| 모델별 컨텍스트 예산 | 라우터/게이트웨이 표준 | `config.py` 모델→윈도우 맵 |

## 설계 (M1~M5, TDD·클린룸)

> 순수 함수 우선 + monkeypatch 가능. 불변식 **I1(tool 짝 보존)**·**I4(항상 DONE)** 유지.

### M1 — 적응형 이미지 다이어트 (`agent/tools/vision.py`) ✅ 완료 (2026-06-11)
- 캡처 직후 **긴 변 캡 다운스케일** + **포맷/품질 선택**. 봉투(`__capture__`)에 `mime`·`detail`·`width`·`height` 동봉.
  - `_prepare_capture_image(png)` 순수 함수(다운스케일·JPEG/PNG 인코딩, 디코딩 실패 시 원본 통과 폴백).
- 신규 `.env`: `VISION_MAX_EDGE`(1568)·`VISION_IMAGE_FORMAT`(jpeg)·`VISION_JPEG_QUALITY`(80)·`VISION_DETAIL`(auto).
- **적응형 detail**: `resolve_detail(configured, near_limit)` — `_estimate_tokens`가 임계 근접 시 새 이미지를 low로
  강등, `off`면 detail 필드 제거(미지원 엔드포인트 대비). 주입은 `build_capture_message(env, near_limit)` 순수 함수.
- 주입부(`server.py`) 하드코딩 `"detail":"high"`·`data:image/png` → 봉투 값 사용 + 적응형으로 교체.
- 테스트: `tests/unit/test_vision.py` (다운스케일·JPEG·폴백·detail 규칙·봉투 메타, 15개 그린). 전체 482 passed.

### M2 — 이미지 eviction (`agent/core/compaction.py` + `server.py`) ✅ 완료 (2026-06-11)
- 순수 함수 `prune_images(messages, *, keep_last_images=K)`: user 멀티모달의 `image_url` 중 최신 K개만 남기고
  과거는 `PRUNED_IMAGE_PLACEHOLDER`(`[이전 화면 이미지 — 생략(n번째 캡처)]`)로 치환. 동반 텍스트 블록·입력 불변 보존.
  `.env` `VISION_KEEP_LAST_IMAGES`(기본 2). 한도 이하면 동일 객체 반환(멱등).
- 루프 진입부 compaction 블록 **직전** 적용(텍스트 compaction과 독립). 정리 시 `COMPACTION` SSE 고지.
- I1 무파손(이미지는 user 메시지) — `test_prune_preserves_tool_pairs_no_orphan`로 보장.
- 테스트: `tests/unit/test_compaction.py` +7(최신 K 유지·자리표시자·동반텍스트·멱등·불변·짝보존·음수). 전체 489 passed.

### M3 — 정확한 토큰 추정 (`agent/core/tokens.py` 신규 + `server._estimate_tokens` 위임) ✅ 완료 (2026-06-11)
- 순수 모듈 `agent/core/tokens.py`: `estimate_message_tokens` 합산, `image_block_tokens`(detail=low→고정 85,
  high/auto→`high_detail_tokens` 타일 공식: 2048박스→짧은변 768→512타일), `image_dims_from_data_url`
  (PNG/JPEG 헤더 prefix만 디코드해 치수 파싱, 미상 시 보수적 기본 1105), `estimate_text_tokens`(tiktoken 우선·폴백).
- `server._estimate_tokens`는 이 모듈에 위임. 거대 base64 길이에 비례하지 않음(과대계상 방지 회귀 유지).
- `tiktoken`은 **선택 의존성**(`requirements.txt` 추가, 미설치 시 4-char 휴리스틱 폴백 — 폐쇄망 안전).
- 테스트: `tests/unit/test_tokens.py`(15: 치수 파싱·타일링·블록·합산·거대 base64). 전체 504 passed.

### M4 — 400 점진적 복구 (`agent/core/overflow.py` 신규 + `server.py` generate 루프) ✅ 완료 (2026-06-11)
- 순수 모듈 `agent/core/overflow.py`: `is_context_overflow`(문구 다중 매칭)·`is_bad_request`(400, 401/403/404 제외)·
  `is_recoverable`. 모델 무관(원칙 #0) — 사내/타 프로바이더 문구·미인식 400 모두 마지막 수단으로 shed&retry.
- `server.generate` 의 `client.chat.completions.create(...)` **호출만** 감싸는 `while stream is None` 복구 루프:
  1. `prune_images(keep_last_images=1)` → 재시도
  2. `compact_messages` **강제 1회**(MAX_COMPACT 무관, executor) → 재시도
  3. 한도(`MAX_OVERFLOW_RETRY`, 기본 2) 소진 시 친절한 안내 ERROR 후 `DONE`(I4). 비복구 예외는 그대로 raise→전역 핸들러.
- 신규 `CONTEXT_TRIM` SSE 고지(`events.py`) + `chat.js`/`style.css` 무딘 안내 노트. 스트림 시작 전 헤드 검증이라 부분 출력 오염 없음.
- 테스트: `tests/unit/test_overflow.py`(8) + `test_server_chat.py::TestOverflowRecovery`(4: prune복구·compact복구·소진graceful·일반예외 비재시도). 전체 516 passed. ✅ 완료 (2026-06-11)

### M5 — 모델별 컨텍스트 예산 (`agent/config.py` + `server.py`) ✅ 완료 (2026-06-11)
- `config.get_context_window(model)`: `.env LLM_{PROFILE}_CONTEXT_TOKENS`(정확값) > 내장 맵 `MODEL_CONTEXT_WINDOWS`
  (최장 키 매칭: gpt-4o=128k, gpt-4=8k, gpt-3.5=16k, gpt-4.1=1M, o1/o3=200k …) > `LLM_DEFAULT_CONTEXT_TOKENS`/128k 폴백.
  잘못된 값·미지 모델에도 항상 양수.
- `server.generate`가 요청마다 `context_max = get_context_window(model)` 계산 → compaction 임계·near_limit·
  CONTEXT_USAGE `tokens_total` 모두 모델별 값 사용(헤더 바도 실제 윈도우 반영).
- **gpt-5.4-nano 등 미지 모델은 `.env`로 정확값 지정 권장**(추정 오차는 M4 400 복구가 최종 보증 — 원칙 #0).
- 테스트: `tests/unit/test_context_window.py`(7: 맵·최장키·미지·env오버라이드·잘못된값·양수). 전체 523 passed.

## 재사용 자산
- `compact_messages`·`_safe_tail_start`·`has_orphan_tool`(`compaction.py`) — eviction도 동일 모듈/테스트 패턴.
- `parse_capture_envelope`(`vision.py`) — 봉투 확장 시 그대로.
- `COMPACTION` SSE·상태 바·`MAX_COMPACT`/`COMPACT_RATIO` 게이트 패턴(`server.py`).

## 파일
- 수정: `agent/tools/vision.py`(M1)·`agent/core/compaction.py`(M2)·`agent/server.py`(M2–M5)·
  `agent/config.py`(M5)·`agent/core/events.py`(M4)·`.env.example`·`SETUP.md`·`CLAUDE.md`.
- 신규: 이 문서.

## 테스트 (TDD)
- 단위: `tests/unit/test_compaction.py`에 `prune_images`(K개 유지·과거 치환·I1 무파손),
  `_estimate_tokens` 타일링, 적응형 detail 강등.
- 회귀: `_estimate_tokens` 변경이 기존 compaction 트리거 테스트 무파손.
- 통합: FakeLLM이 첫 호출 `context_length_exceeded` 던지면 prune→compact→재시도 후 `DONE`(I4).
- 수동: `capture_screen` 반복 누적 → eviction·JPEG 페이로드 축소·detail 강등 로그 확인. `.\test.ps1` 그린.

## 열린 질문 · 블로커
- nano 모델의 실제 컨텍스트 윈도우 값(회사 LLM 엔드포인트별 상이 가능) — M5 맵 채울 때 확인.
- `tiktoken` 폐쇄망 사전반입 여부 — 없으면 휴리스틱 유지(M3 폴백).
- 다운스케일/JPEG가 사내 화면 글자 판독 정확도에 주는 영향 — 적응형이라 평상 고품질 유지하나 실측 권장.
