"""
Windows UI Automation 도구 — 접근성 API로 화면 요소 구조적 읽기
pywin32 (win32gui, win32con) 사용 — requirements.txt에 이미 포함
OCR/비전 없이도 Win32 표준 컨트롤(버튼·입력창·목록)의 텍스트·레이블·값을 직접 읽을 수 있음
"""

import json


def _win32gui():
    try:
        import win32gui
        return win32gui
    except ImportError:
        return None


def ui_list_windows(visible_only: bool = True) -> str:
    """현재 열려있는 모든 창의 목록을 반환합니다.
    제목이 있는 창만 포함됩니다."""
    wg = _win32gui()
    if wg is None:
        return json.dumps({"error": "pywin32가 설치되어 있지 않습니다. pip install pywin32"})
    try:
        windows = []

        def cb(hwnd, _):
            if visible_only and not wg.IsWindowVisible(hwnd):
                return
            title = wg.GetWindowText(hwnd)
            if title:
                windows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "class": wg.GetClassName(hwnd)
                })

        wg.EnumWindows(cb, None)
        return json.dumps({"windows": windows, "count": len(windows)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def ui_inspect_window(title_contains: str, max_controls: int = 80) -> str:
    """창의 모든 컨트롤(버튼·입력창·레이블 등)을 열거하여 접근성 구조를 반환합니다.
    title_contains: 창 제목의 일부 (대소문자 무관)."""
    wg = _win32gui()
    if wg is None:
        return json.dumps({"error": "pywin32가 설치되어 있지 않습니다."})
    try:
        hwnd = _find_window(wg, title_contains)
        if not hwnd:
            return json.dumps({"error": f"창을 찾을 수 없습니다: '{title_contains}'"})

        controls = []

        def cb(h, _):
            if len(controls) >= max_controls:
                return
            text = wg.GetWindowText(h)
            cls = wg.GetClassName(h)
            controls.append({
                "hwnd": h,
                "text": text,
                "class": cls,
                "visible": bool(wg.IsWindowVisible(h))
            })

        wg.EnumChildWindows(hwnd, cb, None)
        return json.dumps({
            "window": wg.GetWindowText(hwnd),
            "hwnd": hwnd,
            "controls": controls,
            "count": len(controls)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def ui_find_and_read(title_contains: str, text_contains: str = "") -> str:
    """창에서 특정 텍스트를 포함하는 컨트롤을 찾아 반환합니다.
    text_contains를 생략하면 텍스트가 있는 모든 컨트롤을 반환합니다."""
    wg = _win32gui()
    if wg is None:
        return json.dumps({"error": "pywin32가 설치되어 있지 않습니다."})
    try:
        hwnd = _find_window(wg, title_contains)
        if not hwnd:
            return json.dumps({"error": f"창을 찾을 수 없습니다: '{title_contains}'"})

        found = []

        def cb(h, _):
            text = wg.GetWindowText(h)
            if not text:
                return
            if text_contains and text_contains.lower() not in text.lower():
                return
            found.append({
                "hwnd": h,
                "text": text,
                "class": wg.GetClassName(h),
                "visible": bool(wg.IsWindowVisible(h))
            })

        wg.EnumChildWindows(hwnd, cb, None)
        return json.dumps({"found": found, "count": len(found)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _find_window(wg, title_contains: str) -> int | None:
    found = [None]

    def cb(hwnd, _):
        if found[0]:
            return
        if title_contains.lower() in wg.GetWindowText(hwnd).lower() and wg.IsWindowVisible(hwnd):
            found[0] = hwnd

    wg.EnumWindows(cb, None)
    return found[0]


MANIFEST = [
    {
        "name": "ui_list_windows",
        "label": "창 목록",
        "schema": {
            "type": "function",
            "function": {
                "name": "ui_list_windows",
                "description": (
                    "현재 열려있는 모든 창의 목록을 반환합니다. "
                    "창 제목·클래스명·HWND를 포함합니다. "
                    "대상 창을 찾기 위한 첫 번째 단계로 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "visible_only": {
                            "type": "boolean",
                            "description": "보이는 창만 반환 (기본 true)"
                        }
                    },
                    "required": []
                }
            }
        },
        "handler": lambda a: ui_list_windows(a.get("visible_only", True))
    },
    {
        "name": "ui_inspect_window",
        "label": "창 컨트롤 구조 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "ui_inspect_window",
                "description": (
                    "창의 모든 컨트롤(버튼·입력창·레이블·목록 등)을 열거합니다. "
                    "OCR 없이 Win32 표준 컨트롤의 텍스트·클래스를 구조적으로 읽을 수 있습니다. "
                    "SAP·MES 같은 표준 Win32 앱 화면 이해에 특히 효과적입니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title_contains": {
                            "type": "string",
                            "description": "창 제목의 일부 (대소문자 무관). ui_list_windows로 먼저 확인하세요."
                        },
                        "max_controls": {
                            "type": "integer",
                            "description": "최대 컨트롤 수 (기본 80)"
                        }
                    },
                    "required": ["title_contains"]
                }
            }
        },
        "handler": lambda a: ui_inspect_window(a["title_contains"], a.get("max_controls", 80))
    },
    {
        "name": "ui_find_and_read",
        "label": "창 컨트롤 검색",
        "schema": {
            "type": "function",
            "function": {
                "name": "ui_find_and_read",
                "description": (
                    "창에서 특정 텍스트를 포함하는 컨트롤을 찾아 반환합니다. "
                    "특정 버튼·레이블·입력값을 빠르게 찾을 때 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title_contains": {
                            "type": "string",
                            "description": "창 제목의 일부"
                        },
                        "text_contains": {
                            "type": "string",
                            "description": "찾을 텍스트 (생략 시 모든 컨트롤 반환)"
                        }
                    },
                    "required": ["title_contains"]
                }
            }
        },
        "handler": lambda a: ui_find_and_read(a["title_contains"], a.get("text_contains", ""))
    },
]
