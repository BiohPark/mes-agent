import json

from agent.tools.ocr      import capture_screen_ocr
from agent.tools.desktop  import (
    mouse_click, mouse_move, mouse_scroll, mouse_drag,
    mouse_down, mouse_up, get_mouse_position,
    key_press, key_down, key_up,
    type_text, type_text_clipboard,
    clipboard_get, clipboard_set,
    focus_window, list_windows, resize_window, move_window,
)
from agent.tools.screen   import (
    capture_region_ocr,
    find_image_on_screen, find_text_location,
    wait_for_image, wait_for_text,
    compare_screenshots, save_screenshot, get_pixel_color,
    capture_window_screenshot,
)
from agent.tools.browser  import (
    browser_open, browser_navigate, browser_get_url, browser_get_title,
    browser_click, browser_fill, browser_type, browser_select,
    browser_get_text, browser_get_page_text, browser_get_attribute,
    browser_wait_for, browser_wait_for_url, browser_wait_for_network_idle,
    browser_screenshot, browser_execute_js,
    browser_handle_dialog, browser_upload_file,
    browser_get_cookies, browser_close,
)
from agent.tools.process  import (
    run_command, list_processes, kill_process,
    is_process_running, start_process,
    open_file, list_directory, file_exists, get_system_info,
)
from agent.tools.document import (
    read_excel, write_excel, append_excel_row, get_excel_sheet_names,
    read_word, append_word,
    read_pdf,
    read_file, write_file,
)
from agent.obsidian_session import get_session_manager

# ─────────────────────────────────────────────────────────────
# 툴 정의 (LLM에 전달)
# ─────────────────────────────────────────────────────────────

