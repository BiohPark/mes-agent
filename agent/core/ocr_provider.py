"""OCR 제공자 어댑터 — OCR을 pytesseract에 직접 결합하지 않고 교체·롤백 가능하게(트랙 3a 1단계).

명세: docs/specs/ocr-provider.md. 이번 단계는 **추상화만**(tesseract 제거는 후속).
향후 provider 후보: UIA(접근성 트리, `agent/tools/ui_automation.py`), multimodal(LLM, 사내 멀티모달 확인 전제).
"""
import os
import pytesseract


class OCRProvider:
    """OCR 백엔드 추상 인터페이스. image는 PIL.Image 또는 동등 객체."""

    def image_to_string(self, image, lang=None) -> str:
        raise NotImplementedError

    def image_to_data(self, image, lang=None) -> dict:
        raise NotImplementedError


def _lang(lang):
    return lang or os.environ.get("OCR_LANG", "kor+eng")


def _tesseract_cmd():
    return os.environ.get("OCR_TESSERACT_CMD", "tesseract")


class TesseractProvider(OCRProvider):
    """pytesseract 래퍼 — 기존 동작 보존. 원시 결과 반환(strip/후처리는 호출부 책임)."""

    def image_to_string(self, image, lang=None) -> str:
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
        return pytesseract.image_to_string(image, lang=_lang(lang))

    def image_to_data(self, image, lang=None) -> dict:
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
        return pytesseract.image_to_data(
            image, lang=_lang(lang), output_type=pytesseract.Output.DICT
        )


# 제공자 레지스트리 (이름 → 클래스). 향후 "uia"·"multimodal" 추가 지점.
_REGISTRY = {
    "tesseract": TesseractProvider,
}

_cached = None
_cached_name = None


def get_ocr_provider() -> OCRProvider:
    """`OCR_PROVIDER`(env, 기본 tesseract)에 맞는 provider 싱글턴 반환.
    미지원 값이면 tesseract로 폴백(예외 금지)."""
    global _cached, _cached_name
    name = os.environ.get("OCR_PROVIDER", "tesseract").strip().lower()
    cls = _REGISTRY.get(name, TesseractProvider)
    if _cached is None or _cached_name != name:
        _cached = cls()
        _cached_name = name
    return _cached


def reset_ocr_provider() -> None:
    """provider 싱글턴 캐시를 비운다(테스트/런타임 전환용)."""
    global _cached, _cached_name
    _cached = None
    _cached_name = None
