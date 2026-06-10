"""멀티모달 화면 이해(capture_screen) 단위 테스트.

capture_screen 의 봉투 형식과 parse_capture_envelope 파서의 정합성을 검증한다.
실제 스크린샷/LLM 호출은 하지 않는다(파서는 순수 함수).
"""

import base64
import json

from agent.tools.vision import parse_capture_envelope


def _envelope(b64="aGVsbG8=", prompt="", note="캡처됨"):
    return json.dumps({
        "__capture__": True,
        "image_b64": b64,
        "prompt": prompt,
        "note": note,
    })


def test_parse_recognizes_capture_envelope():
    env = _envelope(prompt="진행률 확인")
    parsed = parse_capture_envelope(env)
    assert parsed is not None
    assert parsed["image_b64"] == "aGVsbG8="
    assert parsed["prompt"] == "진행률 확인"
    assert parsed["note"] == "캡처됨"


def test_parse_returns_none_for_plain_tool_result():
    assert parse_capture_envelope('{"ok": true}') is None
    assert parse_capture_envelope('{"analysis": "표가 보입니다"}') is None


def test_parse_returns_none_for_non_json():
    assert parse_capture_envelope("그냥 텍스트 결과") is None
    assert parse_capture_envelope("") is None


def test_parse_requires_image_payload():
    # 마커만 있고 이미지가 없으면 봉투로 보지 않는다(잘못된 주입 방지)
    assert parse_capture_envelope(json.dumps({"__capture__": True})) is None


def test_capture_screen_envelope_roundtrip(monkeypatch):
    """capture_screen 출력이 parse_capture_envelope 로 그대로 복원된다."""
    import agent.tools.vision as vision

    monkeypatch.setenv("VISION_ENABLED", "true")
    fake_png = b"\x89PNG\r\n\x1a\nFAKEDATA"
    monkeypatch.setattr(vision, "_screenshot", lambda *a, **k: fake_png)

    out = vision.capture_screen(prompt="버튼이 떴는지 확인")
    parsed = parse_capture_envelope(out)
    assert parsed is not None
    assert base64.b64decode(parsed["image_b64"]) == fake_png
    assert parsed["prompt"] == "버튼이 떴는지 확인"


def test_capture_screen_disabled_returns_error_not_envelope(monkeypatch):
    """VISION_ENABLED=false 면 봉투가 아니라 error 를 반환해 주입을 막는다."""
    import agent.tools.vision as vision

    monkeypatch.setenv("VISION_ENABLED", "false")
    out = vision.capture_screen()
    assert parse_capture_envelope(out) is None
    assert json.loads(out).get("error")


# ── M1 적응형 이미지 다이어트 ────────────────────────────────────────

def _real_png(w: int, h: int) -> bytes:
    """테스트용 실제 PNG 바이트(단색)."""
    import io as _io
    from PIL import Image
    buf = _io.BytesIO()
    Image.new("RGB", (w, h), (123, 222, 64)).save(buf, format="PNG")
    return buf.getvalue()


def test_prepare_downscales_long_edge(monkeypatch):
    """긴 변이 VISION_MAX_EDGE 를 넘으면 비율 유지 축소한다."""
    import agent.tools.vision as vision
    monkeypatch.setenv("VISION_MAX_EDGE", "1000")
    monkeypatch.setenv("VISION_IMAGE_FORMAT", "png")  # 치수 검증을 위해 png

    out = vision._prepare_capture_image(_real_png(2000, 1000))
    assert max(out["width"], out["height"]) == 1000
    assert out["width"] == 1000 and out["height"] == 500  # 2:1 비율 유지


def test_prepare_no_upscale_when_small(monkeypatch):
    """긴 변이 한계 이하이면 확대하지 않는다."""
    import agent.tools.vision as vision
    monkeypatch.setenv("VISION_MAX_EDGE", "1568")
    monkeypatch.setenv("VISION_IMAGE_FORMAT", "png")

    out = vision._prepare_capture_image(_real_png(800, 600))
    assert out["width"] == 800 and out["height"] == 600


