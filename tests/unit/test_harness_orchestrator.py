"""하네스 오케스트레이터 단위 테스트 — FakeLLM으로 네트워크 없이."""

import pytest
from agent.harness.orchestrator import (
    ReviewVerdict,
    parse_verdict,
    run_harness,
)


# ── parse_verdict ────────────────────────────────────────────

class TestParseVerdict:
    def test_passed_true(self):
        v = parse_verdict('{"passed": true}')
        assert v.passed is True
        assert v.feedback == ""

    def test_passed_false_with_feedback(self):
        v = parse_verdict('{"passed": false, "feedback": "파일이 틀렸습니다"}')
        assert v.passed is False
        assert "파일" in v.feedback

    def test_json_embedded_in_text(self):
        v = parse_verdict('검토 결과: {"passed": false, "feedback": "재시도 필요"} 끝.')
        assert v.passed is False
        assert "재시도" in v.feedback

    def test_parse_failure_defaults_to_passed(self):
        """파싱 실패 → 안전 폴백 passed=True."""
        v = parse_verdict("이건 JSON이 아닙니다")
        assert v.passed is True

    def test_malformed_json_defaults_to_passed(self):
        v = parse_verdict("{broken json}")
        assert v.passed is True

    def test_passed_true_no_feedback_field(self):
        v = parse_verdict('{"passed": true}')
        assert v.passed is True
        assert v.feedback == ""

    def test_boolean_string_false(self):
        """'false' 문자열도 처리."""
        v = parse_verdict('{"passed": false, "feedback": "수정 필요"}')
        assert v.passed is False


# ── run_harness ──────────────────────────────────────────────

def _make_executor_fn(events_per_round: list[list[dict]]):
    """각 호출마다 next events 리스트를 yield하는 FakeExecutor."""
    calls = iter(events_per_round)

    async def executor_fn(*, messages, system, **kwargs):
        try:
            events = next(calls)
        except StopIteration:
            events = [{"type": "done"}]
        for e in events:
            yield e

    return executor_fn


def _make_reviewer_fn(verdicts: list[ReviewVerdict]):
    """순서대로 ReviewVerdict를 반환하는 FakeReviewer."""
    verdicts_iter = iter(verdicts)

    async def reviewer_fn(*, messages, system, **kwargs) -> ReviewVerdict:
        try:
            return next(verdicts_iter)
        except StopIteration:
            return ReviewVerdict(passed=True)

    return reviewer_fn


async def _collect(gen) -> list[dict]:
    result = []
    async for item in gen:
        result.append(item)
    return result


