import pyautogui
import pygetwindow as gw
import time

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    pyautogui.click(x, y, button=button, clicks=clicks)
    return f"({x}, {y}) {button} 클릭 완료"


def mouse_move(x: int, y: int) -> str:
    pyautogui.moveTo(x, y, duration=0.2)
    return f"마우스 이동: ({x}, {y})"


def type_text(text: str, interval: float = 0.03) -> str:
    pyautogui.write(text, interval=interval)
    return f"텍스트 입력 완료: {text[:50]}{'...' if len(text) > 50 else ''}"


def key_press(keys: str) -> str:
    """keys 예시: 'enter', 'ctrl+c', 'alt+F4', 'ctrl+shift+esc'"""
    parts = [k.strip() for k in keys.lower().split("+")]
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)
    return f"키 입력: {keys}"


def focus_window(title: str) -> str:
    """제목에 title이 포함된 창을 찾아 포커스"""
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    if not matches:
        available = [w.title for w in gw.getAllWindows() if w.title][:10]
        return f"창을 찾지 못했습니다: '{title}'\n현재 열린 창: {available}"
    win = matches[0]
    win.activate()
    time.sleep(0.3)
    return f"창 포커스: {win.title}"


def get_mouse_position() -> str:
    x, y = pyautogui.position()
    return f"현재 마우스 위치: ({x}, {y})"
