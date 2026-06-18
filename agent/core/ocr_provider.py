"""OCR 제공자 어댑터 — OCR을 pytesseract에 직접 결합하지 않고 교체·롤백 가능하게(트랙 3a 1단계).

명세: docs/specs/ocr-provider.md. 이번 단계는 **추상화만**(tesseract 제거는 후속).
향후 provider 후보: UIA(접근성 트리, `agent/tools/ui_automation.py`), multimodal(LLM, 사내 멀티모달 확인 전제).
"""
import os

try:
    import pytesseract
except ImportError:
    pytesseract = None


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
        if pytesseract is None:
            return "(pytesseract 패키지가 설치되어 있지 않습니다)"
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
        return pytesseract.image_to_string(image, lang=_lang(lang))

    def image_to_data(self, image, lang=None) -> dict:
        if pytesseract is None:
            return {"text": [], "left": [], "top": [], "width": [], "height": [], "conf": []}
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
        return pytesseract.image_to_data(
            image, lang=_lang(lang), output_type=pytesseract.Output.DICT
        )


class UIAutomationProvider(OCRProvider):
    """Win32 UI Automation 기반의 대체 OCR 제공자.
    Tesseract 엔진 설치 없이 Win32 윈도우 및 자식 컨트롤을 구조적으로 탐색하여 텍스트 및 위치를 획득합니다.
    """

    def _get_win32gui(self):
        try:
            import win32gui
            return win32gui
        except ImportError:
            return None

    def _is_in_region(self, hwnd, region, wg):
        if not region:
            return True
        try:
            rx, ry, rw, rh = region
            rect = wg.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            cx = left + (right - left) // 2
            cy = top + (bottom - top) // 2
            return rx <= cx <= rx + rw and ry <= cy <= ry + rh
        except Exception:
            return False

    def image_to_string(self, image, lang=None) -> str:
        wg = self._get_win32gui()
        if not wg:
            return "(pywin32가 설치되어 있지 않습니다)"

        region = getattr(image, "region", None)
        texts = []

        def add_node(hwnd):
            if not wg.IsWindowVisible(hwnd):
                return
            if not self._is_in_region(hwnd, region, wg):
                return
            t = wg.GetWindowText(hwnd).strip()
            if t:
                texts.append(t)

        def cb(hwnd, _):
            add_node(hwnd)
            try:
                wg.EnumChildWindows(hwnd, lambda h, _: add_node(h), None)
            except Exception:
                pass

        try:
            wg.EnumWindows(cb, None)
        except Exception as e:
            return f"(UIA 텍스트 획득 오류: {e})"

        return "\n".join(texts)

    def image_to_data(self, image, lang=None) -> dict:
        data = {
            "text": [],
            "left": [],
            "top": [],
            "width": [],
            "height": [],
            "conf": []
        }
        wg = self._get_win32gui()
        if not wg:
            return data

        region = getattr(image, "region", None)

        def add_node(hwnd):
            if not wg.IsWindowVisible(hwnd):
                return
            if not self._is_in_region(hwnd, region, wg):
                return
            text = wg.GetWindowText(hwnd).strip()
            if not text:
                return
            try:
                rect = wg.GetWindowRect(hwnd)
                left, top, right, bottom = rect
                w = right - left
                h = bottom - top
                if w <= 0 or h <= 0:
                    return
                data["text"].append(text)
                data["left"].append(left)
                data["top"].append(top)
                data["width"].append(w)
                data["height"].append(h)
                data["conf"].append(100)
            except Exception:
                pass

        def cb(hwnd, _):
            add_node(hwnd)
            try:
                wg.EnumChildWindows(hwnd, lambda h, _: add_node(h), None)
            except Exception:
                pass

        try:
            wg.EnumWindows(cb, None)
        except Exception:
            pass

        return data


# 제공자 레지스트리 (이름 → 클래스).
_REGISTRY = {
    "tesseract": TesseractProvider,
    "uia": UIAutomationProvider,
}

_cached = None
_cached_name = None


def get_ocr_provider() -> OCRProvider:
    """`OCR_PROVIDER`(env, 기본 uia)에 맞는 provider 싱글턴 반환.
    미지원 값이면 uia로 폴백(예외 금지)."""
    global _cached, _cached_name
    name = os.environ.get("OCR_PROVIDER", "uia").strip().lower()
    cls = _REGISTRY.get(name, UIAutomationProvider)
    if _cached is None or _cached_name != name:
        _cached = cls()
        _cached_name = name
    return _cached


def reset_ocr_provider() -> None:
    """provider 싱글턴 캐시를 비운다(테스트/런타임 전환용)."""
    global _cached, _cached_name
    _cached = None
    _cached_name = None
