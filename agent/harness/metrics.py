"""하네스 실측 메트릭 — RunLedger의 harness_round 엔트리 집계 (순수, IO 없음).

목적: Executor→Reviewer 하네스가 실제로 가치를 내는지(자기교정·비용)를
데이터로 답할 수 있게 한다. P1 #2(N 에픽 — Planner 역할 추가 여부) 결정의 입력.

계약: docs/specs/domain-harness-pack.md Phase 1
"""
from __future__ import annotations

import json

HARNESS_ROUND_EVENT = "harness_round"


def _parse_round(entry: dict) -> dict | None:
    """ledger dict 한 줄에서 harness 라운드 detail을 파싱한다.

    detail은 JSON 문자열(영속 형태) 또는 dict(테스트 편의)일 수 있다.
    harness_round가 아니거나 손상된 줄은 None.
    """
    if not isinstance(entry, dict) or entry.get("event") != HARNESS_ROUND_EVENT:
        return None
    detail = entry.get("detail", "")
    if isinstance(detail, dict):
        data = detail
    elif isinstance(detail, str):
        try:
            data = json.loads(detail)
        except (json.JSONDecodeError, ValueError):
            return None
    else:
        return None
    if not isinstance(data, dict) or "round" not in data:
        return None
    return data


def summarize_harness_runs(entries: list[dict]) -> dict:
    """RunLedger 엔트리 리스트에서 하네스 라운드를 집계한다.

    반환:
      total_reviews    — Reviewer 판결이 기록된 라운드 수
      retries          — passed=False(재시도 유발) 판결 수
      final_passed     — 마지막 판결의 통과 여부 (없으면 None)
      self_corrected   — 실패 판결이 있었으나 최종 통과 → 자기교정 성공
      max_history_tokens — 라운드별 누적 이력 토큰 추정의 최댓값
      rounds           — 정렬된 라운드 detail 목록(원본)
    """
    rounds: list[dict] = []
    for entry in entries:
        parsed = _parse_round(entry)
        if parsed is not None:
            rounds.append(parsed)
    rounds.sort(key=lambda d: d.get("round", 0))

    total_reviews = len(rounds)
    retries = sum(1 for r in rounds if r.get("passed") is False)
    final_passed = rounds[-1].get("passed") if rounds else None
    had_failure = any(r.get("passed") is False for r in rounds)
    self_corrected = bool(had_failure and final_passed is True)
    max_history_tokens = max(
        (int(r.get("history_tokens", 0) or 0) for r in rounds),
        default=0,
    )

    return {
        "total_reviews": total_reviews,
        "retries": retries,
        "final_passed": final_passed,
        "self_corrected": self_corrected,
        "max_history_tokens": max_history_tokens,
        "rounds": rounds,
    }
