"""M4: 컨텍스트 초과(400) 감지 — 순수 판별 로직.

LLM 호출이 컨텍스트 한도 초과로 거부될 때를 **프로바이더 교차로 견고하게** 감지한다.
특정 모델(gpt-5-nano 등)에 묶이지 않도록, 상태코드 + 다양한 문구 패턴을 함께 본다.
또한 문구를 못 알아봐도 400(BadRequest)이면 마지막 수단으로 줄여 재시도할 수 있게
`is_bad_request`를 별도로 제공한다(원칙 #0: 모델 무관).
"""

from __future__ import annotations

# 컨텍스트 초과를 가리키는 문구(소문자) — OpenAI/사내/타 프로바이더 공통 변형
_OVERFLOW_PATTERNS = (
    "context_length_exceeded",
    "context length",
    "maximum context",
    "context window",
    "too many tokens",
    "maximum number of tokens",
    "reduce the length",
    "input is too long",
    "exceeds the maximum",
    "prompt is too long",
    "too large for the model",
)


def _message_of(exc) -> str:
    parts = [str(exc)]
    for attr in ("message", "code"):
        v = getattr(exc, attr, None)
        if v:
            parts.append(str(v))
    # openai 예외의 body/response 에 담긴 코드도 포함
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        parts.append(str(body))
    return " ".join(parts).lower()


def is_context_overflow(exc) -> bool:
    """예외가 '컨텍스트 초과'로 인식되면 True(문구 다중 매칭)."""
    msg = _message_of(exc)
    return any(p in msg for p in _OVERFLOW_PATTERNS)


def is_bad_request(exc) -> bool:
    """HTTP 400(BadRequest) 계열이면 True(미인식 컨텍스트 초과의 마지막 수단 판단용).

    401/403/404 등 줄여도 해결 안 되는 4xx는 제외한다.
    """
    if getattr(exc, "status_code", None) == 400:
        return True
    if getattr(exc, "code", None) == 400:
        return True
    return type(exc).__name__ == "BadRequestError"


def is_recoverable(exc) -> bool:
    """줄여서 재시도해 볼 가치가 있는 예외(컨텍스트 초과 또는 400)."""
    return is_context_overflow(exc) or is_bad_request(exc)
