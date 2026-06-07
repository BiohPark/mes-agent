"""
데스크탑 입력 제어 도구
- 기본: pyautogui (일반 앱)
- 정밀: pywin32 SendInput (UAC/관리자 권한 앱)
- 클립보드: pyperclip (한글·특수문자 안정 입력)
- 키 홀드: pynput (key_down/key_up 분리)
"""

import time
import json
import ctypes
import ctypes.wintypes

import pyautogui
import pyperclip
import pygetwindow as gw
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

_kb = KeyboardController()
_mouse_ctrl = MouseController()

# ── SendInput 상수 ────────────────────────────────────────────

INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004
KEYEVENTF_SCANCODE    = 0x0008
MOUSEEVENTF_MOVE      = 0x0001
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_ABSOLUTE  = 0x8000

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT_UNION)]

_VK_MAP = {
    "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
    "lctrl": 0xA2, "rctrl": 0xA3, "lshift": 0xA0, "rshift": 0xA1,
    "lalt": 0xA4, "ralt": 0xA5,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
}


def _sendinput_key(vk: int, key_up: bool = False):
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp._input.ki.wVk = vk
    inp._input.ki.dwFlags = KEYEVENTF_KEYUP if key_up else 0
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _screen_size():
    return ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)


def _sendinput_click(x: int, y: int, button: str = "left"):
    sw, sh = _screen_size()
    norm_x = int(x * 65535 / sw)
    norm_y = int(y * 65535 / sh)
    down_flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
    up_flag   = MOUSEEVENTF_LEFTUP   if button == "left" else MOUSEEVENTF_RIGHTUP

    move_inp = _INPUT(type=INPUT_MOUSE)
    move_inp._input.mi.dx = norm_x
    move_inp._input.mi.dy = norm_y
    move_inp._input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE

    down_inp = _INPUT(type=INPUT_MOUSE)
    down_inp._input.mi.dwFlags = down_flag

    up_inp = _INPUT(type=INPUT_MOUSE)
    up_inp._input.mi.dwFlags = up_flag

    inputs = (_INPUT * 3)(move_inp, down_inp, up_inp)
    ctypes.windll.user32.SendInput(3, inputs, ctypes.sizeof(_INPUT))


# ── 기본 마우스 ───────────────────────────────────────────────

def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1,
                use_sendinput: bool = False, after_delay_ms: int = 0) -> str:
    """화면의 특정 좌표를 마우스로 클릭합니다.
    use_sendinput=True 시 UAC/관리자 권한 앱에서도 동작합니다.
    after_delay_ms: 클릭 후 안정화 대기(ms). 팝업·화면 전환이 느린 경우 사용합니다."""
    if use_sendinput:
        for _ in range(clicks):
            _sendinput_click(x, y, button)
            time.sleep(0.05)
        if after_delay_ms > 0:
            time.sleep(after_delay_ms / 1000)
        return f"SendInput ({x}, {y}) {button} 클릭 완료"
    pyautogui.click(x, y, button=button, clicks=clicks)
    if after_delay_ms > 0:
        time.sleep(after_delay_ms / 1000)
    return f"({x}, {y}) {button} 클릭 완료"


def mouse_move(x: int, y: int) -> str:
    """마우스를 특정 좌표로 이동합니다."""
    pyautogui.moveTo(x, y, duration=0.2)
    return f"마우스 이동: ({x}, {y})"


def mouse_scroll(x: int, y: int, amount: int, direction: str = "down") -> str:
    """지정 좌표에서 마우스 휠을 스크롤합니다.
    direction은 'up' 또는 'down', amount는 스크롤 칸 수입니다."""
    pyautogui.moveTo(x, y, duration=0.1)
    scroll_amount = -amount if direction == "down" else amount
    pyautogui.scroll(scroll_amount)
    return f"({x}, {y}) {direction} 스크롤 {amount}칸"


def mouse_drag(x1: int, y1: int, x2: int, y2: int,
               duration: float = 0.5, button: str = "left") -> str:
    """마우스 버튼을 누른 채 드래그합니다. 파일 이동, 선택 영역 지정에 사용합니다."""
    pyautogui.moveTo(x1, y1, duration=0.1)
    pyautogui.dragTo(x2, y2, duration=duration, button=button)
    return f"드래그 완료: ({x1},{y1}) → ({x2},{y2})"


def mouse_down(x: int, y: int, button: str = "left") -> str:
    """마우스 버튼을 누른 상태로 유지합니다 (mouse_up으로 해제)."""
    pyautogui.moveTo(x, y, duration=0.1)
    pyautogui.mouseDown(button=button)
    return f"마우스 {button} 버튼 누름 ({x},{y})"


