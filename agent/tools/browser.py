"""
브라우저 자동화 도구 (Playwright sync API)
- 인트라넷 웹 앱 자동화: 로그인, 폼 입력, 데이터 수집
- 싱글턴 세션으로 브라우저 상태 유지
"""

import json
import tempfile
import os
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, Page, Playwright

# ── 싱글턴 세션 ───────────────────────────────────────────────

_pw: Optional[Playwright] = None
_browser: Optional[Browser] = None
_page: Optional[Page] = None

# ── 전용 단일 스레드 ──────────────────────────────────────────
# Playwright sync API 객체(greenlet)는 자신을 생성한 스레드에만 묶인다.
# 서버는 매 툴 호출을 기본 ThreadPool의 임의 워커 스레드에서 실행하므로,
# 브라우저 작업을 항상 동일한 단일 스레드로 보내지 않으면
# "Cannot switch to a different thread" 오류가 발생한다.
# 모든 공개 핸들러를 이 executor에 위임해 한 스레드에서만 Playwright를 다룬다.
_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")


def _on_pw_thread(fn):
    """핸들러를 전용 Playwright 스레드에서 실행하고 결과를 동기적으로 반환한다."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return _pw_executor.submit(fn, *args, **kwargs).result()
    return wrapper


# ── 포커스 비탈취 (백로그 I) ──────────────────────────────────
# 브라우저를 열거나 페이지를 이동하면 OS가 브라우저 창을 자동 전면화해 사용자 작업을
# 가로챈다. 작업 직전 사용자의 foreground 창을 기억했다가 작업 후 복원한다.
# BROWSER_FOCUS_STEAL=true 거나 bring_to_front=True면 복원하지 않는다(기존 동작).

def _focus_steal_allowed(bring_to_front=None) -> bool:
    if bring_to_front is True:
        return True
    if bring_to_front is False:
        return False
    return os.environ.get("BROWSER_FOCUS_STEAL", "false").lower() in ("1", "true", "yes")


def _capture_foreground():
    """현재 foreground 창 핸들을 반환한다(win32 불가 시 None)."""
    try:
        import win32gui
        return win32gui.GetForegroundWindow()
    except Exception:
        return None


def _restore_foreground(hwnd) -> None:
    """기억해 둔 사용자 창을 다시 전면화한다(win32 제약 우회: AttachThreadInput)."""
    if not hwnd:
        return
    try:
        import win32gui
        import win32process
        if not win32gui.IsWindow(hwnd):
            return
        cur = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
        tgt = win32process.GetWindowThreadProcessId(hwnd)[0]
        attached = False
        try:
            if cur and tgt and cur != tgt:
                win32process.AttachThreadInput(cur, tgt, True)
                attached = True
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                win32process.AttachThreadInput(cur, tgt, False)
    except Exception:
        pass  # 포커스 복원은 best-effort — 실패해도 작업은 계속


def _preserve_focus(bring_to_front, fn):
    """fn 실행 동안 사용자 포커스를 보존한다. steal 허용 시 그대로 실행."""
    if _focus_steal_allowed(bring_to_front):
        return fn()
    prev = _capture_foreground()
    try:
        return fn()
    finally:
        _restore_foreground(prev)


def _get_page(headless: bool = False) -> Page:
    global _pw, _browser, _page
    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = sync_playwright().start()
            # BROWSER_CHANNEL=msedge 로 실제 Edge를 구동(사내 SSO·Office Online 호환 ↑)
            _channel = os.environ.get("BROWSER_CHANNEL", "").strip()
            _launch_kwargs = dict(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            if _channel:
                _launch_kwargs["channel"] = _channel
            _browser = _pw.chromium.launch(**_launch_kwargs)
        context = _browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        _page = context.new_page()
    return _page


def _safe_call(fn):
    try:
        return fn()
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── 공개 툴 ───────────────────────────────────────────────────

def browser_open(url: str, headless: bool = False, bring_to_front: bool = None) -> str:
    """브라우저를 열고 지정한 URL로 이동합니다.
    headless=True 시 화면 없이 백그라운드로 실행됩니다.
    기본은 사용자 작업 포커스를 빼앗지 않습니다(창을 열되 전면화하지 않음).
    bring_to_front=True면 브라우저를 전면으로 가져옵니다(키보드 조작이 필요할 때)."""
    def _do():
        page = _get_page(headless)
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return json.dumps({"url": page.url, "title": page.title(),
                           "message": f"페이지 로드 완료: {page.title()}"})
    return _preserve_focus(bring_to_front, _do)


def _resolve_doc_url(url: str) -> str:
    """절대 URL이면 그대로, 상대경로면 .env의 SHAREPOINT_BASE_URL 기준으로 합성한다."""
    u = (url or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    base = os.environ.get("SHAREPOINT_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/{u.lstrip('/')}"
    return u  # 베이스 미설정 — 그대로 두면 goto가 명확히 실패


def office_web_open(url: str, timeout: int = 60000) -> str:
    """Office Online(SharePoint/OneDrive/365) 문서를 브라우저로 열고 편집 화면이
    뜰 때까지 기다린 뒤 스크린샷을 저장합니다(클라우드 문서 편집의 진입점).
    url이 상대경로면 .env의 SHAREPOINT_BASE_URL을 앞에 붙입니다.
    이후 편집은 키보드 단축키(Ctrl+H 찾아바꾸기, Ctrl+S 저장)와 UI Automation/OCR로 진행하세요.
    환경변수 BROWSER_CHANNEL=msedge 로 실제 Edge에서 열 수 있습니다(사내 SSO 호환)."""
    resolved = _resolve_doc_url(url)
    if not (resolved.startswith("http://") or resolved.startswith("https://")):
        return json.dumps({
            "error": "절대 URL이 아니고 SHAREPOINT_BASE_URL도 설정돼 있지 않습니다. "
                     ".env에 SHAREPOINT_BASE_URL을 넣거나 전체 URL을 전달하세요.",
            "given": url,
        }, ensure_ascii=False)

    def _do():
        page = _get_page()
        page.goto(resolved, wait_until="load", timeout=timeout)
        try:
            page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass  # Office Online은 지속 연결로 networkidle이 안 올 수 있음 — 무시

        # 편집기 종류·상태 진단 (프레임 URL/제목 기반)
        frame_urls = " ".join((f.url or "") for f in page.frames).lower()
        title_l = (page.title() or "").lower()
        blob = frame_urls + " " + title_l
        detected = "unknown"
        for key, name in (("excel", "Excel Online"), ("word", "Word Online"),
                          ("powerpoint", "PowerPoint Online"), ("/we/", "Word Online"),
                          ("/xe/", "Excel Online"), ("/pe/", "PowerPoint Online")):
            if key in blob:
                detected = name
                break
        # 편집 모드 단서: action=edit / wopi edit frame
        looks_editable = ("action=edit" in frame_urls or "edit.aspx" in frame_urls
                          or "wopi" in frame_urls or "office" in frame_urls)

        fd, shot = tempfile.mkstemp(suffix=".png", prefix="office_web_")
        os.close(fd)
        try:
            page.screenshot(path=shot, full_page=False)
        except Exception:
            shot = ""

        return json.dumps({
            "url": page.url,
            "title": page.title(),
            "screenshot": shot,
            "frames": len(page.frames),
            "detected_editor": detected,
            "looks_editable": looks_editable,
            # ── 솔직한 한계 고지 ─────────────────────────────────────
            "known_limitation": (
                "Office Online 편집 화면은 iframe + 캔버스 렌더라 DOM selector로 셀/문단을 직접 "
                "클릭·입력하기 어렵습니다. browser_click 류는 대부분 실패합니다. 이게 웹 편집의 약점입니다."
            ),
            # ── 권장 폴백 순서(에이전트가 따라야 할 사다리) ──────────
            "recommended_next": [
                "1) office_locate_file로 같은 문서의 동기화/로컬 사본을 먼저 찾아라. 있으면 word_edit_text/excel_set_cells(COM)로 편집(가장 정확).",
                "2) M365면 graph_find_item→graph_excel_set_range(Excel)로 REST 편집을 시도하라.",
                "3) 위가 불가하면 이 브라우저 창에서 키보드로 편집: 문서에 포커스 후 Ctrl+H(찾아바꾸기)·타이핑, Ctrl+S(자동저장이면 불필요).",
                "4) 클릭 좌표가 필요하면 analyze_screen/ui_inspect_window로 위치를 먼저 확인하라(스크린샷·OCR).",
                "5) 그래도 막히면 무엇을 시도했고 왜 막혔는지(편집기 종류·로그인·권한 등) 사용자에게 명확히 보고하라.",
            ],
        }, ensure_ascii=False)
    return _safe_call(_do)


def browser_navigate(url: str, bring_to_front: bool = None) -> str:
    """현재 브라우저 탭에서 다른 URL로 이동합니다.
    기본은 사용자 작업 포커스를 빼앗지 않습니다."""
    def _do():
        page = _get_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return json.dumps({"url": page.url, "title": page.title()})
    return _preserve_focus(bring_to_front, _do)


def browser_get_url() -> str:
    """현재 페이지의 URL을 반환합니다."""
    return _get_page().url


def browser_get_title() -> str:
    """현재 페이지의 제목을 반환합니다."""
    return _get_page().title()


def browser_click(selector: str, timeout: int = 5000) -> str:
    """CSS selector 또는 XPath로 요소를 찾아 클릭합니다.
    예: '#submit-btn', 'button:has-text(\"로그인\")', '//input[@type=\"submit\"]'"""
    def _do():
        page = _get_page()
        page.click(selector, timeout=timeout)
        return json.dumps({"clicked": selector, "url": page.url})
    return _safe_call(_do)


def browser_fill(selector: str, text: str, timeout: int = 5000) -> str:
    """입력창에 텍스트를 채웁니다. 기존 내용을 지우고 새로 입력합니다."""
    def _do():
        _get_page().fill(selector, text, timeout=timeout)
        return json.dumps({"filled": selector, "text": text[:50]})
    return _safe_call(_do)


def browser_type(selector: str, text: str, delay: int = 50, timeout: int = 5000) -> str:
    """입력창에 한 글자씩 타이핑합니다. 자동완성이 필요한 입력창에 사용합니다."""
    def _do():
        page = _get_page()
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        page.type(selector, text, delay=delay)
        return json.dumps({"typed": selector, "text": text[:50]})
    return _safe_call(_do)


def browser_select(selector: str, value: str, timeout: int = 5000) -> str:
    """드롭다운(select) 요소에서 값을 선택합니다."""
    def _do():
        _get_page().select_option(selector, value=value, timeout=timeout)
        return json.dumps({"selected": selector, "value": value})
    return _safe_call(_do)


def browser_get_text(selector: str, timeout: int = 5000) -> str:
    """지정한 요소의 텍스트를 추출합니다."""
    def _do():
        text = _get_page().text_content(selector, timeout=timeout)
        return text or "(텍스트 없음)"
    return _safe_call(_do)


def browser_get_page_text() -> str:
    """현재 페이지의 전체 텍스트를 추출합니다 (태그 제외)."""
    def _do():
        text = _get_page().evaluate("() => document.body.innerText")
        lines = [l.strip() for l in str(text).splitlines() if l.strip()]
        return "\n".join(lines[:200])
    return _safe_call(_do)


def browser_get_attribute(selector: str, attribute: str, timeout: int = 5000) -> str:
    """지정한 요소의 속성값을 반환합니다. 예: href, value, class"""
    def _do():
        val = _get_page().get_attribute(selector, attribute, timeout=timeout)
        return val or "(속성 없음)"
    return _safe_call(_do)


def browser_wait_for(selector: str, state: str = "visible", timeout: int = 10000) -> str:
    """지정한 요소가 나타나거나 특정 상태가 될 때까지 기다립니다.
    state: 'visible', 'hidden', 'attached', 'detached'"""
    def _do():
        _get_page().wait_for_selector(selector, state=state, timeout=timeout)
        return json.dumps({"found": True, "selector": selector, "state": state})
    result = _safe_call(_do)
    if isinstance(result, str) and "error" in result.lower():
        return json.dumps({"found": False, "selector": selector, "timeout": timeout})
    return result


def browser_wait_for_url(pattern: str, timeout: int = 10000) -> str:
    """URL이 지정한 패턴(부분 문자열)을 포함할 때까지 기다립니다."""
    def _do():
        _get_page().wait_for_url(f"**{pattern}**", timeout=timeout)
        return json.dumps({"matched": True, "url": _get_page().url})
    result = _safe_call(_do)
    if isinstance(result, str) and "error" in result.lower():
        return json.dumps({"matched": False, "pattern": pattern, "timeout": timeout})
    return result


def browser_wait_for_network_idle(timeout: int = 10000) -> str:
    """네트워크 요청이 완전히 멈출 때까지 기다립니다. Ajax 로딩 완료 감지에 유용합니다."""
    def _do():
        _get_page().wait_for_load_state("networkidle", timeout=timeout)
        return json.dumps({"idle": True, "url": _get_page().url})
    return _safe_call(_do)


def browser_screenshot(save_path: str = "") -> str:
    """현재 페이지 전체의 스크린샷을 저장합니다."""
    if not save_path:
        fd, save_path = tempfile.mkstemp(suffix=".png", prefix="browser_")
        os.close(fd)
    def _do():
        _get_page().screenshot(path=save_path, full_page=True)
        return json.dumps({"path": save_path, "message": f"브라우저 스크린샷: {save_path}"})
    return _safe_call(_do)


def browser_execute_js(script: str) -> str:
    """페이지에서 JavaScript를 직접 실행하고 결과를 반환합니다."""
    def _do():
        result = _get_page().evaluate(script)
        return json.dumps({"result": str(result)[:500]})
    return _safe_call(_do)


def browser_handle_dialog(action: str = "accept", prompt_text: str = "") -> str:
    """다음 alert/confirm/prompt 다이얼로그를 자동 처리합니다.
    action: 'accept'(확인) 또는 'dismiss'(취소)"""
    page = _get_page()
    def handler(dialog):
        if action == "accept":
            dialog.accept(prompt_text)
        else:
            dialog.dismiss()
    page.once("dialog", handler)
    return json.dumps({"registered": True, "action": action,
                       "message": f"다음 다이얼로그를 '{action}'으로 처리 등록"})


def browser_upload_file(selector: str, file_path: str) -> str:
    """파일 업로드 input에 파일을 지정합니다."""
    def _do():
        _get_page().set_input_files(selector, file_path)
        return json.dumps({"uploaded": file_path, "selector": selector})
    return _safe_call(_do)


def browser_get_cookies() -> str:
    """현재 세션의 모든 쿠키를 반환합니다."""
    def _do():
        cookies = _get_page().context.cookies()
        return json.dumps(cookies, ensure_ascii=False)
    return _safe_call(_do)


def browser_get_interactive_elements() -> str:
    """현재 페이지의 입력창·버튼·링크 목록을 반환합니다. 올바른 selector 파악에 사용합니다."""
    def _do():
        page = _get_page()
        result = page.evaluate("""() => {
            const visible = el => el.offsetWidth > 0 && el.offsetHeight > 0;
            const trim = s => (s || '').trim().slice(0, 40);
            const cls = el => (el.className || '').split(' ').filter(Boolean).slice(0, 3).join('.');
            const items = [];
            document.querySelectorAll('input, textarea, select').forEach(el => {
                if (!visible(el)) return;
                items.push({
                    kind: 'input',
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    id: el.id || '',
                    name: el.name || '',
                    placeholder: trim(el.placeholder),
                    ariaLabel: trim(el.getAttribute('aria-label')),
                    class: cls(el),
                });
            });
            document.querySelectorAll('button, [role="button"], [type="submit"]').forEach(el => {
                if (!visible(el)) return;
                items.push({
                    kind: 'button',
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    text: trim(el.innerText),
                    ariaLabel: trim(el.getAttribute('aria-label')),
                    class: cls(el),
                });
            });
            return items.slice(0, 40);
        }""")
        return json.dumps(result, ensure_ascii=False)
    return _safe_call(_do)


def browser_press_key(key: str, selector: str = "") -> str:
    """키를 누릅니다. selector 지정 시 해당 요소에, 없으면 페이지 전체에 전송합니다.
    예: key='Enter', 'Tab', 'Escape', 'ArrowDown', 'Control+a'"""
    def _do():
        page = _get_page()
        if selector:
            page.press(selector, key)
        else:
            page.keyboard.press(key)
        return json.dumps({"key_pressed": key, "target": selector or "page"})
    return _safe_call(_do)


def browser_close() -> str:
    """브라우저 세션을 닫습니다."""
    global _pw, _browser, _page
    try:
        if _page and not _page.is_closed():
            _page.close()
        if _browser and _browser.is_connected():
            _browser.close()
        if _pw:
            _pw.stop()
    except Exception:
        pass
    _pw = _browser = _page = None
    return "브라우저 종료 완료"


MANIFEST = [
    {
        "name": "browser_open",
        "label": "브라우저 열기",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_open",
                "description": (
                    "브라우저를 열고 URL로 이동합니다. 세션이 이미 열려있으면 재사용합니다. "
                    "페이지 로드 후 browser_get_interactive_elements로 입력창·버튼 selector를 확인하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "headless": {"type": "boolean", "description": "true=화면 없이 실행"},
                        "bring_to_front": {"type": "boolean", "description": "true=브라우저를 전면화(키보드 조작 필요 시). 기본은 사용자 포커스 비탈취"}
                    },
                    "required": ["url"]
                }
            }
        },
        "handler": lambda a: browser_open(a["url"], a.get("headless", False), a.get("bring_to_front"))
    },
    {
        "name": "browser_navigate",
        "label": "페이지 이동",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_navigate",
                "description": "현재 브라우저 탭에서 다른 URL로 이동합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"]
                }
            }
        },
        "handler": lambda a: browser_navigate(a["url"])
    },
    {
        "name": "browser_get_url",
        "label": "현재 URL 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_url",
                "description": "현재 브라우저의 URL을 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: browser_get_url()
    },
    {
        "name": "browser_get_title",
        "label": "페이지 제목 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_title",
                "description": "현재 브라우저 페이지의 제목(title)을 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: browser_get_title()
    },
    {
        "name": "browser_click",
        "label": "웹 요소 클릭",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_click",
                "description": "CSS selector 또는 XPath로 웹 요소를 찾아 클릭합니다. 예: '#btn-submit', 'button:has-text(\"확인\")'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "timeout": {"type": "integer", "description": "밀리초 (기본 5000)"}
                    },
                    "required": ["selector"]
                }
            }
        },
        "handler": lambda a: browser_click(a["selector"], a.get("timeout", 5000))
    },
    {
        "name": "browser_fill",
        "label": "웹 입력창 채우기",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_fill",
                "description": (
                    "웹 입력창에 텍스트를 채웁니다. 기존 내용을 지우고 새로 입력합니다. "
                    "폼 제출은 이 툴로 입력 후 browser_press_key('Enter')를 사용하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "text": {"type": "string"},
                        "timeout": {"type": "integer"}
                    },
                    "required": ["selector", "text"]
                }
            }
        },
        "handler": lambda a: browser_fill(a["selector"], a["text"], a.get("timeout", 5000))
    },
    {
        "name": "browser_type",
        "label": "웹 타이핑",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_type",
                "description": (
                    "웹 입력창에 한 글자씩 타이핑합니다. 자동완성 드롭다운을 트리거해야 할 때 사용합니다. "
                    "selector를 모를 경우 먼저 browser_get_interactive_elements로 확인하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "text": {"type": "string"},
                        "delay": {"type": "integer", "description": "글자 간 딜레이 ms (기본 50)"},
                        "timeout": {"type": "integer", "description": "요소 대기 최대 ms (기본 5000)"}
                    },
                    "required": ["selector", "text"]
                }
            }
        },
        "handler": lambda a: browser_type(a["selector"], a["text"], a.get("delay", 50), a.get("timeout", 5000))
    },
    {
        "name": "browser_get_interactive_elements",
        "label": "페이지 인터랙티브 요소 목록",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_interactive_elements",
                "description": (
                    "현재 페이지의 보이는 입력창·버튼·선택박스 목록(id, name, ariaLabel, text 등)을 반환합니다. "
                    "browser_open 후 어떤 selector를 써야 할지 모를 때 먼저 호출하세요."
                ),
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: browser_get_interactive_elements()
    },
    {
        "name": "browser_press_key",
        "label": "키 입력",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_press_key",
                "description": (
                    "브라우저 페이지 또는 특정 요소에 키를 전송합니다. "
                    "예: 'Enter'(폼 제출), 'Tab'(다음 필드), 'Escape', 'ArrowDown'. "
                    "폼 제출 시 browser_fill → browser_press_key('Enter') 패턴을 사용하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key":      {"type": "string", "description": "전송할 키 이름 (예: 'Enter', 'Tab', 'Escape')"},
                        "selector": {"type": "string", "description": "대상 요소 selector. 생략 시 페이지 전체에 전송."}
                    },
                    "required": ["key"]
                }
            }
        },
        "handler": lambda a: browser_press_key(a["key"], a.get("selector", ""))
    },
    {
        "name": "browser_select",
        "label": "드롭다운 선택",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_select",
                "description": "드롭다운에서 값을 선택합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "value": {"type": "string"}
                    },
                    "required": ["selector", "value"]
                }
            }
        },
        "handler": lambda a: browser_select(a["selector"], a["value"], a.get("timeout", 5000))
    },
    {
        "name": "browser_get_text",
        "label": "웹 텍스트 추출",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_text",
                "description": "지정한 웹 요소의 텍스트를 추출합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "timeout": {"type": "integer"}
                    },
                    "required": ["selector"]
                }
            }
        },
        "handler": lambda a: browser_get_text(a["selector"], a.get("timeout", 5000))
    },
    {
        "name": "browser_get_page_text",
        "label": "페이지 전체 텍스트",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_page_text",
                "description": "현재 브라우저 페이지의 전체 텍스트를 추출합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: browser_get_page_text()
    },
    {
        "name": "browser_get_attribute",
        "label": "웹 요소 속성 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_attribute",
                "description": "웹 요소의 속성값을 반환합니다. 예: href, value, class, data-id",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "attribute": {"type": "string"},
                        "timeout": {"type": "integer"}
                    },
                    "required": ["selector", "attribute"]
                }
            }
        },
        "handler": lambda a: browser_get_attribute(a["selector"], a["attribute"], a.get("timeout", 5000))
    },
    {
        "name": "browser_wait_for",
        "label": "웹 요소 대기",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_wait_for",
                "description": "웹 요소가 나타나거나 특정 상태가 될 때까지 기다립니다. state: visible/hidden/attached/detached",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "state": {"type": "string", "enum": ["visible", "hidden", "attached", "detached"]},
                        "timeout": {"type": "integer", "description": "밀리초 (기본 10000)"}
                    },
                    "required": ["selector"]
                }
            }
        },
        "handler": lambda a: browser_wait_for(a["selector"], a.get("state", "visible"), a.get("timeout", 10000))
    },
    {
        "name": "browser_wait_for_url",
        "label": "URL 변경 대기",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_wait_for_url",
                "description": "브라우저 URL이 지정한 패턴을 포함할 때까지 기다립니다. 페이지 이동 완료 감지에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "timeout": {"type": "integer"}
                    },
                    "required": ["pattern"]
                }
            }
        },
        "handler": lambda a: browser_wait_for_url(a["pattern"], a.get("timeout", 10000))
    },
    {
        "name": "browser_wait_for_network_idle",
        "label": "네트워크 완료 대기",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_wait_for_network_idle",
                "description": "페이지의 모든 네트워크 요청이 완료될 때까지 기다립니다. Ajax 로딩 완료 감지에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timeout": {"type": "integer"}
                    }
                }
            }
        },
        "handler": lambda a: browser_wait_for_network_idle(a.get("timeout", 10000))
    },
    {
        "name": "browser_screenshot",
        "label": "브라우저 스크린샷",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_screenshot",
                "description": "현재 브라우저 페이지 전체의 스크린샷을 저장합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "save_path": {"type": "string", "description": "저장 경로 (생략 시 임시 파일)"}
                    }
                }
            }
        },
        "handler": lambda a: browser_screenshot(a.get("save_path", ""))
    },
    {
        "name": "browser_execute_js",
        "label": "JavaScript 실행",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_execute_js",
                "description": "현재 페이지에서 JavaScript를 실행하고 결과를 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"script": {"type": "string"}},
                    "required": ["script"]
                }
            }
        },
        "handler": lambda a: browser_execute_js(a["script"])
    },
    {
        "name": "browser_handle_dialog",
        "label": "다이얼로그 처리",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_handle_dialog",
                "description": "다음에 발생할 alert/confirm/prompt 다이얼로그를 자동 처리합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["accept", "dismiss"]},
                        "prompt_text": {"type": "string", "description": "prompt 입력값"}
                    }
                }
            }
        },
        "handler": lambda a: browser_handle_dialog(a.get("action", "accept"), a.get("prompt_text", ""))
    },
    {
        "name": "browser_upload_file",
        "label": "파일 업로드",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_upload_file",
                "description": "파일 업로드 input 요소에 파일을 지정합니다. <input type='file'> 요소에 사용합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "파일 input 요소의 CSS selector"},
                        "file_path": {"type": "string", "description": "업로드할 파일의 절대 경로"}
                    },
                    "required": ["selector", "file_path"]
                }
            }
        },
        "handler": lambda a: browser_upload_file(a["selector"], a["file_path"])
    },
    {
        "name": "browser_get_cookies",
        "label": "쿠키 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_get_cookies",
                "description": "현재 브라우저 세션의 모든 쿠키를 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: browser_get_cookies()
    },
    {
        "name": "browser_close",
        "label": "브라우저 종료",
        "schema": {
            "type": "function",
            "function": {
                "name": "browser_close",
                "description": "브라우저 세션을 완전히 종료합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: browser_close()
    },
    {
        "name": "office_web_open",
        "label": "Office Online 열기",
        "schema": {
            "type": "function",
            "function": {
                "name": "office_web_open",
                "description": (
                    "Office Online(SharePoint/OneDrive/365) 문서를 브라우저로 열고 편집기 종류·편집가능 여부를 "
                    "진단해 스크린샷과 함께 반환합니다. ⚠ 웹 편집기는 iframe+캔버스라 selector 클릭이 거의 안 되는 "
                    "약점이 있어, 반환되는 recommended_next(로컬사본 COM→Graph→키보드→보고) 순서를 따르세요. "
                    "★ 로컬/동기화 파일은 office_locate_file+word_edit_text(COM)가 가장 정확합니다. "
                    "BROWSER_CHANNEL=msedge 로 실제 Edge에서 열 수 있습니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Office Online 문서 URL"},
                        "timeout": {"type": "integer", "description": "ms (기본 60000)"},
                    },
                    "required": ["url"],
                },
            },
        },
        "handler": lambda a: office_web_open(a["url"], a.get("timeout", 60000)),
    },
]

# 모든 브라우저 핸들러를 전용 Playwright 스레드로 위임해 greenlet 스레드 충돌을 방지한다.
for _tool in MANIFEST:
    _tool["handler"] = _on_pw_thread(_tool["handler"])
