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
                        "headless": {"type": "boolean", "description": "true=화면 없이 실행"}
                    },
                    "required": ["url"]
                }
            }
        },
        "handler": lambda a: browser_open(a["url"], a.get("headless", False))
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
]
