import pyautogui

from agent.core.ocr_provider import get_ocr_provider


def capture_screen_ocr() -> str:
    screenshot = pyautogui.screenshot()
    text = get_ocr_provider().image_to_string(screenshot)
    return text.strip() or '(인식된 텍스트 없음)'


MANIFEST = [
    {
        "name": "capture_screen_ocr",
        "label": "전체 화면 OCR",
        "schema": {
            "type": "function",
            "function": {
                "name": "capture_screen_ocr",
                "description": "전체 화면을 캡처하고 OCR로 텍스트를 추출합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: capture_screen_ocr()
    }
]
