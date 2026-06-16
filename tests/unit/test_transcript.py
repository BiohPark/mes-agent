"""Track 0: transcript persistence/display filtering."""

from agent.core.transcript import (
    compaction_summary_event,
    display_messages_from_events,
    ephemeral_user_message,
    filter_display_messages,
    filter_persisted_messages,
    strip_ephemeral_metadata,
    transcript_event_from_message,
    transcript_events_from_messages,
)


def test_ephemeral_user_messages_are_not_persisted_or_displayed():
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "실제 요청"},
        ephemeral_user_message("[시스템] 계속 진행", "nudge"),
        {"role": "assistant", "content": "응답"},
    ]

    persisted = filter_persisted_messages(msgs)
    displayed = filter_display_messages(msgs)

    assert [m.get("content") for m in persisted if m.get("role") == "user"] == ["실제 요청"]
    assert displayed == [
        {"role": "user", "content": "실제 요청"},
        {"role": "assistant", "content": "응답"},
    ]


def test_strip_ephemeral_metadata_keeps_content_for_llm():
    msg = ephemeral_user_message("[시스템] 계획이 승인되었다.", "plan_approved")
    stripped = strip_ephemeral_metadata([msg])

    assert stripped == [{"role": "user", "content": "[시스템] 계획이 승인되었다."}]
    assert "_ephemeral" not in stripped[0]


def test_ephemeral_flag_filters_even_without_legacy_prefix():
    msg = ephemeral_user_message("runtime only", "test")

    assert filter_persisted_messages([msg]) == []
    assert filter_display_messages([msg]) == []
    assert strip_ephemeral_metadata([msg]) == [{"role": "user", "content": "runtime only"}]


def test_legacy_control_prefixes_are_filtered():
    msgs = [
        {"role": "user", "content": "[시스템] 작업이 아직 끝나지 않았다면 계속"},
        {"role": "user", "content": "[사용자 끼어들기] 잠깐 이 조건도 봐"},
        {"role": "user", "content": "진짜 사용자 메시지"},
        {"role": "assistant", "content": "보이는 답"},
        {"role": "tool", "content": "숨김"},
    ]

    assert filter_display_messages(msgs) == [
        {"role": "user", "content": "진짜 사용자 메시지"},
        {"role": "assistant", "content": "보이는 답"},
    ]
    assert filter_persisted_messages(msgs) == [
        {"role": "user", "content": "진짜 사용자 메시지"},
        {"role": "assistant", "content": "보이는 답"},
        {"role": "tool", "content": "숨김"},
    ]
