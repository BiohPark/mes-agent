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
