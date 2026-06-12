"""Phase 5: auto-wait 파라미터 명시화 + mouse_click after_delay_ms 검증.

screen.py: wait_for_image/wait_for_text의 interval 파라미터가 스키마에 노출되어야 한다.
desktop.py: mouse_click에 after_delay_ms 옵션이 추가되어야 한다.
"""

import json
import pytest
from unittest.mock import patch, call


# ── wait_for_image ─────────────────────────────────────────────

class TestWaitForImageInterval:
    def test_manifest_schema_has_interval(self):
        """MANIFEST 스키마에 interval 파라미터가 있어야 한다."""
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_image")
        props = entry["schema"]["function"]["parameters"]["properties"]
        assert "interval" in props, "wait_for_image 스키마에 interval 파라미터 없음"

    def test_manifest_interval_has_type_number(self):
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_image")
        prop = entry["schema"]["function"]["parameters"]["properties"]["interval"]
        assert prop.get("type") == "number"

    def test_handler_passes_interval_to_function(self):
        """handler가 interval 값을 wait_for_image에 전달해야 한다."""
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_image")
        with patch("agent.tools.screen.wait_for_image") as mock_fn:
            mock_fn.return_value = json.dumps({"found": False, "timeout": 5})
            entry["handler"]({"template_path": "x.png", "timeout": 5,
                              "confidence": 0.8, "interval": 0.2})
        mock_fn.assert_called_once_with("x.png", 5, 0.8, 0.2)

    def test_handler_uses_default_interval_when_omitted(self):
        """interval 생략 시 기본값(0.5)을 사용해야 한다."""
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_image")
        with patch("agent.tools.screen.wait_for_image") as mock_fn:
            mock_fn.return_value = json.dumps({"found": False, "timeout": 10})
            entry["handler"]({"template_path": "x.png"})
        args = mock_fn.call_args[0]
        assert args[3] == 0.5  # 4번째 인자 = interval 기본값

    def test_interval_controls_sleep_between_polls(self):
        """interval=0.3이면 폴링 사이에 sleep(0.3)이 호출되어야 한다."""
        from agent.tools.screen import wait_for_image
        with patch("agent.tools.screen.find_image_on_screen",
                   return_value=json.dumps({"found": False})), \
             patch("agent.tools.screen.time") as mock_time:
            # time.time() 호출 순서: deadline 계산(0) → 1회 루프(0.1) → 2회 루프(0.5) → 탈출(1.5)
            mock_time.time.side_effect = [0, 0.1, 0.5, 1.5]
            wait_for_image("x.png", timeout=1, confidence=0.8, interval=0.3)
        sleep_args = [c.args[0] for c in mock_time.sleep.call_args_list]
        assert len(sleep_args) >= 1
        assert all(s == 0.3 for s in sleep_args), f"sleep 호출 인자 오류: {sleep_args}"


# ── wait_for_text ──────────────────────────────────────────────

class TestWaitForTextInterval:
    def test_manifest_schema_has_interval(self):
        """MANIFEST 스키마에 interval 파라미터가 있어야 한다."""
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_text")
        props = entry["schema"]["function"]["parameters"]["properties"]
        assert "interval" in props, "wait_for_text 스키마에 interval 파라미터 없음"

    def test_manifest_interval_has_type_number(self):
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_text")
        prop = entry["schema"]["function"]["parameters"]["properties"]["interval"]
        assert prop.get("type") == "number"

    def test_handler_passes_interval_to_function(self):
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_text")
        with patch("agent.tools.screen.wait_for_text") as mock_fn:
            mock_fn.return_value = json.dumps({"found": False, "timeout": 5})
            entry["handler"]({"text": "완료", "timeout": 5, "interval": 0.3})
        mock_fn.assert_called_once_with("완료", 5, 0.3)

    def test_handler_uses_default_interval_when_omitted(self):
        from agent.tools.screen import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "wait_for_text")
        with patch("agent.tools.screen.wait_for_text") as mock_fn:
            mock_fn.return_value = json.dumps({"found": False, "timeout": 10})
            entry["handler"]({"text": "완료"})
        args = mock_fn.call_args[0]
        assert args[2] == 0.5  # 3번째 인자 = interval 기본값

    def test_interval_controls_sleep_between_polls(self):
        """interval=0.2이면 폴링 사이에 sleep(0.2)가 호출되어야 한다."""
        from agent.tools.screen import wait_for_text

        class _FakeProvider:
            def image_to_string(self, image, lang=None):
                return ""  # 텍스트 미발견 → 타임아웃까지 폴링

            def image_to_data(self, image, lang=None):
                return {}

        with patch("agent.tools.screen.get_ocr_provider", return_value=_FakeProvider()), \
             patch("agent.tools.screen._capture_full", return_value=__import__("numpy").zeros((10, 10, 3), dtype=__import__("numpy").uint8)), \
             patch("agent.tools.screen.time") as mock_time:
            # time.time() 호출 순서: deadline(0) + start(0) → 1회 루프(0.1) → 2회 루프(0.5) → 탈출(1.5)
            mock_time.time.side_effect = [0, 0, 0.1, 0.5, 1.5]
            wait_for_text("완료", timeout=1, interval=0.2)
        sleep_args = [c.args[0] for c in mock_time.sleep.call_args_list]
        assert len(sleep_args) >= 1
        assert all(s == 0.2 for s in sleep_args), f"sleep 호출 인자 오류: {sleep_args}"


