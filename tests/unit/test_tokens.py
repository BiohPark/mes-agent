"""M3 토큰 추정 순수 로직 단위 테스트.

이미지 타일링 공식·data URL 치수 파싱·텍스트 추정(폴백)·메시지 합산을 검증한다.
실제 LLM/tiktoken 설치에 의존하지 않는다(폴백 경로 보장).
"""

import base64
import io

from agent.core.tokens import (
    estimate_text_tokens,
    estimate_message_tokens,
    image_block_tokens,
    image_dims_from_data_url,
    high_detail_tokens,
    _DEFAULT_HIGH_TOKENS,
    _LOW_DETAIL_TOKENS,
)


def _png_url(w, h):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _jpeg_url(w, h):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _img_block(url, detail=None):
    iu = {"url": url}
    if detail is not None:
        iu["detail"] = detail
    return {"type": "image_url", "image_url": iu}


# ── 치수 파싱 ────────────────────────────────────────────────────────

def test_png_dims_parsed():
    assert image_dims_from_data_url(_png_url(640, 480)) == (640, 480)


def test_jpeg_dims_parsed():
    assert image_dims_from_data_url(_jpeg_url(1024, 768)) == (1024, 768)


def test_dims_none_for_non_image_payload():
    assert image_dims_from_data_url("data:image/png;base64," + "A" * 1000) is None


def test_dims_none_for_garbage():
    assert image_dims_from_data_url("not a data url") is None
    assert image_dims_from_data_url("") is None


# ── 타일링 공식 ──────────────────────────────────────────────────────

def test_high_detail_tiles_small_image():
    # 512x512 → 1타일: 85 + 170 = 255
    assert high_detail_tokens(512, 512) == 85 + 170 * 1


def test_high_detail_scales_shortest_side_to_768():
    # 1568x882 → 짧은 변 768 스케일 → 약 1365x768 → 3x2=6타일
    assert high_detail_tokens(1568, 882) == 85 + 170 * 6


def test_high_detail_zero_returns_default():
    assert high_detail_tokens(0, 0) == _DEFAULT_HIGH_TOKENS


# ── 블록 추정 ────────────────────────────────────────────────────────

def test_low_detail_fixed_cost():
    block = _img_block(_png_url(1920, 1080), detail="low")
    assert image_block_tokens(block) == _LOW_DETAIL_TOKENS


def test_high_detail_uses_dims():
    block = _img_block(_png_url(512, 512), detail="high")
    assert image_block_tokens(block) == 255


def test_missing_detail_treated_as_high():
    block = _img_block(_png_url(512, 512))  # detail 없음
    assert image_block_tokens(block) == 255


def test_unparseable_image_uses_default():
    block = _img_block("data:image/png;base64," + "A" * 5000, detail="high")
    assert image_block_tokens(block) == _DEFAULT_HIGH_TOKENS


# ── 텍스트·메시지 합산 ───────────────────────────────────────────────

def test_estimate_text_fallback_when_no_tiktoken():
    # tiktoken 유무와 무관하게 빈 문자열은 0
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("abcd" * 10) > 0


def test_message_tokens_sums_text_and_image():
    msgs = [
        {"role": "user", "content": "안녕하세요 " * 20},
        {"role": "user", "content": [
            {"type": "text", "text": "확인"},
            _img_block(_png_url(512, 512), detail="high"),
        ]},
    ]
    total = estimate_message_tokens(msgs)
    # 이미지 255 + 텍스트 약간
    assert total >= 255
    assert total < 255 + 500


def test_message_tokens_counts_tool_call_arguments():
    msgs = [{"role": "assistant", "tool_calls": [
        {"id": "c1", "type": "function",
         "function": {"name": "t", "arguments": '{"q":"' + "x" * 400 + '"}'}},
    ]}]
    assert estimate_message_tokens(msgs) > 50


def test_huge_base64_not_proportional():
    """거대 base64 길이에 비례하지 않는다(과대계상 방지 — 기존 회귀)."""
    huge = _img_block("data:image/png;base64," + "A" * 100000, detail="high")
    assert image_block_tokens(huge) == _DEFAULT_HIGH_TOKENS  # < 2000
