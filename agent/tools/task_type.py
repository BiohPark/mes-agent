import json
import re

from agent.obsidian_session import (
    _DEFAULT_TASK_CONFIGS,
    _load_vault_task_configs,
    _save_vault_task_configs,
    get_task_configs,
)


_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        return "업무 타입 이름이 필요합니다"
    if not _NAME_RE.fullmatch(value):
        return "업무 타입 이름은 영문, 숫자, _, -만 사용할 수 있습니다"
    return ""


def _task_type_create(args: dict) -> str:
    name = (args.get("name") or "").strip()
    error = _validate_name(name)
    if error:
        return json.dumps({"status": "error", "reason": error}, ensure_ascii=False)
    if name in get_task_configs():
        return json.dumps({"status": "error", "reason": "이미 존재하는 업무 타입입니다"}, ensure_ascii=False)

    custom = _load_vault_task_configs()
    custom[name] = {
        "label": args.get("label") or name,
        "icon": args.get("icon") or "🧩",
        "description": args.get("description", ""),
        "system_prompt": args.get("system_prompt", ""),
    }
    _save_vault_task_configs(custom)
    return json.dumps({"status": "ok", "name": name}, ensure_ascii=False)


def _task_type_remove(args: dict) -> str:
    name = (args.get("name") or "").strip()
    error = _validate_name(name)
    if error:
        return json.dumps({"status": "error", "reason": error}, ensure_ascii=False)
    if name in _DEFAULT_TASK_CONFIGS:
        return json.dumps({"status": "error", "reason": "기본 업무 타입은 삭제할 수 없습니다"}, ensure_ascii=False)

    custom = _load_vault_task_configs()
    if name not in custom:
        return json.dumps({"status": "error", "reason": "존재하지 않는 업무 타입입니다"}, ensure_ascii=False)
    del custom[name]
    _save_vault_task_configs(custom)
    return json.dumps({"status": "ok", "name": name}, ensure_ascii=False)


MANIFEST = [
    {
        "name": "task_type_create",
        "label": "업무 타입 추가",
        "_risk": "mutate",
        "schema": {
            "type": "function",
            "function": {
                "name": "task_type_create",
                "description": "Vault에 사용자 정의 업무 타입을 추가합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "업무 타입 키. 영문, 숫자, _, -만 허용"},
                        "label": {"type": "string", "description": "사이드바에 표시할 이름"},
                        "icon": {"type": "string", "description": "사이드바에 표시할 아이콘"},
                        "description": {"type": "string", "description": "업무 타입 설명"},
                        "system_prompt": {"type": "string", "description": "이 업무 타입의 시스템 프롬프트"},
                    },
                    "required": ["name", "label", "icon", "description", "system_prompt"],
                },
            },
        },
        "handler": _task_type_create,
    },
    {
        "name": "task_type_remove",
        "label": "업무 타입 삭제",
        "_risk": "mutate",
        "schema": {
            "type": "function",
            "function": {
                "name": "task_type_remove",
                "description": "Vault의 사용자 정의 업무 타입을 삭제합니다. 기본 업무 타입은 삭제할 수 없습니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "삭제할 사용자 정의 업무 타입 키"},
                    },
                    "required": ["name"],
                },
            },
        },
        "handler": _task_type_remove,
    },
]
