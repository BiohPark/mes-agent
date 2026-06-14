"""하네스 오케스트레이터 — Executor→Reviewer 2역할 루프.

계약: docs/contracts/harness-poc-v1.md
불변식:
  I2: Reviewer LLM 호출에 tools 배열 미전송 (tool_calls 구조적 차단)
  I3: MAX_ROUNDS 상한, 무한루프 불가
  I5: generate() 루프 코드 무수정
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable, Awaitable

from agent.harness.roles import EXECUTOR, REVIEWER


@dataclass
class ReviewVerdict:
    """Reviewer LLM 단발 호출 결과."""

    passed: bool
    feedback: str = field(default="")


def parse_verdict(text: str) -> ReviewVerdict:
    """LLM 응답 텍스트에서 {passed, feedback} JSON을 파싱한다.

    파싱 실패 시 passed=True 안전 폴백 — Reviewer 오작동이 실행을 막지 않도록.
    """
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        return ReviewVerdict(passed=True)
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return ReviewVerdict(passed=True)

    passed = data.get("passed")
    if passed is True:
        return ReviewVerdict(passed=True)
    if passed is False:
        feedback = str(data.get("feedback", ""))
        return ReviewVerdict(passed=False, feedback=feedback)
    return ReviewVerdict(passed=True)


async def run_harness(
    *,
    executor_fn: Callable[..., AsyncGenerator[dict, None]],
    reviewer_fn: Callable[..., Awaitable[ReviewVerdict]],
    initial_messages: list[dict],
    system_base: str,
    max_rounds: int = 2,
):
    """Executor→Reviewer 루프. SSE dict를 yield한다.

    Args:
        executor_fn: 키워드 인자 messages, system을 받는 async generator callable.
        reviewer_fn: 키워드 인자 messages, system을 받아 ReviewVerdict를 반환하는 callable.
        initial_messages: 사용자 요청 메시지 리스트.
        system_base: 기본 시스템 프롬프트 (역할 suffix가 뒤에 붙음).
        max_rounds: Executor 최대 실행 횟수 (기본 2).
    """
    messages = list(initial_messages)
    executor_system = system_base + "\n\n" + EXECUTOR.system_suffix

    for round_n in range(max_rounds):
        is_last_round = (round_n == max_rounds - 1)

        # 1. Executor 실행 — 기존 generate() 루프 그대로 호출 (I5)
        history: list[dict] = messages
        async for event in executor_fn(messages=messages, system=executor_system):
            yield event
            if event.get("type") == "done" and "history" in event:
                history = event["history"]

        if is_last_round:
            break

        # 2. Reviewer 단발 호출 (I2: reviewer_fn이 tools 배열 미전송 책임)
        yield {"type": "harness_round", "round": round_n + 1, "phase": "reviewing"}
        verdict = await reviewer_fn(messages=history, system=REVIEWER.system_suffix)

        if verdict.passed:
            break

        # 3. Reviewer 피드백을 다음 Executor 라운드에 주입
        feedback_msg = {
            "role": "user",
            "content": f"[검증자 피드백 라운드 {round_n + 1}]: {verdict.feedback}",
        }
        messages = history + [feedback_msg]
        yield {
            "type": "harness_round",
            "round": round_n + 1,
            "phase": "retrying",
            "feedback": verdict.feedback,
        }
