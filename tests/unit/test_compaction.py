"""G1 STEP 1: 순수 compaction 함수 단위 테스트 (LLM 불필요).

핵심은 짝 보존(I1): tool_calls↔tool 짝을 깨지 않는다.
"""

from agent.core.compaction import (
    compact_messages,
    has_orphan_tool,
    prune_images,
    SUMMARY_PREFIX,
    PRUNED_IMAGE_PLACEHOLDER,
)


def _fake_summary(msgs):
    return "요약본"


def _img_user(b64, text="화면"):
    """capture 주입과 동형의 user 멀티모달 메시지."""
    return {"role": "user", "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
    ]}


def _image_count(messages):
    n = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            n += sum(1 for b in c if isinstance(b, dict) and b.get("type") == "image_url")
    return n


def _sys(c="sys"):
    return {"role": "system", "content": c}


def _user(c):
    return {"role": "user", "content": c}


def _asst(c):
    return {"role": "assistant", "content": c}


def _asst_tc(*ids):
    return {"role": "assistant", "tool_calls": [
        {"id": i, "type": "function", "function": {"name": "t", "arguments": "{}"}} for i in ids
    ]}


def _tool(call_id, c="ok"):
    return {"role": "tool", "tool_call_id": call_id, "content": c}


def test_no_compaction_when_body_small():
    """중간 구간이 없으면(짧으면) 원본을 그대로 반환한다."""
    msgs = [_sys(), _user("a"), _asst("b")]
    out = compact_messages(msgs, keep_recent=6, summarize_fn=_fake_summary)
    assert out == msgs


def test_preserves_leading_system_and_recent():
    msgs = [_sys("S")] + [_user(f"u{i}") for i in range(10)]
    out = compact_messages(msgs, keep_recent=3, summarize_fn=_fake_summary)
    # 선두 system 보존
    assert out[0] == _sys("S")
    # 요약 메시지 1개 삽입
    assert out[1]["role"] == "system" and out[1]["content"].startswith(SUMMARY_PREFIX)
    # 마지막 3개 보존
    assert out[-3:] == [_user("u7"), _user("u8"), _user("u9")]
    # 전체 길이 감소
    assert len(out) < len(msgs)


def test_summarize_receives_middle_only():
    captured = {}

    def cap(msgs):
        captured["middle"] = list(msgs)
        return "x"

    msgs = [_sys()] + [_user(f"u{i}") for i in range(8)]
    compact_messages(msgs, keep_recent=2, summarize_fn=cap)
    # 중간 = 선두 system 제외 후, 마지막 2개 제외
    assert captured["middle"] == [_user(f"u{i}") for i in range(6)]


def test_tail_not_starting_with_orphan_tool():
    """tail 경계가 tool에 걸리면 주인 assistant까지 당겨 orphan을 막는다."""
    # body 구조: u0, A(tc1,tc2), tool1, tool2, u1
    msgs = [_sys(), _user("u0"), _asst_tc("c1", "c2"), _tool("c1"), _tool("c2"), _user("u1")]
    # keep_recent=2 라면 단순 cut은 [tool2, u1] → tool2가 orphan으로 시작
    out = compact_messages(msgs, keep_recent=2, summarize_fn=_fake_summary)
    assert not has_orphan_tool(out), "압축 결과에 orphan tool 발생"
    # 보정으로 assistant(tool_calls)부터 보존돼야 함
    roles = [m.get("role") for m in out]
    # 마지막 구간에 assistant(tool_calls)+tool+tool 이 온전히 포함
    assert {"role": "assistant", "tool_calls": msgs[2]["tool_calls"]} in out
    assert _tool("c1") in out and _tool("c2") in out


def test_result_has_no_orphan_tool_general():
    msgs = [_sys()]
    for i in range(5):
        msgs += [_user(f"u{i}"), _asst_tc(f"c{i}"), _tool(f"c{i}")]
    out = compact_messages(msgs, keep_recent=4, summarize_fn=_fake_summary)
    assert not has_orphan_tool(out)