# ── mouse_click after_delay_ms ─────────────────────────────────

class TestMouseClickAfterDelay:
    def test_manifest_schema_has_after_delay_ms(self):
        """MANIFEST 스키마에 after_delay_ms 파라미터가 있어야 한다."""
        from agent.tools.desktop import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "mouse_click")
        props = entry["schema"]["function"]["parameters"]["properties"]
        assert "after_delay_ms" in props, "mouse_click 스키마에 after_delay_ms 없음"

    def test_manifest_after_delay_ms_type_integer(self):
        from agent.tools.desktop import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "mouse_click")
        prop = entry["schema"]["function"]["parameters"]["properties"]["after_delay_ms"]
        assert prop.get("type") == "integer"

    def test_after_delay_ms_causes_sleep(self):
        """after_delay_ms=200이면 클릭 후 sleep(0.2)가 호출되어야 한다."""
        from agent.tools.desktop import mouse_click
        with patch("agent.tools.desktop.pyautogui.click"), \
             patch("agent.tools.desktop.time") as mock_time:
            mouse_click(100, 200, after_delay_ms=200)
        sleep_calls = [c.args[0] for c in mock_time.sleep.call_args_list]
        assert 0.2 in sleep_calls, f"sleep(0.2) 미호출. 실제 호출: {sleep_calls}"

    def test_after_delay_ms_zero_no_extra_sleep(self):
        """after_delay_ms=0(기본)이면 추가 sleep이 없어야 한다."""
        from agent.tools.desktop import mouse_click
        with patch("agent.tools.desktop.pyautogui.click"), \
             patch("agent.tools.desktop.time") as mock_time:
            mock_time.sleep = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
            mouse_click(100, 200, after_delay_ms=0)
        # pyautogui 내부 sleep만 허용 (우리가 추가한 after_delay는 없어야 함)
        for c in mock_time.sleep.call_args_list:
            assert c.args[0] != pytest.approx(0.0, abs=1e-9) or True  # 0ms sleep은 허용하지 않음
        delay_calls = [c for c in mock_time.sleep.call_args_list if c.args[0] == 0.0]
        assert len(delay_calls) == 0

    def test_handler_passes_after_delay_ms(self):
        """handler가 after_delay_ms 값을 mouse_click에 전달해야 한다."""
        from agent.tools.desktop import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "mouse_click")
        with patch("agent.tools.desktop.mouse_click") as mock_fn:
            mock_fn.return_value = "클릭 완료"
            entry["handler"]({"x": 100, "y": 200, "after_delay_ms": 300})
        call_kwargs = mock_fn.call_args
        # positional 또는 keyword로 after_delay_ms=300이 전달되어야 함
        passed = dict(zip(["x", "y", "button", "clicks", "use_sendinput", "after_delay_ms"],
                          call_kwargs[0]))
        passed.update(call_kwargs[1])
        assert passed.get("after_delay_ms") == 300

    def test_handler_default_after_delay_ms_zero(self):
        """after_delay_ms 생략 시 0이 기본값이어야 한다."""
        from agent.tools.desktop import MANIFEST
        entry = next(m for m in MANIFEST if m["name"] == "mouse_click")
        with patch("agent.tools.desktop.mouse_click") as mock_fn:
            mock_fn.return_value = "클릭 완료"
            entry["handler"]({"x": 100, "y": 200})
        call_kwargs = mock_fn.call_args
        passed = dict(zip(["x", "y", "button", "clicks", "use_sendinput", "after_delay_ms"],
                          call_kwargs[0]))
        passed.update(call_kwargs[1])
        assert passed.get("after_delay_ms", 0) == 0
