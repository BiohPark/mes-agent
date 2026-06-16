"""Transcript filtering and display transcript reconstruction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CONTROL_PREFIXES = ("[시스템]", "[사용자 끼어들기]", "[?쒖뒪??", "[?ъ슜???쇱뼱?ㅺ린]")
VISIBLE_TRANSCRIPT_KINDS = {"message", "compaction_summary"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ephemeral_user_message(content: str, kind: str) -> dict:
    return {"role": "user", "content": content, "_ephemeral": kind}


def content_to_display_text(content: Any) -> str:
    """Return text safe for user-facing transcript display."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        omitted_images = 0
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and block.get("text"):
                parts.append(str(block["text"]))
            elif block.get("type") == "image_url":
                omitted_images += 1
        if omitted_images:
            parts.append(f"[image omitted: {omitted_images}]")
        return "\n".join(p for p in parts if p)
    return str(content) if content is not None else ""


def _is_legacy_control_message(message: dict) -> bool:
    if message.get("role") != "user":
        return False
    content = message.get("content")
    return isinstance(content, str) and content.startswith(CONTROL_PREFIXES)


def _is_ephemeral(message: dict) -> bool:
    return bool(message.get("_ephemeral")) or _is_legacy_control_message(message)


def strip_ephemeral_metadata(messages: list) -> list:
    """Return API-safe messages without private runtime metadata."""
    out = []
    for message in messages:
        if not isinstance(message, dict):
            out.append(message)
            continue
        clean = dict(message)
        clean.pop("_ephemeral", None)
        out.append(clean)
    return out


def filter_persisted_messages(messages: list) -> list:
    """Remove runtime-only control messages before writing thread history."""
    result = []
    for message in messages:
        if isinstance(message, dict) and _is_ephemeral(message):
            continue
        result.extend(strip_ephemeral_metadata([message]))
    return result


def filter_display_messages(messages: list) -> list:
    """Return only user/assistant messages meant for the chat transcript."""
    result = []
    for message in messages:
        if not isinstance(message, dict) or _is_ephemeral(message):
            continue
        role = message.get("role", "")
        content = content_to_display_text(message.get("content", ""))
        if role in ("user", "assistant") and content:
            result.append({"role": role, "content": content})
    return result


def transcript_event_from_message(message: dict, *, kind: str = "message", ts: str | None = None) -> dict | None:
    """Create an append-only display transcript event from a visible message."""
    if not isinstance(message, dict) or _is_ephemeral(message):
        return None
    role = message.get("role", "")
    if role not in ("user", "assistant"):
        return None
    content = content_to_display_text(message.get("content"))
    if not content:
        return None
    return {
        "ts": ts or _now_iso(),
        "kind": kind,
        "role": role,
        "content": content,
    }


def compaction_summary_event(summary: str, *, ts: str | None = None) -> dict | None:
    content = content_to_display_text(summary).strip()
    if not content:
        return None
    return {
        "ts": ts or _now_iso(),
        "kind": "compaction_summary",
        "role": "assistant",
        "content": content,
    }


def display_messages_from_events(events: list) -> list:
    """Reconstruct user-facing messages from append-only transcript events."""
    messages = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("kind") not in VISIBLE_TRANSCRIPT_KINDS:
            continue
        role = event.get("role")
        content = content_to_display_text(event.get("content", ""))
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    return messages


def transcript_events_from_messages(messages: list, *, ts: str | None = None) -> list[dict]:
    events = []
    for message in messages:
        event = transcript_event_from_message(message, ts=ts)
        if event:
            events.append(event)
    return events
