"""OCRProvider 어댑터 수용 테스트 (트랙3a 1단계 게이트).

명세: docs/specs/ocr-provider.md. 실 tesseract/디스플레이 없이 검증(monkeypatch).
구현 전에는 ImportError/AttributeError로 실패(=레드). 구현 후 전부 green이면 완료.
"""
import json
import numpy as np
import pytest


# ── get_ocr_provider / 폴백 ──────────────────────────────────────
def test_default_provider_is_uia(monkeypatch):
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    from agent.core import ocr_provider as op
    if hasattr(op, "reset_ocr_provider"):
        op.reset_ocr_provider()
    assert isinstance(op.get_ocr_provider(), op.UIAutomationProvider)


def test_unknown_provider_falls_back_to_uia(monkeypatch):
    monkeypatch.setenv("OCR_PROVIDER", "does-not-exist-xyz")
    from agent.core import ocr_provider as op
    if hasattr(op, "reset_ocr_provider"):
        op.reset_ocr_provider()
    assert isinstance(op.get_ocr_provider(), op.UIAutomationProvider)  # 예외 없이 폴백


# ── TesseractProvider 래핑 ───────────────────────────────────────
def test_tesseract_image_to_string_passthrough(monkeypatch):
    from agent.core import ocr_provider as op
    calls = {}

    def fake_i2s(image, lang=None):
        calls["image"] = image
        calls["lang"] = lang
        return "  hello  "  # 원시(strip 안 함) 반환 검증

    monkeypatch.setattr(op.pytesseract, "image_to_string", fake_i2s)
    monkeypatch.setenv("OCR_LANG", "kor+eng")
    monkeypatch.setenv("OCR_TESSERACT_CMD", "X:/tess.exe")

    out = op.TesseractProvider().image_to_string("IMG")
    assert out == "  hello  "
    assert calls["lang"] == "kor+eng"
    assert op.pytesseract.pytesseract.tesseract_cmd == "X:/tess.exe"


def test_tesseract_image_to_data_uses_dict_output(monkeypatch):
    from agent.core import ocr_provider as op
    captured = {}

    def fake_i2d(image, lang=None, output_type=None):
        captured["output_type"] = output_type
        return {"text": ["hi"], "conf": [95], "left": [0], "top": [0], "width": [10], "height": [10]}

    monkeypatch.setattr(op.pytesseract, "image_to_data", fake_i2d)
    data = op.TesseractProvider().image_to_data("IMG")
    assert isinstance(data, dict) and data["text"] == ["hi"]
    assert captured["output_type"] == op.pytesseract.Output.DICT


# ── 도구 4곳이 provider 경유(직접 pytesseract 호출 없음) ──────────
class _FakeProvider:
    def __init__(self):
        self.used = {"s": False, "d": False}

    def image_to_string(self, image, lang=None):
        self.used["s"] = True
        return "배포 완료"

    def image_to_data(self, image, lang=None):
        self.used["d"] = True
        return {"text": ["배포"], "conf": [90], "left": [10], "top": [20], "width": [40], "height": [12]}


def test_capture_screen_ocr_routes_through_provider(monkeypatch):
    from agent.tools import ocr
    monkeypatch.setattr(ocr.pyautogui, "screenshot", lambda: "FAKE")
    fake = _FakeProvider()
    monkeypatch.setattr(ocr, "get_ocr_provider", lambda: fake)
    out = ocr.capture_screen_ocr()
    assert fake.used["s"] and "배포 완료" in out


def test_capture_region_ocr_routes_through_provider(monkeypatch):
    from agent.tools import screen
    monkeypatch.setattr(screen, "_capture_region", lambda x, y, w, h: np.zeros((2, 2, 3), np.uint8))
    fake = _FakeProvider()
    monkeypatch.setattr(screen, "get_ocr_provider", lambda: fake)
    out = screen.capture_region_ocr(0, 0, 2, 2)
    assert fake.used["s"] and "배포 완료" in out


def test_find_text_location_routes_through_provider(monkeypatch):
    from agent.tools import screen
    monkeypatch.setattr(screen, "_capture_full", lambda: np.zeros((2, 2, 3), np.uint8))
    fake = _FakeProvider()
    monkeypatch.setattr(screen, "get_ocr_provider", lambda: fake)
    out = json.loads(screen.find_text_location("배포"))
    assert fake.used["d"] and out["found"] is True


def test_wait_for_text_routes_through_provider(monkeypatch):
    from agent.tools import screen
    monkeypatch.setattr(screen, "_capture_full", lambda: np.zeros((2, 2, 3), np.uint8))
    fake = _FakeProvider()
    monkeypatch.setattr(screen, "get_ocr_provider", lambda: fake)
    out = json.loads(screen.wait_for_text("배포", timeout=2))
    assert fake.used["s"] and out["found"] is True
