"""server.py 순수 헬퍼 단위 테스트 — 멀티모달(이미지) 메시지 처리.

capture_screen 주입으로 생기는 list-content(user) 메시지를 토큰 추정·요약 평탄화가
크래시 없이 다루는지 검증한다.
"""

from agent.server import _history_to_text, _estimate_tokens


def _img_msg(text="방금 캡처한 화면", b64="QUJD"):
    return {"role": "user", "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
    ]}


def test_history_to_text_flattens_image_message():
    out = _history_to_text([
        {"role": "user", "content": "안녕"},
        _img_msg(text="진행 상태 확인"),
    ])
    assert "안녕" in out
    assert "진행 상태 확인" in out
    assert "[화면 이미지]" in out


def test_history_to_text_no_crash_on_image_only():
    msg = {"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
    ]}
    out = _history_to_text([msg])
    assert "[화면 이미지]" in out


def test_estimate_tokens_counts_image_as_fixed_cost():
    """이미지 토큰은 base64 길이가 아니라 고정 비용으로 계산한다(과대/과소계상 방지)."""
    huge_b64 = "A" * 100000  # base64 길이로 세면 ~25000토큰까지 부풀려짐
    small = _estimate_tokens([{"role": "user", "content": "짧은 텍스트"}])
    with_img = _estimate_tokens([_img_msg(text="x", b64=huge_b64)])
    # 고정 비용(~1000) 근처여야 한다(거대 base64 길이에 비례하지 않음)
    assert with_img < 2000
    assert with_img > small