def mouse_up(x: int, y: int, button: str = "left") -> str:
    """눌려있는 마우스 버튼을 해제합니다."""
    pyautogui.mouseUp(x=x, y=y, button=button)
    return f"마우스 {button} 버튼 해제 ({x},{y})"


def get_mouse_position() -> str:
    """현재 마우스 커서의 좌표를 반환합니다."""
    x, y = pyautogui.position()
    return f"현재 마우스 위치: ({x}, {y})"


# ── 키보드 ────────────────────────────────────────────────────

def key_press(keys: str, use_sendinput: bool = False) -> str:
    """키보드 단축키 또는 단일 키를 누릅니다. 예: 'enter', 'ctrl+c', 'alt+F4'.
    use_sendinput=True 시 UAC 앱에서도 동작합니다."""
    parts = [k.strip().lower() for k in keys.split("+")]
    if use_sendinput:
        vks = [_VK_MAP.get(p) for p in parts]
        if None in vks:
            missing = parts[[i for i, v in enumerate(vks) if v is None][0]]
            return f"SendInput: 지원하지 않는 키 '{missing}'"
        for vk in vks:
            _sendinput_key(vk, key_up=False)
        for vk in reversed(vks):
            _sendinput_key(vk, key_up=True)
        return f"SendInput 키 입력: {keys}"
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)
    return f"키 입력: {keys}"


def key_down(key: str) -> str:
    """키를 누른 상태로 유지합니다 (key_up으로 해제). Shift+클릭 등 복합 조작에 사용합니다."""
    _pynput_key = _to_pynput_key(key)
    _kb.press(_pynput_key)
    return f"키 누름 유지: {key}"


def key_up(key: str) -> str:
    """key_down으로 누른 키를 해제합니다."""
    _pynput_key = _to_pynput_key(key)
    _kb.release(_pynput_key)
    return f"키 해제: {key}"


def _to_pynput_key(key: str):
    special = {
        "ctrl": Key.ctrl, "shift": Key.shift, "alt": Key.alt,
        "enter": Key.enter, "tab": Key.tab, "esc": Key.esc, "escape": Key.esc,
        "backspace": Key.backspace, "delete": Key.delete, "space": Key.space,
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "home": Key.home, "end": Key.end,
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
        "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
    }
    k = key.lower().strip()
    return special.get(k, k)


# ── 텍스트 입력 ───────────────────────────────────────────────

def type_text(text: str, interval: float = 0.03) -> str:
    """현재 포커스된 입력창에 텍스트를 입력합니다. 영문/숫자에 적합합니다."""
    pyautogui.write(text, interval=interval)
    return f"텍스트 입력 완료: {text[:50]}{'...' if len(text) > 50 else ''}"


def type_text_clipboard(text: str) -> str:
    """클립보드를 경유하여 텍스트를 입력합니다.
    한글, 특수문자, 긴 텍스트를 안정적으로 입력할 때 사용합니다."""
    prev = pyperclip.paste()
    pyperclip.copy(text)
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.1)
    try:
        pyperclip.copy(prev)
    except Exception:
        pass
    return f"클립보드 입력 완료: {text[:50]}{'...' if len(text) > 50 else ''}"


# ── 클립보드 ─────────────────────────────────────────────────

def clipboard_get() -> str:
    """클립보드의 현재 텍스트를 반환합니다."""
    text = pyperclip.paste()
    return text if text else "(클립보드 비어있음)"


def clipboard_set(text: str) -> str:
    """클립보드에 텍스트를 복사합니다."""
    pyperclip.copy(text)
    return f"클립보드 복사 완료: {text[:80]}{'...' if len(text) > 80 else ''}"


# ── 창 관리 ──────────────────────────────────────────────────

def focus_window(title: str) -> str:
    """제목에 title이 포함된 창을 찾아 포커스합니다."""
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    if not matches:
        available = [w.title for w in gw.getAllWindows() if w.title][:10]
        return f"창을 찾지 못했습니다: '{title}'\n현재 열린 창: {available}"
    win = matches[0]
    try:
        win.activate()
    except Exception:
        win.minimize()
        time.sleep(0.2)
        win.restore()
    time.sleep(0.3)
    return f"창 포커스: {win.title}"


def list_windows() -> str:
    """현재 열려 있는 모든 창의 목록과 위치/크기를 반환합니다."""
    windows = []
    for w in gw.getAllWindows():
        if not w.title:
            continue
        windows.append({
            "title": w.title,
            "x": w.left, "y": w.top,
            "width": w.width, "height": w.height,
            "visible": w.visible
        })
    return json.dumps(windows, ensure_ascii=False)


