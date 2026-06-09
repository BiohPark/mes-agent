"""G1: 컨텍스트 compaction (순수 로직).

긴 대화가 컨텍스트 한도에 가까워지면, 선두 system 메시지와 최근 N턴은 보존하고
그 사이 오래된 메시지를 요약 1개로 치환한다.

핵심 불변조건(I1): OpenAI tool-calling 규약상 `assistant(tool_calls)` 와 그에 대응하는
`tool`(tool_call_id) 메시지는 짝을 이뤄야 한다. 압축이 이 짝을 깨면 API가 거부한다.
따라서 보존 구간(tail)은 절대 orphan `tool` 메시지로 시작하지 않도록 경계를 보정한다.

요약 호출(LLM)은 `summarize_fn`으로 **주입**받아 이 모듈을 순수/테스트 가능하게 유지한다.
루프(server.generate) 쪽에서 실제 LLM 요약 함수를 넘긴다.
"""

from __future__ import annotations

from typing import Callable

SUMMARY_PREFIX = "[이전 진행 요약]\n"


def _leading_system_count(messages: list) -> int:
    """선두에 연속된 system 메시지 개수."""
    n = 0
    for m in messages:
        if m.get("role") == "system":
            n += 1
        else:
            break
    return n


def _safe_tail_start(body: list, cut: int) -> int:
    """tail = body[cut:] 가 orphan tool로 시작하지 않도록 경계를 앞으로 당긴다.

    body는 선두 system을 제외한 부분. tool 메시지의 주인은 직전 assistant(tool_calls)이므로,
    cut이 tool을 가리키면 그 tool 묶음의 주인 assistant까지 포함하도록 cut을 감소시킨다.
    """
    while cut > 0 and cut < len(body) and body[cut].get("role") == "tool":
        cut -= 1
    return cut


def compact_messages(
    messages: list,
    *,
    keep_recent: int,
    summarize_fn: Callable[[list], str],
) -> list:
    """오래된 중간 구간을 요약 1개로 치환한 새 메시지 리스트를 반환한다.

    - 선두 system 메시지(들) 보존
    - 마지막 keep_recent개 메시지 보존
    - 짝 보존(I1): tail이 orphan tool로 시작하지 않도록 경계 보정
    - 압축 대상(중간)이 없으면 원본을 그대로 반환(멱등/안전)
    """
    if keep_recent < 0:
        keep_recent = 0

    head_n = _leading_system_count(messages)
    head = messages[:head_n]
    body = messages[head_n:]

    # 보존할 tail이 body 전체를 덮으면 압축할 중간이 없음
    if len(body) <= keep_recent:
        return messages

    cut = len(body) - keep_recent
    cut = _safe_tail_start(body, cut)

    middle = body[:cut]
    tail = body[cut:]
    if not middle:
        # 경계 보정 결과 중간이 비었으면 압축 불가 — 원본 유지
        return messages

    summary = summarize_fn(middle)
    summary_msg = {"role": "system", "content": SUMMARY_PREFIX + (summary or "")}
    return head + [summary_msg] + tail


def has_orphan_tool(messages: list) -> bool:
    """assistant(tool_calls) 없이 떠도는 tool 메시지가 있으면 True (불변조건 검증용)."""
    known_ids: set[str] = set()
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                if tc.get("id"):
                    known_ids.add(tc["id"])
        elif m.get("role") == "tool":
            if m.get("tool_call_id") not in known_ids:
                return True
    return False
