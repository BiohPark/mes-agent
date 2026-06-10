"""명시적 장기기억 도구 — 사용자가 "이거 기억해 / 잊어"라고 하면 에이전트가 직접 호출.

자동 추출(server `_extract_memories`)과 달리 사용자 의도를 즉시 반영한다.
`MemoryStore`(memory.py)를 그대로 재사용 — 같은 노트(`<vault>/agent/memory/long_term.md`)에 저장.
"""

import json
import os

from agent.memory import MemoryStore

_VALID_CATEGORIES = ("fact", "preference", "decision")


def _store() -> MemoryStore:
    return MemoryStore(os.environ.get("OBSIDIAN_VAULT_PATH", "."))


def memory_remember(text: str, category: str = "fact") -> str:
    """사용자가 명시적으로 요청한 내용을 장기기억에 저장한다."""
    text = (text or "").strip()
    if not text:
        return json.dumps({"ok": False, "error": "기억할 내용이 비어 있습니다."}, ensure_ascii=False)
    cat = category if category in _VALID_CATEGORIES else "fact"
    mem = _store().add(text, cat, source="user")
    if mem is None:
        return json.dumps(
            {"ok": True, "saved": False, "reason": "이미 비슷한 기억이 있습니다(중복)."},
            ensure_ascii=False,
        )
    return json.dumps(
        {"ok": True, "saved": True, "id": mem.id, "text": mem.text, "category": mem.category},
        ensure_ascii=False,
    )


def memory_forget(query: str) -> str:
    """질의(내용 키워드 또는 기억 id)에 가장 잘 맞는 기억 1건을 삭제한다."""
    q = (query or "").strip()
    if not q:
        return json.dumps({"ok": False, "error": "삭제할 기억을 지정하세요."}, ensure_ascii=False)
    store = _store()
    # 1) id 직접 지정 지원(관리 UI/에이전트가 id를 알 때)
    for m in store.all():
        if m.id == q:
            store.delete(q)
            return json.dumps({"ok": True, "deleted": True, "id": m.id, "text": m.text}, ensure_ascii=False)
    # 2) 키워드 최선 매칭 1건
    hits = store.search(q, 1)
    if not hits:
        return json.dumps(
            {"ok": True, "deleted": False, "reason": "일치하는 기억이 없습니다."}, ensure_ascii=False
        )
    target = hits[0]
    ok = store.delete(target.id)
    return json.dumps({"ok": True, "deleted": ok, "id": target.id, "text": target.text}, ensure_ascii=False)


def memory_recall(query: str, k: int = 5) -> str:
    """대화 도중 질의와 관련된 장기기억을 능동적으로 회수한다(시작 시 자동 주입 외 추가 조회)."""
    try:
        k = int(k)
    except (TypeError, ValueError):
        k = 5
    hits = _store().search(query or "", max(1, k))
    return json.dumps({"ok": True, "memories": [m.to_dict() for m in hits]}, ensure_ascii=False)


MANIFEST = [
    {
        "name": "memory_remember",
        "label": "기억 저장",
        "schema": {
            "type": "function",
            "function": {
                "name": "memory_remember",
                "description": (
                    "사용자가 '이거 기억해' 같은 요청을 하면 그 내용을 대화를 넘는 장기기억에 저장한다. "
                    "지속적 사실·선호·결정만 저장하라(일시적 내용 제외)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "기억할 내용(한 문장)"},
                        "category": {
                            "type": "string",
                            "enum": list(_VALID_CATEGORIES),
                            "description": "분류: fact(사실)·preference(선호)·decision(결정)",
                        },
                    },
                    "required": ["text"],
                },
            },
        },
        "handler": lambda a: memory_remember(a.get("text", ""), a.get("category", "fact")),
    },
    {
        "name": "memory_forget",
        "label": "기억 삭제",
        "schema": {
            "type": "function",
            "function": {
                "name": "memory_forget",
                "description": (
                    "사용자가 '이거 잊어/기억 지워' 라고 하면 해당 기억을 삭제한다. "
                    "query에 잊을 내용의 키워드(또는 기억 id)를 넣으면 가장 잘 맞는 1건을 지운다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "삭제할 기억의 내용 키워드 또는 id"}
                    },
                    "required": ["query"],
                },
            },
        },
        "handler": lambda a: memory_forget(a.get("query", "")),
    },
    {
        "name": "memory_recall",
        "label": "기억 회수",
        "schema": {
            "type": "function",
            "function": {
                "name": "memory_recall",
                "description": (
                    "대화 도중 특정 주제에 대해 과거에 기억해 둔 내용이 있는지 능동적으로 조회한다. "
                    "대화 시작 시 자동 주입되는 기억 외에 추가로 필요할 때 사용."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "조회할 주제 키워드"},
                        "k": {"type": "integer", "description": "최대 결과 수(기본 5)"},
                    },
                    "required": ["query"],
                },
            },
        },
        "handler": lambda a: memory_recall(a.get("query", ""), a.get("k", 5)),
    },
]
