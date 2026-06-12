# 스펙 — OCRProvider 어댑터 (트랙 2 첫 스펙)

> 상태: 구현 대상 · 수용 게이트 = `tests/unit/test_ocr_provider.py` + 기존 `.\test.ps1` 전부 green
> 트랙 3a(Tesseract 제거)의 1단계 — 이번엔 **추상화만**, tesseract 제거는 후속.

## 해결하는 문제

OCR이 `pytesseract`에 **직접 결합**돼 있어(`ocr.py` 1곳, `screen.py` 3곳) 향후 대안(Windows UI Automation 접근성 트리,
멀티모달 LLM)으로 **교체·롤백이 불가**하다. 폐쇄망 tesseract 바이너리·`kor.traineddata` 반입 부담도 이 결합 때문에 제거하기 어렵다.

## 설계

신규 `agent/core/ocr_provider.py`:

- **`OCRProvider`(추상 베이스)** — 두 메서드:
  - `image_to_string(image, lang: str | None = None) -> str` — **원시 텍스트 그대로 반환**(strip/후처리 안 함, 호출부 책임).
  - `image_to_data(image, lang: str | None = None) -> dict` — `pytesseract.image_to_data(..., output_type=Output.DICT)`와 같은 키(`text`/`conf`/`left`/`top`/`width`/`height`)의 dict.
- **`TesseractProvider(OCRProvider)`** — 기존 동작 그대로 래핑:
  - `lang` 기본값 = `OCR_LANG`(기본 `kor+eng`), `tesseract_cmd` = `OCR_TESSERACT_CMD`(기본 `tesseract`)를 호출 시 `pytesseract.pytesseract.tesseract_cmd`에 설정.
  - `image_to_data`는 `output_type=pytesseract.Output.DICT` 사용.
- **`get_ocr_provider() -> OCRProvider`** — `OCR_PROVIDER`(env, 기본 `"tesseract"`)로 레지스트리 조회. **미지원 값이면 `TesseractProvider`로 폴백(예외 금지)**. 인스턴스는 싱글턴 캐시(성능). env 변경 테스트를 위해 `reset_ocr_provider()`(캐시 비움) 헬퍼 제공 권장.

### 호출부 라우팅 (4곳)
각 도구 모듈은 **`from agent.core.ocr_provider import get_ocr_provider`** 로 가져와 사용한다(테스트가 모듈 네임스페이스로 monkeypatch):

| 파일·함수 | 기존 | 변경 |
|---|---|---|
| `agent/tools/ocr.py` `capture_screen_ocr` | `pytesseract.image_to_string(screenshot, lang=lang)` | `get_ocr_provider().image_to_string(screenshot)` (그 후 기존 `.strip() or "(인식된 텍스트 없음)"` 유지) |
| `agent/tools/screen.py` `capture_region_ocr` | `pytesseract.image_to_string(pil, lang=_lang())` | `get_ocr_provider().image_to_string(pil)` (strip 유지) |
| `agent/tools/screen.py` `find_text_location` | `pytesseract.image_to_data(pil, lang=_lang(), output_type=DICT)` | `get_ocr_provider().image_to_data(pil)` (이후 후보 추출 로직 그대로) |
| `agent/tools/screen.py` `wait_for_text` | `pytesseract.image_to_string(pil, lang=_lang())` | `get_ocr_provider().image_to_string(pil)` (이후 비교 로직 그대로) |

→ 변경 후 `ocr.py`·`screen.py`의 **도구 함수 안에 `pytesseract.image_to_*` 직접 호출이 남으면 안 된다**(provider 경유). `screen.py`의 `_tesseract_cmd()`/`_lang()`/`_capture_*`/`_bgr_to_pil` 유틸은 유지.

## 범위
- **IN**: `ocr_provider.py` 추상화 + 4곳 라우팅 + `.env.example` `OCR_PROVIDER` + CLAUDE.md 현재 상태 표 1행.
- **OUT**(후속): tesseract 실제 제거(`requirements.txt`/`SETUP.md` 유지), UIA provider, 멀티모달 provider(사내 LLM 멀티모달 확인 전제), 새 의존성.

## 수용 기준 (테스트로 검증)
- [ ] `get_ocr_provider()` 기본 → `TesseractProvider`; `OCR_PROVIDER` 미지원값 → 폴백(예외 없음).
- [ ] `TesseractProvider.image_to_string`이 `pytesseract.image_to_string`에 `lang` 전달 + `tesseract_cmd` 설정 + 원시 반환.
- [ ] `TesseractProvider.image_to_data`가 `Output.DICT`로 dict 반환.
- [ ] 4개 도구 함수가 provider 경유(직접 pytesseract 호출 없음) — monkeypatch로 검증.
- [ ] `OCR_PROVIDER` 미설정 시 기존과 동일 동작. 기존 `.\test.ps1` 전부 green. smoke 툴 수 132 불변.

## 비고
- provider는 **도구(MANIFEST)가 아니다** → `EXPECTED_TOOL_COUNT` 불변.
- 후처리(strip/“없음” 표기)는 **도구에 유지**, provider는 순수 래퍼.