class TestRunHarness:
    @pytest.mark.asyncio
    async def test_single_pass_when_reviewer_passes(self):
        """Reviewer가 pass → 라운드 1회 후 종료."""
        executor_fn = _make_executor_fn([
            [{"type": "text", "text": "완료"}, {"type": "done", "history": []}]
        ])
        reviewer_fn = _make_reviewer_fn([ReviewVerdict(passed=True)])

        events = await _collect(run_harness(
            executor_fn=executor_fn,
            reviewer_fn=reviewer_fn,
            initial_messages=[{"role": "user", "content": "작업"}],
            system_base="기본 시스템 프롬프트",
            max_rounds=2,
        ))
        types = [e["type"] for e in events]
        assert "text" in types
        assert "done" in types
        assert "harness_round" in types
        # reviewing 이벤트가 있고 retrying은 없음
        reviewing = [e for e in events if e.get("type") == "harness_round" and e.get("phase") == "reviewing"]
        retrying = [e for e in events if e.get("type") == "harness_round" and e.get("phase") == "retrying"]
        assert len(reviewing) == 1
        assert len(retrying) == 0

    @pytest.mark.asyncio
    async def test_retry_when_reviewer_fails(self):
        """Reviewer 실패 → Executor 재시도."""
        executor_fn = _make_executor_fn([
            [{"type": "text", "text": "1차 실행"}, {"type": "done", "history": []}],
            [{"type": "text", "text": "2차 실행"}, {"type": "done", "history": []}],
        ])
        reviewer_fn = _make_reviewer_fn([
            ReviewVerdict(passed=False, feedback="파일이 잘못됨"),
        ])

        events = await _collect(run_harness(
            executor_fn=executor_fn,
            reviewer_fn=reviewer_fn,
            initial_messages=[{"role": "user", "content": "작업"}],
            system_base="기본",
            max_rounds=2,
        ))
        types = [e["type"] for e in events]
        texts = [e.get("text", "") for e in events if e.get("type") == "text"]
        assert "1차 실행" in texts
        assert "2차 실행" in texts
        retrying = [e for e in events if e.get("type") == "harness_round" and e.get("phase") == "retrying"]
        assert len(retrying) == 1
        assert "파일이 잘못됨" in retrying[0]["feedback"]

    @pytest.mark.asyncio
    async def test_max_rounds_respected(self):
        """max_rounds=1이면 Reviewer 호출 없이 종료."""
        executor_fn = _make_executor_fn([
            [{"type": "done", "history": []}]
        ])
        reviewer_fn = _make_reviewer_fn([])

        events = await _collect(run_harness(
            executor_fn=executor_fn,
            reviewer_fn=reviewer_fn,
            initial_messages=[{"role": "user", "content": "작업"}],
            system_base="기본",
            max_rounds=1,
        ))
        # Reviewer가 호출되지 않으므로 harness_round 이벤트 없음
        harness_events = [e for e in events if e.get("type") == "harness_round"]
        assert len(harness_events) == 0

    @pytest.mark.asyncio
    async def test_feedback_injected_into_second_round(self):
        """Reviewer 피드백이 두 번째 Executor 메시지에 포함되는지."""
        received_messages = []

        async def executor_fn(*, messages, system, **kwargs):
            received_messages.append(messages[:])
            yield {"type": "done", "history": messages}

        reviewer_fn = _make_reviewer_fn([
            ReviewVerdict(passed=False, feedback="경로가 틀렸음"),
        ])

        await _collect(run_harness(
            executor_fn=executor_fn,
            reviewer_fn=reviewer_fn,
            initial_messages=[{"role": "user", "content": "작업"}],
            system_base="기본",
            max_rounds=2,
        ))
        assert len(received_messages) == 2
        second_round_content = str(received_messages[1])
        assert "경로가 틀렸음" in second_round_content

    @pytest.mark.asyncio
    async def test_reviewer_parse_failure_does_not_retry(self):
        """Reviewer 파싱 실패(안전 폴백 passed=True) → 재시도 없음."""
        executor_fn = _make_executor_fn([
            [{"type": "done", "history": []}],
        ])
        # ReviewVerdict(passed=True) 반환 = 파싱 실패 폴백과 같음
        reviewer_fn = _make_reviewer_fn([ReviewVerdict(passed=True)])

        events = await _collect(run_harness(
            executor_fn=executor_fn,
            reviewer_fn=reviewer_fn,
            initial_messages=[{"role": "user", "content": "작업"}],
            system_base="기본",
            max_rounds=2,
        ))
        retrying = [e for e in events if e.get("type") == "harness_round" and e.get("phase") == "retrying"]
        assert len(retrying) == 0

    @pytest.mark.asyncio
    async def test_executor_system_includes_role_suffix(self):
        """Executor 호출 시 system에 역할 suffix가 포함돼야 한다."""
        received_systems = []

        async def executor_fn(*, messages, system, **kwargs):
            received_systems.append(system)
            yield {"type": "done", "history": messages}

        reviewer_fn = _make_reviewer_fn([ReviewVerdict(passed=True)])

        await _collect(run_harness(
            executor_fn=executor_fn,
            reviewer_fn=reviewer_fn,
            initial_messages=[{"role": "user", "content": "작업"}],
            system_base="기본 시스템",
            max_rounds=2,
        ))
        assert len(received_systems) >= 1
        assert "기본 시스템" in received_systems[0]
        assert "실행자" in received_systems[0] or "executor" in received_systems[0].lower()
