"""M3: 토큰 추정 순수 로직.

`_estimate_tokens`가 이미지를 무조건 ~1000토큰 고정으로 세던 것을 대체한다.
- 텍스트: tiktoken 이 설치돼 있으면 실제 토큰화, 없으면 4-char≈1토큰 휴리스틱 폴백.
- 이미지: OpenAI 비전 타일링 공식(detail=low 고정, high/auto 는 치수 기반 타일 수×비용+base).
  치수는 data URL 헤더(PNG/JPEG)를 가볍게 파싱해 얻고, 미상이면 보수적 기본값을 쓴다.

폐쇄망에서 tiktoken 미반입이어도 동작하도록 순수 폴백을 보장한다(지연 import).
"""

from __future__ import annotations

import base64

# OpenAI 비전 타일링 상수 (gpt-4o 계열 기준)
_IMG_BASE_TOKENS = 85
_IMG_TILE_TOKENS = 170
_LOW_DETAIL_TOKENS = 85
# 치수 미상 high/auto 이미지의 기본 추정 (긴 변 ~1568 캡처 가정 ≈ 6타일)
_DEFAULT_HIGH_TOKENS = 1105
# data URL 헤더 파싱용 prefix 디코드 한도(바이트). JPEG SOF 마커까지 닿기에 충분.
_HEADER_BYTES = 16384

_encoder = None
_encoder_tried = False


def _get_encoder():
    """tiktoken 인코더를 1회 지연 로드한다(미설치/실패 시 None)."""
    global _encoder, _encoder_tried
    if _encoder_tried:
        return _encoder
    _encoder_tried = True
    try:
        import tiktoken
        _encoder = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _encoder = None
    return _encoder


def estimate_text_tokens(text: str) -> int:
    """텍스트 토큰 수: tiktoken 우선, 미설치 시 4-char≈1토큰 휴리스틱."""
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    return len(text) // 4


def _png_dims(data: bytes):
    # PNG: 8바이트 시그니처 + IHDR(길이4+타입4) 후 width(4)·height(4) big-endian
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        if w and h:
            return (w, h)
    return None


def _jpeg_dims(data: bytes):
    # JPEG: SOF 마커(0xFFC0~0xFFCF, C4/C8/CC 제외)에서 height·width 파싱
    n = len(data)
    if n < 4 or data[0] != 0xFF or data[1] != 0xD8:
        return None
    i = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in sof:
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            if w and h:
                return (w, h)
            return None
        if marker == 0xD8 or marker == 0xD9 or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        if seg_len <= 0:
            break
        i += 2 + seg_len
    return None


def image_dims_from_data_url(url: str):
    """data:<mime>;base64,<payload> 의 헤더 prefix만 디코드해 (w,h) 또는 None 반환."""
    if not url or "base64," not in url:
        return None
    payload = url.split("base64,", 1)[1]
    # 헤더에 필요한 만큼만 디코드(4의 배수로 자르고 패딩)
    chunk = payload[: (_HEADER_BYTES * 4 // 3 + 4)]
    chunk = chunk[: len(chunk) - (len(chunk) % 4)]
    try:
        data = base64.b64decode(chunk + "===", validate=False)
    except Exception:
        return None
    return _png_dims(data) or _jpeg_dims(data)


def high_detail_tokens(w: int, h: int) -> int:
    """OpenAI high-detail 타일 토큰: 2048 박스 맞춤 → 짧은 변 768 스케일 → 512 타일."""
    if w <= 0 or h <= 0:
        return _DEFAULT_HIGH_TOKENS
    # 1) 2048x2048 박스에 맞춤
    if max(w, h) > 2048:
        scale = 2048.0 / max(w, h)
        w, h = round(w * scale), round(h * scale)
    # 2) 짧은 변을 768로
    short = min(w, h)
    if short > 768:
        scale = 768.0 / short
        w, h = round(w * scale), round(h * scale)
    tiles = ((w + 511) // 512) * ((h + 511) // 512)
    return _IMG_BASE_TOKENS + _IMG_TILE_TOKENS * tiles


def image_block_tokens(block: dict) -> int:
    """image_url 블록 1개의 추정 토큰."""
    iu = (block.get("image_url") if isinstance(block, dict) else None) or {}
    detail = str(iu.get("detail") or "high").strip().lower()
    if detail == "low":
        return _LOW_DETAIL_TOKENS
    dims = image_dims_from_data_url(iu.get("url", ""))
    if dims is None:
        return _DEFAULT_HIGH_TOKENS
    return high_detail_tokens(*dims)


def estimate_message_tokens(messages: list) -> int:
    """메시지 리스트 전체의 추정 토큰(텍스트+이미지+tool_calls 인자)."""
    total = 0
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, str):
            total += estimate_text_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "image_url":
                    total += image_block_tokens(block)
                else:
                    total += estimate_text_tokens(block.get("text", ""))
        for tc in m.get("tool_calls") or []:
            total += estimate_text_tokens(tc.get("function", {}).get("arguments", ""))
    return total
