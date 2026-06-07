"""LLM 프로파일 설정 단위 테스트."""

import pytest
import agent.config as cfg


class TestGetActive:
    def test_defaults_to_openai(self, monkeypatch):
        monkeypatch.delenv("LLM_ACTIVE", raising=False)
        cfg._active_override = None
        assert cfg.get_active() == "openai"

    def test_env_var_respected(self, monkeypatch):
        monkeypatch.setenv("LLM_ACTIVE", "internal")
        cfg._active_override = None
        assert cfg.get_active() == "internal"

    def test_override_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("LLM_ACTIVE", "openai")
        cfg._active_override = "internal"
        assert cfg.get_active() == "internal"


class TestSetActiveProfile:
    def test_switch_to_internal(self):
        cfg.set_active_profile("internal")
        assert cfg.get_active() == "internal"

    def test_switch_back_to_openai(self):
        cfg.set_active_profile("internal")
        cfg.set_active_profile("openai")
        assert cfg.get_active() == "openai"

    def test_invalid_profile_raises_value_error(self):
        with pytest.raises(ValueError, match="존재하지 않는 프로파일"):
            cfg.set_active_profile("nonexistent")

    def test_override_cleared_does_not_raise(self):
        """_active_override = None 상태에서 get_active()는 env를 읽어야 한다."""
        cfg._active_override = None
        result = cfg.get_active()
        assert result in ("openai", "internal")


class TestListProfiles:
    def test_returns_known_profiles(self):
        profiles = cfg.list_profiles()
        assert "openai" in profiles
        assert "internal" in profiles

    def test_returns_list(self):
        assert isinstance(cfg.list_profiles(), list)


class TestActiveLlm:
    def test_returns_required_keys(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("LLM_OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("LLM_OPENAI_MODEL", "gpt-4o")
        cfg._active_override = "openai"
        result = cfg.active_llm()
        assert result["api_key"] == "sk-test"
        assert result["base_url"] == "https://api.openai.com/v1"
        assert result["model"] == "gpt-4o"

    def test_missing_api_key_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg._active_override = "openai"
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            cfg.active_llm()

    def test_invalid_active_profile_raises_value_error(self, monkeypatch):
        cfg._active_override = "ghost"
        with pytest.raises(ValueError, match="존재하지 않는 프로파일"):
            cfg.active_llm()
