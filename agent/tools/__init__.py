import json
from agent.tools.ocr import capture_screen_ocr
from agent.tools.desktop import mouse_click, mouse_move, type_text, key_press, focus_window, get_mouse_position
from agent.obsidian_session import get_session_manager

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "capture_screen_ocr",
            "description": "현재 화면 전체를 캡처하고 텍스트를 OCR로 추출합니다.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "화면의 특정 좌표를 마우스로 클릭합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 좌표"},
                    "y": {"type": "integer", "description": "Y 좌표"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "마우스 버튼 (기본: left)"},
                    "clicks": {"type": "integer", "description": "클릭 횟수 (기본: 1, 더블클릭은 2)"}
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
                    "x": {"type": "integer", "description": "X 좌표"},
                    "y": {"type": "integer", "description": "Y 좌표"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "현재 포커스된 입력창에 텍스트를 입력합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "입력할 텍스트"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "key_press",
            "description": "키보드 단축키 또는 단일 키를 누릅니다. 예: 'enter', 'ctrl+c', 'alt+F4'",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "키 이름 또는 '+' 로 연결한 단축키"}
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "제목에 특정 문자열이 포함된 창을 찾아 포커스합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "찾을 창 제목의 일부"}
                },
                "required": ["title"]
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
    {
        "type": "function",
        "function": {
            "name": "add_dev_note",
            "description": "Obsidian Vault에 개발 노트를 저장합니다. 업무 중 발견한 인사이트, 버그 수정 내용, 설계 결정을 기록할 때 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "노트 제목"},
                    "content": {"type": "string", "description": "노트 내용 (마크다운 가능)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "태그 목록 (선택)"},
                    "related_session": {"type": "string", "description": "관련 세션 ID (선택)"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_plan_item",
            "description": "Obsidian 백로그(plans/backlog.md)에 할 일 항목을 추가합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "할 일 제목"},
                    "description": {"type": "string", "description": "상세 설명 (선택)"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_sessions",
            "description": "Obsidian에 저장된 최근 업무 세션 목록을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "반환할 세션 수 (기본: 5)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_sessions",
            "description": "Obsidian에 저장된 세션 내용을 키워드로 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색 키워드"}
                },
                "required": ["query"]
            }
        }
    }
]

TOOL_LABELS = {
    "capture_screen_ocr": "화면 캡처 및 OCR 처리",
    "mouse_click": "마우스 클릭",
    "mouse_move": "마우스 이동",
    "type_text": "텍스트 입력",
    "key_press": "키보드 입력",
    "focus_window": "창 포커스",
    "get_mouse_position": "마우스 위치 확인",
    "add_dev_note": "개발 노트 저장",
    "add_plan_item": "백로그 항목 추가",
    "list_recent_sessions": "최근 세션 조회",
    "search_sessions": "세션 검색",
}

_TOOL_MAP = {
    "capture_screen_ocr": lambda args: capture_screen_ocr(),
    "mouse_click":        lambda args: mouse_click(args["x"], args["y"], args.get("button", "left"), args.get("clicks", 1)),
    "mouse_move":         lambda args: mouse_move(args["x"], args["y"]),
    "type_text":          lambda args: type_text(args["text"]),
    "key_press":          lambda args: key_press(args["keys"]),
    "focus_window":       lambda args: focus_window(args["title"]),
    "get_mouse_position": lambda args: get_mouse_position(),
    "add_dev_note":        lambda args: get_session_manager().add_note(
        args["title"], args["content"], args.get("tags", []), args.get("related_session", "")
    ),
    "add_plan_item":       lambda args: get_session_manager().add_plan_item(
        args["title"], args.get("description", "")
    ),
    "list_recent_sessions": lambda args: get_session_manager().list_recent_sessions(
        args.get("limit", 5)
    ),
    "search_sessions":     lambda args: get_session_manager().search_sessions(args["query"]),
}

def run_tool(name: str, arguments: str) -> str:
    args = json.loads(arguments) if arguments.strip() else {}
    if name not in _TOOL_MAP:
        raise ValueError(f"알 수 없는 툴: {name}")
    return _TOOL_MAP[name](args)