def test_returns_original_if_boundary_collapses():
    """경계 보정 결과 중간이 비면 원본 유지(짝 보호 우선)."""
    # tail 전체가 하나의 tool 묶음이라 보정 시 cut→0 이 되는 케이스
    msgs = [_sys(), _asst_tc("c1"), _tool("c1")]
    out = compact_messages(msgs, keep_recent=1, summarize_fn=_fake_summary)
    assert out == msgs


def test_has_orphan_tool_helper():
    assert has_orphan_tool([_tool("x")]) is True
    assert has_orphan_tool([_asst_tc("x"), _tool("x")]) is False


# ── M2 이미지 eviction ──────────────────────────────────────────────

def test_prune_keeps_only_last_k_images():
    msgs = [_sys()] + [_img_user(f"img{i}") for i in range(5)]
    out = prune_images(msgs, keep_last_images=2)
    # 최신 2개만 남는다
    assert _image_count(out) == 2
    # 남은 이미지는 마지막 두 메시지의 것(img3, img4)
    kept = [b["image_url"]["url"] for m in out for b in (m.get("content") or [])
            if isinstance(b, dict) and b.get("type") == "image_url"]
    assert kept == ["data:image/png;base64,img3", "data:image/png;base64,img4"]


def test_prune_replaces_old_images_with_placeholder():
    msgs = [_sys()] + [_img_user(f"img{i}") for i in range(3)]
    out = prune_images(msgs, keep_last_images=1)
    # 첫 두 이미지는 자리표시자 텍스트로 치환(순번 1,2)
    texts = [b["text"] for m in out for b in (m.get("content") or [])
             if isinstance(b, dict) and b.get("type") == "text"]
    assert PRUNED_IMAGE_PLACEHOLDER.format(n=1) in texts
    assert PRUNED_IMAGE_PLACEHOLDER.format(n=2) in texts
    # 동반 텍스트("화면")는 보존
    assert texts.count("화면") == 3


def test_prune_preserves_companion_text_block():
    msgs = [_img_user("only", text="버튼 확인")]
    out = prune_images(msgs, keep_last_images=0)
    blocks = out[0]["content"]
    # 이미지 블록은 사라지고 텍스트 블록은 유지 + 자리표시자 추가
    assert {"type": "text", "text": "버튼 확인"} in blocks
    assert any(b.get("text", "").startswith("[이전 화면 이미지") for b in blocks)
    assert not any(b.get("type") == "image_url" for b in blocks)


def test_prune_noop_when_within_limit():
    msgs = [_sys(), _img_user("a"), _img_user("b")]
    out = prune_images(msgs, keep_last_images=2)
    assert out is msgs  # 멱등/안전: 동일 객체 반환


def test_prune_does_not_mutate_input():
    msgs = [_img_user("x"), _img_user("y")]
    snapshot = [m["content"][1]["image_url"]["url"] for m in msgs]
    prune_images(msgs, keep_last_images=0)
    after = [m["content"][1]["image_url"]["url"] for m in msgs]
    assert after == snapshot  # 원본 불변


def test_prune_preserves_tool_pairs_no_orphan():
    """이미지가 tool 묶음 사이에 있어도 짝(I1)을 깨지 않는다."""
    msgs = [
        _sys(),
        _asst_tc("c1"), _tool("c1"),
        _img_user("img0"),
        _asst_tc("c2"), _tool("c2"),
        _img_user("img1"),
    ]
    out = prune_images(msgs, keep_last_images=1)
    assert not has_orphan_tool(out)
    assert _image_count(out) == 1


def test_prune_negative_keep_treated_as_zero():
    msgs = [_img_user("a")]
    out = prune_images(msgs, keep_last_images=-3)
    assert _image_count(out) == 0
