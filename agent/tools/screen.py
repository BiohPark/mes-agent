"""
화면 인텔리전스 도구
- 영역 OCR, 이미지 템플릿 매칭, 텍스트 위치 찾기
- 요소 대기 (wait_for_image, wait_for_text)
- 스크린샷 비교, 픽셀 색상, 창별 캡처
"""

import os
import time
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
import mss
import pytesseract
from PIL import Image


# ── 공통 유틸 ─────────────────────────────────────────────────

def _tesseract_cmd() -> str:
    return os.environ.get("OCR_TESSERACT_CMD", "tesseract")


def _lang() -> str:
    return os.environ.get("OCR_LANG", "kor+eng")


def _capture_full() -> np.ndarray:
    """전체 화면을 BGR numpy 배열로 반환 (mss 사용, 빠름)."""
    with mss.mss() as sct:
        monitor = sct.monitors[0]  # 전체 가상 화면
        shot = sct.grab(monitor)
        img = np.array(shot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def _capture_region(x: int, y: int, w: int, h: int) -> np.ndarray:
    """지정 영역을 BGR numpy 배열로 반환."""
    with mss.mss() as sct:
        region = {"left": x, "top": y, "width": w, "height": h}
        shot = sct.grab(region)
        img = np.array(shot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def _bgr_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


# ── 공개 툴 ───────────────────────────────────────────────────

def capture_region_ocr(x: int, y: int, width: int, height: int) -> str:
    """지정 영역만 캡처하고 OCR로 텍스트를 추출합니다.
    전체 화면 OCR보다 빠르고 정확합니다."""
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    img = _capture_region(x, y, width, height)
    pil = _bgr_to_pil(img)
    text = pytesseract.image_to_string(pil, lang=_lang())
    return text.strip() or "(인식된 텍스트 없음)"


def find_image_on_screen(template_path: str, confidence: float = 0.8) -> str:
    """화면에서 템플릿 이미지를 찾아 중심 좌표를 반환합니다.
    confidence(0~1)는 매칭 정확도 임계값입니다."""
    if not Path(template_path).exists():
        return json.dumps({"found": False, "error": f"템플릿 파일 없음: {template_path}"})

    screen = _capture_full()
    template = cv2.imread(template_path)
    if template is None:
        return json.dumps({"found": False, "error": "템플릿 이미지 로드 실패"})

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < confidence:
        return json.dumps({"found": False, "confidence": round(float(max_val), 3),
                           "message": f"매칭 실패 (정확도 {max_val:.1%} < {confidence:.0%})"})

    th, tw = template.shape[:2]
    cx = max_loc[0] + tw // 2
    cy = max_loc[1] + th // 2
    return json.dumps({"found": True, "x": cx, "y": cy,
                       "confidence": round(float(max_val), 3)})


def find_text_location(text: str) -> str:
    """화면에서 특정 텍스트의 위치(중심 좌표)를 찾아 반환합니다.
    찾은 경우 x, y 좌표를 반환하며, 바로 mouse_click으로 클릭할 수 있습니다."""
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    screen = _capture_full()
    pil = _bgr_to_pil(screen)
    data = pytesseract.image_to_data(pil, lang=_lang(), output_type=pytesseract.Output.DICT)

    text_lower = text.lower()
    candidates = []
    n = len(data["text"])
    for i in range(n):
        word = str(data["text"][i]).strip()
        if not word or int(data["conf"][i]) < 30:
            continue
        if text_lower in word.lower():
            x = data["left"][i] + data["width"][i] // 2
            y = data["top"][i] + data["height"][i] // 2
            candidates.append({"x": x, "y": y, "word": word,
                                "conf": int(data["conf"][i])})

    if not candidates:
        return json.dumps({"found": False, "message": f"'{text}' 텍스트를 찾지 못했습니다."})

    best = max(candidates, key=lambda c: c["conf"])
    return json.dumps({"found": True, "x": best["x"], "y": best["y"],
                       "matched_word": best["word"], "conf": best["conf"],
                       "all_matches": len(candidates)})


def wait_for_image(template_path: str, timeout: int = 10,
                   confidence: float = 0.8, interval: float = 0.5) -> str:
    """지정한 이미지가 화면에 나타날 때까지 기다립니다.
    배포 완료 버튼, 로딩 스피너 사라짐 등을 감지하는 데 사용합니다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = json.loads(find_image_on_screen(template_path, confidence))
        if result.get("found"):
            return json.dumps({"found": True, "x": result["x"], "y": result["y"],
                               "elapsed": round(deadline - timeout - time.time() + timeout, 1)})
        time.sleep(interval)
    return json.dumps({"found": False, "timeout": timeout,
                       "message": f"{timeout}초 내에 이미지를 찾지 못했습니다."})


def wait_for_text(text: str, timeout: int = 10, interval: float = 0.5) -> str:
    """지정한 텍스트가 화면에 나타날 때까지 기다립니다.
    '배포 완료', '오류' 등의 메시지를 감지하는 데 사용합니다."""
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    deadline = time.time() + timeout
    start = time.time()
    while time.time() < deadline:
        screen = _capture_full()
        pil = _bgr_to_pil(screen)
        page_text = pytesseract.image_to_string(pil, lang=_lang())
        if text.lower() in page_text.lower():
            elapsed = round(time.time() - start, 1)
            return json.dumps({"found": True, "elapsed_sec": elapsed,
                               "message": f"'{text}' 텍스트 발견 ({elapsed}초 후)"})
        time.sleep(interval)
    return json.dumps({"found": False, "timeout": timeout,
                       "message": f"{timeout}초 내에 '{text}' 텍스트를 찾지 못했습니다."})


def compare_screenshots(before_path: str, after_path: str) -> str:
    """두 스크린샷을 비교하여 변화 여부와 차이 비율을 반환합니다.
    배포 전후 화면 검증, UI 회귀 테스트에 활용합니다."""
    img_before = cv2.imread(before_path)
    img_after = cv2.imread(after_path)
    if img_before is None or img_after is None:
        return json.dumps({"error": "이미지 파일을 로드할 수 없습니다."})

    # 크기 맞추기
    if img_before.shape != img_after.shape:
        img_after = cv2.resize(img_after, (img_before.shape[1], img_before.shape[0]))

    diff = cv2.absdiff(img_before, img_after)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    changed_pixels = int(np.sum(thresh > 0))
    total_pixels = thresh.shape[0] * thresh.shape[1]
    diff_percent = round(changed_pixels / total_pixels * 100, 2)

    return json.dumps({
        "changed": diff_percent > 0.5,
        "diff_percent": diff_percent,
        "changed_pixels": changed_pixels,
        "message": f"화면 변화: {diff_percent}% ({'변화 있음' if diff_percent > 0.5 else '거의 동일'})"
    })


def save_screenshot(save_path: str = "") -> str:
    """현재 화면 전체를 파일로 저장합니다.
    save_path를 생략하면 임시 폴더에 자동 저장됩니다."""
    if not save_path:
        fd, save_path = tempfile.mkstemp(suffix=".png", prefix="screenshot_")
        os.close(fd)
    img = _capture_full()
    cv2.imwrite(save_path, img)
    return json.dumps({"path": save_path, "message": f"스크린샷 저장: {save_path}"})


def get_pixel_color(x: int, y: int) -> str:
    """지정 좌표의 픽셀 색상을 반환합니다.
    버튼 활성화 여부, 상태 표시등 색 판단에 활용합니다."""
    img = _capture_region(x, y, 1, 1)
    b, g, r = img[0, 0]
    hex_color = "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
    return json.dumps({"x": x, "y": y, "r": int(r), "g": int(g), "b": int(b),
                       "hex": hex_color})


def capture_window_screenshot(title: str, save_path: str = "") -> str:
    """제목으로 창을 찾아 해당 창 영역만 캡처합니다."""
    import pygetwindow as gw
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    if not matches:
        return json.dumps({"error": f"창을 찾지 못했습니다: '{title}'"})
    win = matches[0]
    x, y, w, h = win.left, win.top, win.width, win.height
    if w <= 0 or h <= 0:
        return json.dumps({"error": "창 크기가 올바르지 않습니다."})

    if not save_path:
        fd, save_path = tempfile.mkstemp(suffix=".png", prefix=f"win_{title[:10]}_")
        os.close(fd)
    img = _capture_region(x, y, w, h)
    cv2.imwrite(save_path, img)
    return json.dumps({"path": save_path, "title": win.title,
                       "region": {"x": x, "y": y, "w": w, "h": h}})


MANIFEST = [
    {
        "name": "capture_region_ocr",
        "label": "영역 OCR",
        "schema": {
            "type": "function",
            "function": {
                "name": "capture_region_ocr",
                "description": "지정 영역만 캡처하고 OCR로 텍스트를 추출합니다. 특정 영역에 집중할 때 전체 화면 OCR보다 정확합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"},
                        "width": {"type": "integer"}, "height": {"type": "integer"}
                    },
                    "required": ["x", "y", "width", "height"]
                }
            }
        },
        "handler": lambda a: capture_region_ocr(a["x"], a["y"], a["width"], a["height"])
    },
    {
        "name": "find_image_on_screen",
        "label": "이미지 위치 탐색",
        "schema": {
            "type": "function",
            "function": {
                "name": "find_image_on_screen",
                "description": "화면에서 템플릿 이미지를 찾아 중심 좌표를 반환합니다. 버튼·아이콘 위치를 찾을 때 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_path": {"type": "string", "description": "찾을 이미지 파일 경로"},
                        "confidence": {"type": "number", "description": "매칭 정확도 임계값 0~1 (기본 0.8)"}
                    },
                    "required": ["template_path"]
                }
            }
        },
        "handler": lambda a: find_image_on_screen(a["template_path"], a.get("confidence", 0.8))
    },
    {
        "name": "find_text_location",
        "label": "텍스트 위치 탐색",
        "schema": {
            "type": "function",
            "function": {
                "name": "find_text_location",
                "description": "화면에서 특정 텍스트의 좌표를 찾습니다. 반환된 x, y로 바로 클릭할 수 있습니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "찾을 텍스트"}
                    },
                    "required": ["text"]
                }
            }
        },
        "handler": lambda a: find_text_location(a["text"])
    },
    {
        "name": "wait_for_image",
        "label": "이미지 대기",
        "schema": {
            "type": "function",
            "function": {
                "name": "wait_for_image",
                "description": "지정한 이미지가 화면에 나타날 때까지 기다립니다. 배포 완료 버튼, 로딩 화면 감지에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_path": {"type": "string"},
                        "timeout": {"type": "integer", "description": "최대 대기 초 (기본 10)"},
                        "confidence": {"type": "number"},
                        "interval": {"type": "number", "description": "폴링 간격(초), 기본 0.5"}
                    },
                    "required": ["template_path"]
                }
            }
        },
        "handler": lambda a: wait_for_image(a["template_path"], a.get("timeout", 10), a.get("confidence", 0.8), a.get("interval", 0.5))
    },
    {
        "name": "wait_for_text",
        "label": "텍스트 대기",
        "schema": {
            "type": "function",
            "function": {
                "name": "wait_for_text",
                "description": "지정한 텍스트가 화면에 나타날 때까지 기다립니다. '완료', '오류' 메시지 감지에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "timeout": {"type": "integer", "description": "최대 대기 초 (기본 10)"},
                        "interval": {"type": "number", "description": "폴링 간격(초), 기본 0.5"}
                    },
                    "required": ["text"]
                }
            }
        },
        "handler": lambda a: wait_for_text(a["text"], a.get("timeout", 10), a.get("interval", 0.5))
    },
    {
        "name": "compare_screenshots",
        "label": "스크린샷 비교",
        "schema": {
            "type": "function",
            "function": {
                "name": "compare_screenshots",
                "description": "두 스크린샷 파일을 비교하여 화면 변화를 감지합니다. 배포 전후 검증에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "before_path": {"type": "string"},
                        "after_path": {"type": "string"}
                    },
                    "required": ["before_path", "after_path"]
                }
            }
        },
        "handler": lambda a: compare_screenshots(a["before_path"], a["after_path"])
    },
    {
        "name": "save_screenshot",
        "label": "스크린샷 저장",
        "schema": {
            "type": "function",
            "function": {
                "name": "save_screenshot",
                "description": "현재 전체 화면을 이미지 파일로 저장합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "save_path": {"type": "string", "description": "저장 경로 (생략 시 임시 파일 자동 생성)"}
                    }
                }
            }
        },
        "handler": lambda a: save_screenshot(a.get("save_path", ""))
    },
    {
        "name": "get_pixel_color",
        "label": "픽셀 색상 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_pixel_color",
                "description": "지정 좌표의 픽셀 색상(RGB, HEX)을 반환합니다. 상태 표시등 색으로 정상/오류 여부를 판단할 때 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"}
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "handler": lambda a: get_pixel_color(a["x"], a["y"])
    },
    {
        "name": "capture_window_screenshot",
        "label": "창 캡처",
        "schema": {
            "type": "function",
            "function": {
                "name": "capture_window_screenshot",
                "description": "특정 창만 캡처하여 이미지 파일로 저장합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "창 제목의 일부"},
                        "save_path": {"type": "string"}
                    },
                    "required": ["title"]
                }
            }
        },
        "handler": lambda a: capture_window_screenshot(a["title"], a.get("save_path", ""))
    },
]
