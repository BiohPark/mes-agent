"""M5 모델별 컨텍스트 예산 단위 테스트.

모델명→윈도우 조회: .env 정확값 > 내장 맵(최장 키) > 폴백. 미지 모델도 항상 양수.
"""

import agent.config as config
from agent.config import get_context_window, DEFAULT_CONTEXT_TOKENS


def test_known_models_mapped():
    assert get_context_window("gpt-4o") == 128_000
    assert get_context_window("gpt-4o-2024-08-06") == 128_000
    assert get_context_window("gpt-3.5-turbo") == 16_385
    assert get_context_window("gpt-4.1") == 1_047_576


def test_longest_key_wins_over_substring():
    # 'gpt-4o' 는 'gpt-4'(8192) 가 아니라 'gpt-4o'(128k) 로 매칭돼야 한다
    assert get_context_window("gpt-4o") == 128_000
    # 'gpt-4o-mini' 는 'gpt-4o-mini' 키로
    assert get_context_window("gpt-4o-mini") == 128_000
    # 순수 gpt-4 계열은 8192
    assert get_context_window("gpt-4-0613") == 8_192


def test_unknown_model_uses_default():
    assert get_context_window("totally-unknown-model") == DEFAULT_CONTEXT_TOKENS
    assert get_context_window("gpt-5.4-nano") == 100_000  # 미지 → 보수적 폴백


def test_env_exact_override_wins(monkeypatch):
    monkeypatch.setattr(config, "get_active", lambda: "openai")
    monkeypatch.setenv("LLM_OPENAI_CONTEXT_TOKENS", "8000")
    # 맵에 있는 모델이어도 .env 정확값이 우선
    assert get_context_window("gpt-4o") == 8000
    # 미지 모델도 정확값 적용
    assert get_context_window("gpt-5.4-nano") == 8000


def test_env_default_fallback_override(monkeypatch):
    monkeypatch.setattr(config, "get_active", lambda: "openai")
    monkeypatch.delenv("LLM_OPENAI_CONTEXT_TOKENS", raising=False)
    monkeypatch.setenv("LLM_DEFAULT_CONTEXT_TOKENS", "32000")
    assert get_context_window("unknown-x") == 32000


def test_invalid_env_values_ignored(monkeypatch):
    monkeypatch.setattr(config, "get_active", lambda: "openai")
    monkeypatch.setenv("LLM_OPENAI_CONTEXT_TOKENS", "not-a-number")
    monkeypatch.delenv("LLM_DEFAULT_CONTEXT_TOKENS", raising=False)
    # 잘못된 값은 무시하고 맵/폴백으로
    assert get_context_window("gpt-4o") == 128_000
    assert get_context_window("unknown") == DEFAULT_CONTEXT_TOKENS


def test_always_positive(monkeypatch):
    monkeypatch.setattr(config, "get_active", lambda: "openai")
    monkeypatch.setenv("LLM_OPENAI_CONTEXT_TOKENS", "-5")
    # 음수는 무시 → 맵/폴백
    assert get_context_window("gpt-4o") == 128_000
    assert get_context_window("") == DEFAULT_CONTEXT_TOKENS
