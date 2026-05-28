"""
툴 레지스트리 — 자동 디스커버리 방식

새 툴을 추가하려면:
  1. agent/tools/ 안에 파이썬 파일 생성
  2. 파일 끝에 MANIFEST 리스트 정의
     (name, label, schema, handler 키 필수)
  3. 끝. __init__.py 수정 불필요.
"""

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
        _registry[tool["name"]] = tool

for tool in getattr(_obs, "MANIFEST", []):
    _registry[tool["name"]] = tool

# ── 공개 인터페이스 ───────────────────────────────────────────

TOOLS = [t["schema"] for t in _registry.values()]
TOOL_LABELS = {name: t["label"] for name, t in _registry.items()}


def run_tool(name: str, arguments: str) -> str:
    args = json.loads(arguments) if arguments.strip() else {}
    if name not in _registry:
        raise ValueError(f"알 수 없는 툴: {name}")
    return _registry[name]["handler"](args)