TOOLS = [

    # ── OCR ───────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "capture_screen_ocr",
            "description": "전체 화면을 캡처하고 OCR로 텍스트를 추출합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
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

    # ── 화면 인텔리전스 ──────────────────────────────────────
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "wait_for_image",
            "description": "지정한 이미지가 화면에 나타날 때까지 기다립니다. 배포 완료 버튼, 로딩 화면 감지에 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_path": {"type": "string"},
                    "timeout": {"type": "integer", "description": "최대 대기 초 (기본 10)"},
                    "confidence": {"type": "number"}
                },
                "required": ["template_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_text",
            "description": "지정한 텍스트가 화면에 나타날 때까지 기다립니다. '완료', '오류' 메시지 감지에 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "timeout": {"type": "integer", "description": "최대 대기 초 (기본 10)"}
                },
                "required": ["text"]
            }
        }
    },
    {
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
    {
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
    {
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
    {
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

    # ── 마우스 ────────────────────────────────────────────────
    {
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
                    "use_sendinput": {"type": "boolean", "description": "UAC/관리자 앱 제어 시 true"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
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
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "get_mouse_position",
            "description": "현재 마우스 커서의 좌표를 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── 키보드 ────────────────────────────────────────────────
    {
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
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "clipboard_get",
            "description": "클립보드의 현재 텍스트 내용을 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
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

    # ── 창 관리 ───────────────────────────────────────────────
    {
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
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "현재 열려 있는 모든 창의 목록, 위치, 크기를 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
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
    {
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

    # ── 브라우저 ──────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "브라우저를 열고 URL로 이동합니다. 세션이 이미 열려있으면 재사용합니다.",
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "browser_get_title",
            "description": "현재 브라우저 페이지의 제목(title)을 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
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
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "웹 입력창에 텍스트를 채웁니다. 기존 내용을 지우고 새로 입력합니다.",
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
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "웹 입력창에 한 글자씩 타이핑합니다. 자동완성 드롭다운을 트리거해야 할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "delay": {"type": "integer", "description": "글자 간 딜레이 ms (기본 50)"}
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "browser_get_page_text",
            "description": "현재 브라우저 페이지의 전체 텍스트를 추출합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
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
    {
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
    {
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
    {
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
    {
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
    {
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
    {
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
    {
        "type": "function",
        "function": {
            "name": "browser_get_url",
            "description": "현재 브라우저의 URL을 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
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
    {
        "type": "function",
        "function": {
            "name": "browser_get_cookies",
            "description": "현재 브라우저 세션의 모든 쿠키를 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_close",
            "description": "브라우저 세션을 완전히 종료합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── 프로세스/시스템 ──────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "PowerShell 또는 CMD 명령어를 실행하고 stdout, stderr, returncode를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string"},
                    "timeout": {"type": "integer", "description": "초 (기본 30)"},
                    "shell": {"type": "string", "enum": ["powershell", "cmd"]}
                },
                "required": ["cmd"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "실행 중인 프로세스 목록을 반환합니다. name_filter로 검색 가능합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_filter": {"type": "string", "description": "프로세스 이름 검색어"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "프로세스 이름 또는 PID로 프로세스를 종료합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_pid": {"type": "string", "description": "프로세스 이름 또는 PID"}
                },
                "required": ["name_or_pid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "is_process_running",
            "description": "특정 프로세스가 실행 중인지 확인합니다.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_process",
            "description": "명령어로 프로세스를 실행합니다. wait=true 시 완료 대기합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string"},
                    "wait": {"type": "boolean"}
                },
                "required": ["cmd"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_file",
            "description": "파일을 연결된 기본 프로그램으로 엽니다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "폴더의 파일 및 하위 폴더 목록을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_exists",
            "description": "파일 또는 폴더가 존재하는지 확인합니다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "CPU, 메모리, 디스크 사용량 등 현재 시스템 상태를 반환합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },

    # ── 문서 처리 ─────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_excel_sheet_names",
            "description": "Excel 파일의 시트 이름 목록을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_excel",
            "description": "Excel 파일을 읽어 JSON 데이터로 반환합니다. 첫 행이 헤더입니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "sheet": {"description": "시트 번호(0부터) 또는 시트 이름"},
                    "max_rows": {"type": "integer", "description": "최대 행 수 (기본 200)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_excel",
            "description": "딕셔너리 리스트를 Excel 파일로 저장합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "data": {"type": "array", "items": {"type": "object"}},
                    "sheet_name": {"type": "string"}
                },
                "required": ["path", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_excel_row",
            "description": "Excel 파일의 마지막에 행을 추가합니다. 파일이 없으면 새로 생성합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "row_data": {"type": "object", "description": "헤더: 값 딕셔너리"}
                },
                "required": ["path", "row_data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_word",
            "description": "Word(.docx) 파일의 텍스트를 추출합니다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_word",
            "description": "Word 파일에 내용을 추가합니다. 파일이 없으면 새로 생성합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "text": {"type": "string"},
                    "heading": {"type": "string", "description": "섹션 제목 (선택)"}
                },
                "required": ["path", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_pdf",
            "description": "PDF 파일에서 텍스트를 추출합니다. pages 예: '1', '1-3', '2,4'",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pages": {"type": "string", "description": "페이지 범위 (생략 시 전체)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "텍스트 파일을 읽어 내용을 반환합니다. 로그, 설정 파일, CSV 등에 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "텍스트 파일에 내용을 씁니다. append=true 시 기존 내용 뒤에 추가합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "append": {"type": "boolean"}
                },
                "required": ["path", "content"]
            }
        }
    },

    # ── Obsidian 세션 ─────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "add_dev_note",
            "description": "Obsidian Vault에 개발 노트를 저장합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "related_session": {"type": "string"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_plan_item",
            "description": "Obsidian 백로그에 할 일 항목을 추가합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_sessions",
            "description": "최근 업무 세션 목록을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_sessions",
            "description": "Obsidian 세션 내용을 키워드로 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
]

# ─────────────────────────────────────────────────────────────
# 툴 레이블 (UI 표시용)
# ─────────────────────────────────────────────────────────────

TOOL_LABELS = {
    "capture_screen_ocr":        "전체 화면 OCR",
    "capture_region_ocr":        "영역 OCR",
    "find_image_on_screen":      "이미지 위치 탐색",
    "find_text_location":        "텍스트 위치 탐색",
    "wait_for_image":            "이미지 대기",
    "wait_for_text":             "텍스트 대기",
    "compare_screenshots":       "스크린샷 비교",
    "save_screenshot":           "스크린샷 저장",
    "get_pixel_color":           "픽셀 색상 확인",
    "capture_window_screenshot": "창 캡처",
    "mouse_click":               "마우스 클릭",
    "mouse_move":                "마우스 이동",
    "mouse_scroll":              "마우스 스크롤",
    "mouse_drag":                "마우스 드래그",
    "mouse_down":                "마우스 버튼 누름",
    "mouse_up":                  "마우스 버튼 해제",
    "get_mouse_position":        "마우스 위치 확인",
    "key_press":                 "키보드 입력",
    "key_down":                  "키 누름 유지",
    "key_up":                    "키 해제",
    "type_text":                 "텍스트 입력",
    "type_text_clipboard":       "클립보드 텍스트 입력",
    "clipboard_get":             "클립보드 읽기",
    "clipboard_set":             "클립보드 복사",
    "focus_window":              "창 포커스",
    "list_windows":              "창 목록 조회",
    "resize_window":             "창 크기 변경",
    "move_window":               "창 이동",
    "browser_open":              "브라우저 열기",
    "browser_navigate":          "페이지 이동",
    "browser_get_title":         "페이지 제목 확인",
    "browser_click":             "웹 요소 클릭",
    "browser_fill":              "웹 입력창 채우기",
    "browser_type":              "웹 타이핑",
    "browser_select":            "드롭다운 선택",
    "browser_get_text":          "웹 텍스트 추출",
    "browser_get_page_text":     "페이지 전체 텍스트",
    "browser_wait_for":          "웹 요소 대기",
    "browser_wait_for_url":      "URL 변경 대기",
    "browser_wait_for_network_idle": "네트워크 완료 대기",
    "browser_screenshot":        "브라우저 스크린샷",
    "browser_execute_js":        "JavaScript 실행",
    "browser_handle_dialog":     "다이얼로그 처리",
    "browser_upload_file":       "파일 업로드",
    "browser_get_url":           "현재 URL 확인",
    "browser_get_attribute":     "웹 요소 속성 조회",
    "browser_get_cookies":       "쿠키 조회",
    "browser_close":             "브라우저 종료",
    "run_command":               "명령 실행",
    "list_processes":            "프로세스 목록 조회",
    "kill_process":              "프로세스 종료",
    "is_process_running":        "프로세스 실행 확인",
    "start_process":             "프로세스 시작",
    "open_file":                 "파일 열기",
    "list_directory":            "폴더 목록 조회",
    "file_exists":               "파일 존재 확인",
    "get_system_info":           "시스템 정보 확인",
    "get_excel_sheet_names":     "Excel 시트 목록",
    "read_excel":                "Excel 읽기",
    "write_excel":               "Excel 쓰기",
    "append_excel_row":          "Excel 행 추가",
    "read_word":                 "Word 읽기",
    "append_word":               "Word 내용 추가",
    "read_pdf":                  "PDF 읽기",
    "read_file":                 "파일 읽기",
    "write_file":                "파일 쓰기",
    "add_dev_note":              "개발 노트 저장",
    "add_plan_item":             "백로그 항목 추가",
    "list_recent_sessions":      "최근 세션 조회",
    "search_sessions":           "세션 검색",
}

# ─────────────────────────────────────────────────────────────
# 툴 실행 맵
# ─────────────────────────────────────────────────────────────

_TOOL_MAP = {
    # OCR
    "capture_screen_ocr":        lambda a: capture_screen_ocr(),
    "capture_region_ocr":        lambda a: capture_region_ocr(a["x"], a["y"], a["width"], a["height"]),
    # 화면 인텔리전스
    "find_image_on_screen":      lambda a: find_image_on_screen(a["template_path"], a.get("confidence", 0.8)),
    "find_text_location":        lambda a: find_text_location(a["text"]),
    "wait_for_image":            lambda a: wait_for_image(a["template_path"], a.get("timeout", 10), a.get("confidence", 0.8)),
    "wait_for_text":             lambda a: wait_for_text(a["text"], a.get("timeout", 10)),
    "compare_screenshots":       lambda a: compare_screenshots(a["before_path"], a["after_path"]),
    "save_screenshot":           lambda a: save_screenshot(a.get("save_path", "")),
    "get_pixel_color":           lambda a: get_pixel_color(a["x"], a["y"]),
    "capture_window_screenshot": lambda a: capture_window_screenshot(a["title"], a.get("save_path", "")),
    # 마우스
    "mouse_click":               lambda a: mouse_click(a["x"], a["y"], a.get("button", "left"), a.get("clicks", 1), a.get("use_sendinput", False)),
    "mouse_move":                lambda a: mouse_move(a["x"], a["y"]),
    "mouse_scroll":              lambda a: mouse_scroll(a["x"], a["y"], a["amount"], a.get("direction", "down")),
    "mouse_drag":                lambda a: mouse_drag(a["x1"], a["y1"], a["x2"], a["y2"], a.get("duration", 0.5), a.get("button", "left")),
    "mouse_down":                lambda a: mouse_down(a["x"], a["y"], a.get("button", "left")),
    "mouse_up":                  lambda a: mouse_up(a["x"], a["y"], a.get("button", "left")),
    "get_mouse_position":        lambda a: get_mouse_position(),
    # 키보드
    "key_press":                 lambda a: key_press(a["keys"], a.get("use_sendinput", False)),
    "key_down":                  lambda a: key_down(a["key"]),
    "key_up":                    lambda a: key_up(a["key"]),
    "type_text":                 lambda a: type_text(a["text"]),
    "type_text_clipboard":       lambda a: type_text_clipboard(a["text"]),
    "clipboard_get":             lambda a: clipboard_get(),
    "clipboard_set":             lambda a: clipboard_set(a["text"]),
    # 창 관리
    "focus_window":              lambda a: focus_window(a["title"]),
    "list_windows":              lambda a: list_windows(),
    "resize_window":             lambda a: resize_window(a["title"], a["width"], a["height"]),
    "move_window":               lambda a: move_window(a["title"], a["x"], a["y"]),
    # 브라우저
    "browser_open":              lambda a: browser_open(a["url"], a.get("headless", False)),
    "browser_navigate":          lambda a: browser_navigate(a["url"]),
    "browser_get_title":         lambda a: browser_get_title(),
    "browser_click":             lambda a: browser_click(a["selector"], a.get("timeout", 5000)),
    "browser_fill":              lambda a: browser_fill(a["selector"], a["text"], a.get("timeout", 5000)),
    "browser_type":              lambda a: browser_type(a["selector"], a["text"], a.get("delay", 50)),
    "browser_select":            lambda a: browser_select(a["selector"], a["value"], a.get("timeout", 5000)),
    "browser_get_text":          lambda a: browser_get_text(a["selector"], a.get("timeout", 5000)),
    "browser_get_page_text":     lambda a: browser_get_page_text(),
    "browser_get_attribute":     lambda a: browser_get_attribute(a["selector"], a["attribute"], a.get("timeout", 5000)),
    "browser_wait_for":          lambda a: browser_wait_for(a["selector"], a.get("state", "visible"), a.get("timeout", 10000)),
    "browser_wait_for_url":      lambda a: browser_wait_for_url(a["pattern"], a.get("timeout", 10000)),
    "browser_wait_for_network_idle": lambda a: browser_wait_for_network_idle(a.get("timeout", 10000)),
    "browser_screenshot":        lambda a: browser_screenshot(a.get("save_path", "")),
    "browser_execute_js":        lambda a: browser_execute_js(a["script"]),
    "browser_handle_dialog":     lambda a: browser_handle_dialog(a.get("action", "accept"), a.get("prompt_text", "")),
    "browser_upload_file":       lambda a: browser_upload_file(a["selector"], a["file_path"]),
    "browser_get_url":           lambda a: browser_get_url(),
    "browser_get_cookies":       lambda a: browser_get_cookies(),
    "browser_close":             lambda a: browser_close(),
    # 프로세스/시스템
    "run_command":               lambda a: run_command(a["cmd"], a.get("timeout", 30), a.get("shell", "powershell")),
    "list_processes":            lambda a: list_processes(a.get("name_filter", "")),
    "kill_process":              lambda a: kill_process(a["name_or_pid"]),
    "is_process_running":        lambda a: is_process_running(a["name"]),
    "start_process":             lambda a: start_process(a["cmd"], a.get("wait", False)),
    "open_file":                 lambda a: open_file(a["path"]),
    "list_directory":            lambda a: list_directory(a["path"]),
    "file_exists":               lambda a: file_exists(a["path"]),
    "get_system_info":           lambda a: get_system_info(),
    # 문서
    "read_excel":                lambda a: read_excel(a["path"], a.get("sheet", 0), a.get("max_rows", 200)),
    "write_excel":               lambda a: write_excel(a["path"], a["data"], a.get("sheet_name", "Sheet1")),
    "append_excel_row":          lambda a: append_excel_row(a["path"], a["row_data"], a.get("sheet", 0)),
    "get_excel_sheet_names":     lambda a: get_excel_sheet_names(a["path"]),
    "read_word":                 lambda a: read_word(a["path"]),
    "append_word":               lambda a: append_word(a["path"], a["text"], a.get("heading", "")),
    "read_pdf":                  lambda a: read_pdf(a["path"], a.get("pages", "")),
    "read_file":                 lambda a: read_file(a["path"]),
    "write_file":                lambda a: write_file(a["path"], a["content"], a.get("append", False)),
    # Obsidian
    "add_dev_note":              lambda a: get_session_manager().add_note(a["title"], a["content"], a.get("tags", []), a.get("related_session", "")),
    "add_plan_item":             lambda a: get_session_manager().add_plan_item(a["title"], a.get("description", "")),
    "list_recent_sessions":      lambda a: get_session_manager().list_recent_sessions(a.get("limit", 5)),
    "search_sessions":           lambda a: get_session_manager().search_sessions(a["query"]),
}


def run_tool(name: str, arguments: str) -> str:
    args = json.loads(arguments) if arguments.strip() else {}
    if name not in _TOOL_MAP:
        raise ValueError(f"알 수 없는 툴: {name}")
    return _TOOL_MAP[name](args)