def resize_window(title: str, width: int, height: int) -> str:
    """창의 크기를 변경합니다."""
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    if not matches:
        return f"창을 찾지 못했습니다: '{title}'"
    win = matches[0]
    win.resizeTo(width, height)
    return f"창 크기 변경: {win.title} → {width}x{height}"


def move_window(title: str, x: int, y: int) -> str:
    """창의 위치를 변경합니다."""
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    if not matches:
        return f"창을 찾지 못했습니다: '{title}'"
    win = matches[0]
    win.moveTo(x, y)
    return f"창 이동: {win.title} → ({x}, {y})"


def maximize_window(title: str) -> str:
    """창을 OS 수준으로 최대화합니다."""
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    if not matches:
        available = [w.title for w in gw.getAllWindows() if w.title][:8]
        return json.dumps({"error": f"창을 찾지 못했습니다: '{title}'", "available": available})
    win = matches[0]
    try:
        win.maximize()
        return json.dumps({"maximized": win.title})
    except Exception as e:
        return json.dumps({"error": str(e), "title": win.title})


MANIFEST = [
    # ── 마우스 ────────────────────────────────────────────────
    {
        "name": "mouse_click",
        "label": "마우스 클릭",
        "schema": {
            "type": "function",
            "function": {
                "name": "mouse_click",
                "description": "화면의 특정 좌표를 마우스로 클릭합니다. use_sendinput=true 시 관리자 권한 앱에서도 동작합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"},
                        "button": {"type": "string", "enum": ["left", "right", "middle"]},
                        "clicks": {"type": "integer", "description": "1=단일, 2=더블클릭"},
                        "use_sendinput": {"type": "boolean", "description": "UAC/관리자 앱 제어 시 true"},
                        "after_delay_ms": {"type": "integer", "description": "클릭 후 안정화 대기(ms), 기본 0"}
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "handler": lambda a: mouse_click(a["x"], a["y"], a.get("button", "left"), a.get("clicks", 1), a.get("use_sendinput", False), a.get("after_delay_ms", 0))
    },
    {
        "name": "mouse_move",
        "label": "마우스 이동",
        "schema": {
            "type": "function",
            "function": {
                "name": "mouse_move",
                "description": "마우스를 특정 좌표로 이동합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"}
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "handler": lambda a: mouse_move(a["x"], a["y"])
    },
    {
        "name": "mouse_scroll",
        "label": "마우스 스크롤",
        "schema": {
            "type": "function",
            "function": {
                "name": "mouse_scroll",
                "description": "지정 좌표에서 마우스 휠을 스크롤합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"},
                        "amount": {"type": "integer", "description": "스크롤 칸 수"},
                        "direction": {"type": "string", "enum": ["up", "down"]}
                    },
                    "required": ["x", "y", "amount"]
                }
            }
        },
        "handler": lambda a: mouse_scroll(a["x"], a["y"], a["amount"], a.get("direction", "down"))
    },
    {
        "name": "mouse_drag",
        "label": "마우스 드래그",
        "schema": {
            "type": "function",
            "function": {
                "name": "mouse_drag",
                "description": "마우스 드래그 앤 드롭을 수행합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x1": {"type": "integer"}, "y1": {"type": "integer"},
                        "x2": {"type": "integer"}, "y2": {"type": "integer"},
                        "duration": {"type": "number", "description": "드래그 소요 시간(초)"},
                        "button": {"type": "string", "enum": ["left", "right"]}
                    },
                    "required": ["x1", "y1", "x2", "y2"]
                }
            }
        },
        "handler": lambda a: mouse_drag(a["x1"], a["y1"], a["x2"], a["y2"], a.get("duration", 0.5), a.get("button", "left"))
    },
    {
        "name": "mouse_down",
        "label": "마우스 버튼 누름",
        "schema": {
            "type": "function",
            "function": {
                "name": "mouse_down",
                "description": "마우스 버튼을 누른 상태로 유지합니다. mouse_up으로 해제합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"},
                        "button": {"type": "string", "enum": ["left", "right", "middle"]}
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "handler": lambda a: mouse_down(a["x"], a["y"], a.get("button", "left"))
    },
    {
        "name": "mouse_up",
        "label": "마우스 버튼 해제",
        "schema": {
            "type": "function",
            "function": {
                "name": "mouse_up",
                "description": "mouse_down으로 누른 마우스 버튼을 해제합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"}, "y": {"type": "integer"},
                        "button": {"type": "string", "enum": ["left", "right", "middle"]}
                    },
                    "required": ["x", "y"]
                }
            }
        },
        "handler": lambda a: mouse_up(a["x"], a["y"], a.get("button", "left"))
    },
    {
        "name": "get_mouse_position",
        "label": "마우스 위치 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_mouse_position",
                "description": "현재 마우스 커서의 좌표를 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: get_mouse_position()
    },
    # ── 키보드 ────────────────────────────────────────────────
    {
        "name": "key_press",
        "label": "키보드 입력",
        "schema": {
            "type": "function",
            "function": {
                "name": "key_press",
                "description": "키보드 단축키 또는 단일 키를 누릅니다. 예: 'enter', 'ctrl+c', 'alt+F4'. use_sendinput=true 시 UAC 앱에서도 동작합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keys": {"type": "string"},
                        "use_sendinput": {"type": "boolean"}
                    },
                    "required": ["keys"]
                }
            }
        },
        "handler": lambda a: key_press(a["keys"], a.get("use_sendinput", False))
    },
    {
        "name": "key_down",
        "label": "키 누름 유지",
        "schema": {
            "type": "function",
            "function": {
                "name": "key_down",
                "description": "키를 누른 상태로 유지합니다. key_up으로 해제하기 전까지 눌린 상태입니다. Shift+클릭 등 복합 조작에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"]
                }
            }
        },
        "handler": lambda a: key_down(a["key"])
    },
    {
        "name": "key_up",
        "label": "키 해제",
        "schema": {
            "type": "function",
            "function": {
                "name": "key_up",
                "description": "key_down으로 누른 키를 해제합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"]
                }
            }
        },
        "handler": lambda a: key_up(a["key"])
    },
    {
        "name": "type_text",
        "label": "텍스트 입력",
        "schema": {
            "type": "function",
            "function": {
                "name": "type_text",
                "description": "포커스된 입력창에 텍스트를 입력합니다. 영문/숫자에 적합합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"]
                }
            }
        },
        "handler": lambda a: type_text(a["text"])
    },
    {
        "name": "type_text_clipboard",
        "label": "클립보드 텍스트 입력",
        "schema": {
            "type": "function",
            "function": {
                "name": "type_text_clipboard",
                "description": "클립보드를 경유하여 텍스트를 입력합니다. 한글, 특수문자, 긴 텍스트를 안정적으로 입력할 때 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"]
                }
            }
        },
        "handler": lambda a: type_text_clipboard(a["text"])
    },
    {
        "name": "clipboard_get",
        "label": "클립보드 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "clipboard_get",
                "description": "클립보드의 현재 텍스트 내용을 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: clipboard_get()
    },
    {
        "name": "clipboard_set",
        "label": "클립보드 복사",
        "schema": {
            "type": "function",
            "function": {
                "name": "clipboard_set",
                "description": "클립보드에 텍스트를 복사합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"]
                }
            }
        },
        "handler": lambda a: clipboard_set(a["text"])
    },
    # ── 창 관리 ───────────────────────────────────────────────
    {
        "name": "focus_window",
        "label": "창 포커스",
        "schema": {
            "type": "function",
            "function": {
                "name": "focus_window",
                "description": "제목에 특정 문자열이 포함된 창을 찾아 포커스합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"]
                }
            }
        },
        "handler": lambda a: focus_window(a["title"])
    },
    {
        "name": "list_windows",
        "label": "창 목록 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "list_windows",
                "description": "현재 열려 있는 모든 창의 목록, 위치, 크기를 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: list_windows()
    },
    {
        "name": "resize_window",
        "label": "창 크기 변경",
        "schema": {
            "type": "function",
            "function": {
                "name": "resize_window",
                "description": "창의 크기를 변경합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"}
                    },
                    "required": ["title", "width", "height"]
                }
            }
        },
        "handler": lambda a: resize_window(a["title"], a["width"], a["height"])
    },
    {
        "name": "move_window",
        "label": "창 이동",
        "schema": {
            "type": "function",
            "function": {
                "name": "move_window",
                "description": "창의 위치를 변경합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "x": {"type": "integer"},
                        "y": {"type": "integer"}
                    },
                    "required": ["title", "x", "y"]
                }
            }
        },
        "handler": lambda a: move_window(a["title"], a["x"], a["y"])
    },
    {
        "name": "maximize_window",
        "label": "창 최대화",
        "schema": {
            "type": "function",
            "function": {
                "name": "maximize_window",
                "description": "창을 OS 수준으로 최대화합니다. resize_window 대신 이 툴을 사용하세요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "창 제목 일부 (부분 일치)"}
                    },
                    "required": ["title"]
                }
            }
        },
        "handler": lambda a: maximize_window(a["title"])
    },
]
