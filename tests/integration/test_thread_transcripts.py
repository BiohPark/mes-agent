"""Track 1C display transcript persistence and lookup coverage."""

TASK = "general"


async def _new_thread(client):
    resp = await client.post(f"/threads/{TASK}", json={"title": "l2 transcript"})
    assert resp.status_code == 200
    return resp.json()["thread_id"]


class TestThreadDisplayTranscripts:
    async def test_display_prefers_transcript_events_after_compacted_messages(self, client):
        from agent.obsidian_session import get_session_manager

        tid = await _new_thread(client)
        mgr = get_session_manager()
        mgr.append_thread_transcript_message(TASK, tid, {"role": "user", "content": "old visible request"})
        mgr.append_thread_transcript_message(TASK, tid, {"role": "assistant", "content": "old visible answer"})
        mgr.save_thread_messages(TASK, tid, [
            {"role": "system", "content": "summary only"},
            {"role": "user", "content": "latest tail"},
        ])

        resp = await client.get(f"/threads/{TASK}/{tid}/messages")

        assert resp.status_code == 200
        assert resp.json() == [
            {"role": "user", "content": "old visible request"},
            {"role": "assistant", "content": "old visible answer"},
        ]

    async def test_message_count_uses_transcript_events(self, client):
        from agent.obsidian_session import get_session_manager

        tid = await _new_thread(client)
        mgr = get_session_manager()
        mgr.append_thread_transcript_message(TASK, tid, {"role": "user", "content": "one"})
        mgr.append_thread_transcript_message(TASK, tid, {"role": "assistant", "content": "two"})
        mgr.save_thread_messages(TASK, tid, [{"role": "system", "content": "summary only"}])

        resp = await client.get(f"/threads/{TASK}")
        thread = next(t for t in resp.json() if t["thread_id"] == tid)

        assert thread["message_count"] == 2

    async def test_search_snippet_uses_transcript_events(self, client):
        from agent.obsidian_session import get_session_manager

        tid = await _new_thread(client)
        mgr = get_session_manager()
        mgr.append_thread_transcript_message(
            TASK, tid, {"role": "assistant", "content": "needle survives compaction"}
        )
        mgr.save_thread_messages(TASK, tid, [{"role": "system", "content": "summary only"}])

        resp = await client.get("/search?q=needle")

        assert resp.status_code == 200
        hit = next(h for h in resp.json() if h["thread_id"] == tid)
        assert "needle survives" in hit["snippet"]

    async def test_server_records_compaction_summary_event(self, client, monkeypatch):
        import agent.server as srv
        from agent.obsidian_session import get_session_manager

        tid = await _new_thread(client)
        get_session_manager().save_thread_messages(TASK, tid, [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "old one"},
            {"role": "assistant", "content": "old two"},
            {"role": "user", "content": "old three"},
            {"role": "assistant", "content": "old four"},
        ])
        monkeypatch.setattr(srv, "COMPACT_RATIO", 0.0)
        monkeypatch.setattr(srv, "COMPACT_KEEP_RECENT", 1)
        monkeypatch.setattr(srv, "MAX_COMPACT", 1)
        monkeypatch.setattr(srv, "_summarize_history", lambda history: "compact summary")

        async with client.stream("POST", "/chat", json={
            "message": "force compaction", "thread_id": tid, "task_type": TASK,
        }) as resp:
            assert resp.status_code == 200
            await resp.aread()

        displayed = get_session_manager().get_thread_display_messages(TASK, tid)
        contents = [m["content"] for m in displayed]

        assert "force compaction" in contents
        assert any("compact summary" in c for c in contents)
