"""업무타입 하네스 옵트인 단위 테스트.

도메인 하네스 팩 v1: 업무 설정에 harness/verify_prompt 필드를 추가하고,
업무타입 단위로 Executor→Reviewer 자기검증 루프를 옵트인하는 헬퍼를 검증한다.
순수 로직 — 네트워크/LLM 없음.
"""

from agent.obsidian_session import (
    get_task_configs,
    task_type_harness_enabled,
    task_type_verify_prompt,
)


class TestTaskConfigSchema:
    def test_syncade_opts_into_harness(self):
        """첫 도메인 버티컬(syncade)은 harness:true로 자기검증 루프를 사용한다."""
        cfg = get_task_configs()["syncade"]
        assert cfg.get("harness") is True

    def test_syncade_has_verify_prompt(self):
        cfg = get_task_configs()["syncade"]
        assert isinstance(cfg.get("verify_prompt", ""), str)
        assert cfg.get("verify_prompt", "").strip() != ""

    def test_general_defaults_to_no_harness(self):
        """옵트인하지 않은 업무타입은 harness 필드가 없거나 false다(하위호환)."""
        cfg = get_task_configs()["general"]
        assert cfg.get("harness", False) is False


class TestHarnessEnabledHelper:
    def test_enabled_for_syncade(self):
        assert task_type_harness_enabled("syncade") is True

    def test_disabled_for_general(self):
        assert task_type_harness_enabled("general") is False

    def test_unknown_task_type_is_false(self):
        assert task_type_harness_enabled("does-not-exist") is False

    def test_empty_task_type_is_false(self):
        assert task_type_harness_enabled("") is False


class TestVerifyPromptHelper:
    def test_returns_prompt_for_syncade(self):
        assert task_type_verify_prompt("syncade").strip() != ""

    def test_blank_for_task_without_prompt(self):
        assert task_type_verify_prompt("general") == ""

    def test_blank_for_unknown(self):
        assert task_type_verify_prompt("does-not-exist") == ""
