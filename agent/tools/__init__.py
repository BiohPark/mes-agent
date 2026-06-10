"""
툴 레지스트리 — 자동 디스커버리 방식

새 툴을 추가하려면:
  1. agent/tools/ 안에 파이썬 파일 생성
  2. 파일 끝에 MANIFEST 리스트 정의
     (name, label, schema, handler 키 필수)
  3. 끝. __init__.py 수정 불필요.

요청당 도구 전송: LLM API(OpenAI 호환)는 tools 배열을 최대 128개로 제한한다.
등록 도구가 그보다 많으면 select_tools()가 task_type·메시지 관련도로 ≤한도 만큼만 추린다.
"""

import os
import re
import json
import importlib
import pkgutil

import agent.tools as _pkg
from agent import obsidian_session as _obs

# ── 자동 디스커버리 ───────────────────────────────────────────

_registry: dict = {}

for _info in pkgutil.iter_modules(_pkg.__path__):
    if _info.name.startswith("_"):
        continue
    _mod = importlib.import_module(f"agent.tools.{_info.name}")
    for tool in getattr(_mod, "MANIFEST", []):
        tool["_module"] = _info.name
        _registry[tool["name"]] = tool

for tool in getattr(_obs, "MANIFEST", []):
    tool["_module"] = "obsidian_session"
    _registry[tool["name"]] = tool

# ── 공개 인터페이스 ───────────────────────────────────────────

TOOLS = [t["schema"] for t in _registry.values()]
TOOL_LABELS = {name: t["label"] for name, t in _registry.items()}


def run_tool(name: str, arguments: str) -> str:
    args = json.loads(arguments) if arguments.strip() else {}
    if name not in _registry:
        raise ValueError(f"알 수 없는 툴: {name}")
    return _registry[name]["handler"](args)


# ── 요청당 도구 서브셋 선택 (128 한계 대응) ─────────────────────

# OpenAI 호환 API의 tools 배열 최대 길이
LLM_MAX_TOOLS = int(os.environ.get("LLM_MAX_TOOLS", "128"))

# 모듈 우선순위(core → optional). 앞일수록 먼저 채워진다.
# 미등록(미래 MCP 등) 모듈은 _UNKNOWN_RANK로 core 끝쯤에 배치해 기본 포함되게 한다.
_MODULE_PRIORITY = [
    "ocr", "interaction", "memory_tools", "workflow", "vision",
    "screen", "desktop", "browser", "process", "document",
    "obsidian_rag", "obsidian_session",
    # ← 미등록 모듈은 여기(_UNKNOWN_RANK)에 들어간다
    "ui_automation", "office_com", "office_libre", "office_cloud",
]
_UNKNOWN_RANK = 12  # obsidian_session(11) 직후, ui_automation(12) 앞
_RELEVANCE_BOOST = 100  # 관련 모듈을 우선순위 앞으로 당기는 폭
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1}


def _module_rank(module: str) -> int:
    try:
        i = _MODULE_PRIORITY.index(module)
        # 미등록 모듈 자리(_UNKNOWN_RANK) 이후는 한 칸씩 밀어 자리 확보
        return i if i < _UNKNOWN_RANK else i + 1
    except ValueError:
        return _UNKNOWN_RANK


def _module_text(tools: list) -> str:
    parts = []
    for t in tools:
        fn = t.get("schema", {}).get("function", {})
        parts.append(t.get("name", ""))
        parts.append(t.get("label", ""))
        parts.append(fn.get("description", ""))
    return " ".join(parts)


def select_tools(message: str = "", task_type: str = "", limit: int = LLM_MAX_TOOLS) -> list[dict]:
    """요청에 보낼 도구 스키마를 한도(limit) 이하로 추린다.

    - 등록 수가 한도 이하면 전체(TOOLS)를 그대로 반환.
    - 모듈 우선순위(core 먼저) + 메시지/task_type 관련도 부스트로 정렬한 뒤,
      모듈 단위로 예산이 허용하는 만큼 그리디하게 담는다(부분 모듈 없음).
    """
    if len(TOOLS) <= limit:
        return TOOLS

    # 모듈별 그룹화(등록 순서 보존)
    groups: dict[str, list] = {}
    for t in _registry.values():
        groups.setdefault(t.get("_module", ""), []).append(t)

    query = _tokens(f"{message} {task_type}")

    def sort_key(module: str):
        rank = _module_rank(module)
        matched = bool(query & _tokens(_module_text(groups[module]))) if query else False
        return (rank - (_RELEVANCE_BOOST if matched else 0), rank, module)

    selected: list[dict] = []
    for module in sorted(groups, key=sort_key):
        schemas = [t["schema"] for t in groups[module]]
        if len(selected) + len(schemas) <= limit:
            selected.extend(schemas)
    return selected
