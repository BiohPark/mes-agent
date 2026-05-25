import os

_active_override: str | None = None

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
    global _active_override
    if name not in _profiles():
        raise ValueError(f"존재하지 않는 프로파일: {name}")
    _active_override = name
