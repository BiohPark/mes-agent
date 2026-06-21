"""업무타입 옵트인 → 하네스 라우팅 결정 단위 테스트.

server._should_use_harness가 ① /chat의 명시적 harness_mode 플래그와
② 업무타입 설정의 harness 옵트인을 모두 반영하되, HARNESS_ENABLED가 꺼져 있으면
항상 기존 generate() 경로를 쓰도록(I6 기본 비활성) 검증한다.
"""

import agent.server as server


def test_optin_task_type_routes_to_harness(monkeypatch):
    monkeypatch.setattr(server, "HARNESS_ENABLED", True)
    # syncade는 설정상 harness:true → 명시 플래그 없이도 하네스 경로
    assert server._should_use_harness(harness_mode=False, task_type="syncade") is True


def test_explicit_flag_routes_to_harness(monkeypatch):
    monkeypatch.setattr(server, "HARNESS_ENABLED", True)
    assert server._should_use_harness(harness_mode=True, task_type="general") is True


def test_non_optin_task_without_flag_uses_generate(monkeypatch):
    monkeypatch.setattr(server, "HARNESS_ENABLED", True)
    assert server._should_use_harness(harness_mode=False, task_type="general") is False


def test_harness_disabled_globally_always_false(monkeypatch):
    """HARNESS_ENABLED=false면 옵트인·플래그와 무관하게 기존 경로(I6)."""
    monkeypatch.setattr(server, "HARNESS_ENABLED", False)
    assert server._should_use_harness(harness_mode=True, task_type="syncade") is False
    assert server._should_use_harness(harness_mode=False, task_type="syncade") is False


def test_empty_task_type_false(monkeypatch):
    monkeypatch.setattr(server, "HARNESS_ENABLED", True)
    assert server._should_use_harness(harness_mode=True, task_type="") is False
