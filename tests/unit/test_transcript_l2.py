"""Track 1C: L2 display transcript event reconstruction."""

from agent.core.transcript import (
    compaction_summary_event,
    display_messages_from_events,
    ephemeral_user_message,
    transcript_event_from_message,
    transcript_events_from_messages,
)


def test_transcript_events_reconstruct_visible_messages_only():
    events = transcript_events_from_messages([
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
        ephemeral_user_message("[system] hidden", "nudge"),
        {"role": "assistant", "content": "world"},
        {"role": "tool", "content": "tool-result"},
    ], ts="2026-01-01T00:00:00+00:00")

    assert events == [
        {"ts": "2026-01-01T00:00:00+00:00", "kind": "message", "role": "user", "content": "hello"},
        {"ts": "2026-01-01T00:00:00+00:00", "kind": "message", "role": "assistant", "content": "world"},
    ]
    assert display_messages_from_events(events) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_transcript_event_sanitizes_multimodal_content():
    event = transcript_event_from_message({
        "role": "user",
        "content": [
            {"type": "text", "text": "look here"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,secret"}},
        ],
    }, ts="2026-01-01T00:00:00+00:00")

    assert event["content"] == "look here\n[image omitted: 1]"
    assert "base64" not in event["content"]


def test_compaction_summary_event_is_display_visible():
    event = compaction_summary_event("summary text", ts="2026-01-01T00:00:00+00:00")

    assert display_messages_from_events([event]) == [
        {"role": "assistant", "content": "summary text"},
    ]
