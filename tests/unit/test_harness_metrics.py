"""하네스 실측 메트릭 집계 단위 테스트 (순수, 네트워크 없음).

agent.harness.metrics.summarize_harness_runs가 RunLedger의 harness_round
엔트리에서 라운드 수·재시도·자기교정·비용을 정확히 집계하는지 검증한다.
"""

from agent.harness.metrics import summarize_harness_runs


def _round_entry(n, passed, history_tokens=0, feedback_len=0, as_dict=False):
    detail = {
        "round": n,
        "passed": passed,
        "feedback_len": feedback_len,
        "history_tokens": history_tokens,
    }
    import json
    return {
        "event": "harness_round",
        "phase": "verifying",
        "detail": detail if as_dict else json.dumps(detail),
    }


def test_empty_ledger():
    s = summarize_harness_runs([])
    assert s["total_reviews"] == 0
    assert s["retries"] == 0
    assert s["final_passed"] is None
    assert s["self_corrected"] is False
    assert s["max_history_tokens"] == 0


def test_single_passed_round():
    s = summarize_harness_runs([_round_entry(1, True, history_tokens=1200)])
    assert s["total_reviews"] == 1
    assert s["retries"] == 0
    assert s["final_passed"] is True
    assert s["self_corrected"] is False
    assert s["max_history_tokens"] == 1200


def test_fail_then_pass_is_self_corrected():
    entries = [
        _round_entry(1, False, history_tokens=1000, feedback_len=40),
        _round_entry(2, True, history_tokens=1800),
    ]
    s = summarize_harness_runs(entries)
    assert s["total_reviews"] == 2
    assert s["retries"] == 1
    assert s["final_passed"] is True
    assert s["self_corrected"] is True
    assert s["max_history_tokens"] == 1800


def test_fail_without_recovery_not_self_corrected():
    s = summarize_harness_runs([_round_entry(1, False), _round_entry(2, False)])
    assert s["retries"] == 2
    assert s["final_passed"] is False
    assert s["self_corrected"] is False


def test_corrupted_detail_skipped():
    bad = {"event": "harness_round", "detail": "{not json"}
    s = summarize_harness_runs([bad, _round_entry(1, True)])
    assert s["total_reviews"] == 1


def test_non_harness_entries_ignored():
    other = {"event": "done", "phase": "done", "detail": ""}
    s = summarize_harness_runs([other, _round_entry(1, True)])
    assert s["total_reviews"] == 1


def test_dict_detail_supported():
    """테스트 편의를 위해 detail이 dict인 경우도 처리한다."""
    s = summarize_harness_runs([_round_entry(1, True, as_dict=True)])
    assert s["total_reviews"] == 1
    assert s["final_passed"] is True


def test_rounds_sorted_by_round_number():
    entries = [_round_entry(2, True), _round_entry(1, False)]
    s = summarize_harness_runs(entries)
    assert [r["round"] for r in s["rounds"]] == [1, 2]
    assert s["final_passed"] is True
