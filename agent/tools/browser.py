"""
브라우저 자동화 도구 (Playwright sync API)
- 인트라넷 웹 앱 자동화: 로그인, 폼 입력, 데이터 수집
- 싱글턴 세션으로 브라우저 상태 유지
"""

import json
import tempfile
import os
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, Page, Playwright

# ── 싱글턴 세션 ───────────────────────────────────────────────

_pw: Optional[Playwright] = None
_browser: Optional[Browser] = None
_page: Optional[Page] = None


def _get_page(headless: bool = False) -> Page:
    global _pw, _browser, _page
    if _page is None or _page.is_closed():
        if _browser is None or not _browser.is_connected():
            if _pw is None:
                _pw = sync_playwright().start()
            _browser = _pw.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
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

def browser_open(url: str, headless: bool = False) -> str:
    """브라우저를 열고 지정한 URL로 이동합니다.
    headless=True 시 화면 없이 백그라운드로 실행됩니다."""
    page = _get_page(headless)
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    return json.dumps({"url": page.url, "title": page.title(),
                       "message": f"페이지 로드 완료: {page.title()}"})


def browser_navigate(url: str) -> str:
    """현재 브라우저 탭에서 다른 URL로 이동합니다."""
    page = _get_page()
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    return json.dumps({"url": page.url, "title": page.title()})


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


def browser_type(selector: str, text: str, delay: int = 50) -> str:
    """입력창에 한 글자씩 타이핑합니다. 자동완성이 필요한 입력창에 사용합니다."""
    def _do():
        _get_page().type(selector, text, delay=delay)
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