def test_prepare_jpeg_is_smaller_and_tagged(monkeypatch):
    """JPEG 인코딩이 mime 를 image/jpeg 로 표기하고 PNG 보다 작다(스크린샷류)."""
    import agent.tools.vision as vision
    png = _real_png(1200, 900)

    monkeypatch.setenv("VISION_IMAGE_FORMAT", "jpeg")
    monkeypatch.setenv("VISION_JPEG_QUALITY", "80")
    monkeypatch.setenv("VISION_MAX_EDGE", "0")  # 다운스케일 영향 배제, 압축만 비교
    jpeg = vision._prepare_capture_image(png)
    assert jpeg["mime"] == "image/jpeg"

    # JPEG 헤더(FFD8) 확인
    assert base64.b64decode(jpeg["image_b64"])[:2] == b"\xff\xd8"


def test_prepare_fallback_on_invalid_bytes(monkeypatch):
    """디코딩 불가한 바이트는 원본 PNG 로 통과(주입 자체는 유지)."""
    import agent.tools.vision as vision
    bad = b"\x89PNG\r\n\x1a\nNOTREALLYANIMAGE"
    out = vision._prepare_capture_image(bad)
    assert base64.b64decode(out["image_b64"]) == bad
    assert out["mime"] == "image/png"


def test_resolve_detail_rules():
    from agent.tools.vision import resolve_detail
    assert resolve_detail("auto", near_limit=False) == "auto"
    assert resolve_detail("high", near_limit=False) == "high"
    # 임계 근접이면 high/auto 를 low 로 강등
    assert resolve_detail("high", near_limit=True) == "low"
    assert resolve_detail("auto", near_limit=True) == "low"
    assert resolve_detail("low", near_limit=True) == "low"
    # off 는 detail 필드 자체를 제거(None)
    assert resolve_detail("off", near_limit=False) is None
    assert resolve_detail("off", near_limit=True) is None
    # 알 수 없는 값은 auto 취급
    assert resolve_detail("weird", near_limit=False) == "auto"


def test_build_capture_message_uses_envelope_mime_and_detail():
    from agent.tools.vision import build_capture_message
    env = {"image_b64": "QUJD", "mime": "image/jpeg", "detail": "high", "prompt": "확인해"}

    msg = build_capture_message(env, near_limit=False)
    assert msg["role"] == "user"
    blocks = msg["content"]
    assert blocks[0] == {"type": "text", "text": "확인해"}
    iu = blocks[1]["image_url"]
    assert iu["url"] == "data:image/jpeg;base64,QUJD"
    assert iu["detail"] == "high"


def test_build_capture_message_adaptive_downgrade():
    from agent.tools.vision import build_capture_message
    env = {"image_b64": "QUJD", "mime": "image/png", "detail": "high"}
    msg = build_capture_message(env, near_limit=True)
    assert msg["content"][1]["image_url"]["detail"] == "low"


def test_build_capture_message_off_omits_detail():
    from agent.tools.vision import build_capture_message
    env = {"image_b64": "QUJD", "mime": "image/png", "detail": "off"}
    iu = build_capture_message(env)["content"][1]["image_url"]
    assert "detail" not in iu


def test_capture_screen_envelope_carries_mime_and_detail(monkeypatch):
    """capture_screen 봉투가 mime·detail·치수를 포함한다(M1)."""
    import agent.tools.vision as vision
    monkeypatch.setenv("VISION_ENABLED", "true")
    monkeypatch.setenv("VISION_IMAGE_FORMAT", "jpeg")
    monkeypatch.setenv("VISION_DETAIL", "auto")
    monkeypatch.setenv("VISION_MAX_EDGE", "1568")
    monkeypatch.setattr(vision, "_screenshot", lambda *a, **k: _real_png(1920, 1080))

    parsed = parse_capture_envelope(vision.capture_screen(prompt="x"))
    assert parsed is not None
    assert parsed["mime"] == "image/jpeg"
    assert parsed["detail"] == "auto"
    assert max(parsed["width"], parsed["height"]) == 1568
