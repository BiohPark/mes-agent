import os
import pytesseract
import pyautogui

def capture_screen_ocr() -> str:
    tesseract_cmd = os.environ.get('OCR_TESSERACT_CMD', 'tesseract')
    lang = os.environ.get('OCR_LANG', 'kor+eng')
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    screenshot = pyautogui.screenshot()
    text = pytesseract.image_to_string(screenshot, lang=lang)
    return text.strip() or '(인식된 텍스트 없음)'
