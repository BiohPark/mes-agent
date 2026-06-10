"""협업모드(코치 모드) — 백로그 H.

사용자가 직접 작업하는 동안, 에이전트가 관찰자로 화면을 보며 비간섭 힌트를 만든다.
힌트는 메인 에이전트 루프(server.generate)를 타지 않고 **도구 없는(toolless) 단발 멀티모달
호출**로 만든다 → 실행 도구가 구조적으로 차단되고 비용·복잡도가 낮다.

흐름: start(goal) → 주기 tick(변화 게이트로 LLM 호출 통제) → 힌트 1개.
순수 로직(screenshot/LLM은 주입·monkeypatch 가능)이라 단위 테스트 가능.
"""

from __future__ import annotations

import base64
import io
import os

from agent.llm import get_client, get_model

# thread_id(또는 "") → {"goal", "last_shot"(bytes|None), "hint_history"[]}
_sessions: dict[str, dict] = {}

_COACH_SYSTEM = (
    "너는 사용자의 작업을 어깨너머로 지켜보는 조용한 코치다. "
    "사용자의 목표와 현재 화면을 보고, 지금 바로 도움이 될 짧은 힌트가 있으면 한국어 한 문장으로만 답하라. "
    "특별히 줄 힌트가 없거나 사용자가 잘 진행 중이면 정확히 'NONE'이라고만 답하라. "
    "잔소리·뻔한 말·직전과 같은 힌트 반복은 금지. 사용자의 작업을 대신 수행하지 마라(조언만)."
)


def _new_session(goal: str) -> dict:
    return {"goal": goal or "", "last_shot": None, "hint_history": []}


def start(thread_id: str, goal: str) -> dict:
    """협업 세션을 시작/리셋한다."""
    _sessions[thread_id or ""] = _new_session(goal)
    return {"ok": True, "goal": goal or ""}


def stop(thread_id: str) -> dict:
    _sessions.pop(thread_id or "", None)
    return {"ok": True}


def _change_ratio(prev_png: bytes | None, cur_png: bytes) -> float:
    """직전·현재 스크린샷의 평균 픽셀 변화율(0~1). 직전이 없으면 1.0(=완전 변화)."""
    if not prev_png:
        return 1.0
    try:
        from PIL import Image, ImageChops
        a = Image.open(io.BytesIO(prev_png)).convert("L").resize((64, 64))
        b = Image.open(io.BytesIO(cur_png)).convert("L").resize((64, 64))
        diff = ImageChops.difference(a, b)
        total = sum(i * c for i, c in enumerate(diff.histogram()))
        return (total / (64 * 64)) / 255.0
    except Exception:
        return 1.0  # 계산 실패 시 보수적으로 변화 있음 처리


def screenshot_and_diff(thread_id: str) -> tuple[bytes, float]:
    """현재 화면을 캡처하고 직전 대비 변화율을 계산한다(세션의 last_shot 갱신)."""
    from agent.tools.vision import _screenshot
    cur = _screenshot()
    sess = _sessions.setdefault(thread_id or "", _new_session(""))
    ratio = _change_ratio(sess.get("last_shot"), cur)
    sess["last_shot"] = cur
    return cur, ratio


def make_hint(goal: str, img_b64: str, history: list[str]) -> str | None:
    """목표 + 현재 화면(멀티모달)으로 짧은 힌트를 만든다. 없으면 None. (tools 미전송)"""
    recent = " / ".join(history[-3:]) if history else "없음"
    user_content = [
        {"type": "text", "text": f"목표: {goal or '(미설정)'}\n최근 준 힌트: {recent}\n현재 화면:"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}},
    ]
    resp = get_client().chat.completions.create(
        model=get_model(),
        stream=False,
        messages=[
            {"role": "system", "content": _COACH_SYSTEM},
            {"role": "user", "content": user_content},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text or text.upper().strip(" .'\"") == "NONE":
        return None
    return text


def tick(thread_id: str, force: bool = False) -> dict:
    """주기 틱: 변화가 충분(또는 force)할 때만 힌트를 생성한다."""
    sess = _sessions.get(thread_id or "")
    if not sess:
        return {"active": False, "hint": None}
    try:
        img_bytes, ratio = screenshot_and_diff(thread_id)
    except Exception as e:
        return {"active": True, "hint": None, "error": str(e)}

    threshold = _threshold()
    if not force and ratio < threshold:
        return {"active": True, "hint": None, "change": round(ratio, 3), "skipped": True}

    try:
        hint = make_hint(sess["goal"], base64.b64encode(img_bytes).decode(), sess["hint_history"])
    except Exception as e:
        return {"active": True, "hint": None, "change": round(ratio, 3), "error": str(e)}

    if hint:
        sess["hint_history"].append(hint)
    return {"active": True, "hint": hint, "change": round(ratio, 3)}


def _threshold() -> float:
    try:
        return float(os.environ.get("COLLAB_CHANGE_THRESHOLD", "0.08"))
    except (TypeError, ValueError):
        return 0.08
