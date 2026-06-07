import os

_active_override: str | None = None
_model_override: str | None = None

_ENV_KEY_MAP = {
    'openai': 'OPENAI_API_KEY',
    'internal': 'INTERNAL_API_KEY',
}


def _profiles() -> dict:
    return {
        'openai': {
            'base_url': os.environ.get('LLM_OPENAI_BASE_URL', 'https://api.openai.com/v1'),
            'model': os.environ.get('LLM_OPENAI_MODEL', 'gpt-4o'),
        },
        'internal': {
            'base_url': os.environ.get('LLM_INTERNAL_BASE_URL', ''),
            'model': os.environ.get('LLM_INTERNAL_MODEL', ''),
        },
    }


def get_active() -> str:
    return _active_override or os.environ.get('LLM_ACTIVE', 'openai')


def active_llm() -> dict:
    active = get_active()
    profiles = _profiles()
    if active not in profiles:
        raise ValueError(f"존재하지 않는 프로파일: {active}")
    profile = dict(profiles[active])

    env_key = _ENV_KEY_MAP.get(active, f"{active.upper()}_API_KEY")
    api_key = os.environ.get(env_key, '')
    if not api_key:
        raise RuntimeError(f"환경변수 {env_key} 가 설정되지 않았습니다.")
    profile['api_key'] = api_key
    return profile


def list_profiles() -> list[str]:
    return list(_profiles().keys())


def set_active_profile(name: str) -> None:
    global _active_override, _model_override
    if name not in _profiles():
        raise ValueError(f"존재하지 않는 프로파일: {name}")
    _active_override = name
    # 모델은 프로파일에 종속되므로 프로파일 전환 시 오버라이드 초기화
    _model_override = None


# ── 모델 선택 (개선 아이디어 D) ───────────────────────────────

def get_model_override() -> str | None:
    return _model_override


def set_model(name: str | None) -> None:
    """현재 프로파일에서 사용할 모델을 런타임으로 지정한다. None이면 기본값으로 복귀."""
    global _model_override
    _model_override = name or None


def env_model_presets() -> list[str]:
    """`.env`의 LLM_{PROFILE}_MODELS(콤마 구분)에서 모델 프리셋 목록을 읽는다."""
    active = get_active()
    raw = os.environ.get(f'LLM_{active.upper()}_MODELS', '')
    return [m.strip() for m in raw.split(',') if m.strip()]
