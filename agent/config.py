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


# ── 모델별 컨텍스트 예산 (백로그 M5) ──────────────────────────
# 컨텍스트 윈도우는 모델마다 다르다. 하드코딩 대신 모델명으로 윈도우를 조회한다.
# 우선순위: .env LLM_{PROFILE}_CONTEXT_TOKENS(정확값 직접 지정) > 내장 맵(known 모델) > 폴백.
# 미지의 모델(예: gpt-5.4-nano 등 사내/신규)은 .env 로 정확값을 잡는 것을 권장한다 — 추정 오차는
# 런타임 400 점진적 복구(M4)가 최종 보증한다.
DEFAULT_CONTEXT_TOKENS = 128_000

# 키는 부분문자열로 매칭하며, 더 구체적인(긴) 키가 우선한다(예: 'gpt-4o'가 'gpt-4'보다 우선).
MODEL_CONTEXT_WINDOWS = {
    'gpt-3.5-turbo': 16_385,
    'gpt-4-turbo': 128_000,
    'gpt-4o-mini': 128_000,
    'gpt-4o': 128_000,
    'gpt-4.1': 1_047_576,
    'gpt-4': 8_192,
    'o1-mini': 128_000,
    'o1': 200_000,
    'o3-mini': 200_000,
    'o3': 200_000,
    'o4-mini': 200_000,
}


def get_context_window(model: str) -> int:
    """모델의 컨텍스트 윈도우(토큰)를 반환한다.

    .env LLM_{PROFILE}_CONTEXT_TOKENS(정확값) → 내장 맵(최장 키 매칭) → LLM_DEFAULT_CONTEXT_TOKENS
    또는 DEFAULT_CONTEXT_TOKENS 폴백 순. 잘못된 값/미지 모델에도 항상 양의 정수를 보장한다.
    """
    active = get_active()
    env_exact = os.environ.get(f'LLM_{active.upper()}_CONTEXT_TOKENS', '').strip()
    if env_exact:
        try:
            v = int(env_exact)
            if v > 0:
                return v
        except ValueError:
            pass

    m = (model or '').lower()
    best_key = None
    for key in MODEL_CONTEXT_WINDOWS:
        if key in m and (best_key is None or len(key) > len(best_key)):
            best_key = key
    if best_key is not None:
        return MODEL_CONTEXT_WINDOWS[best_key]

    fallback = os.environ.get('LLM_DEFAULT_CONTEXT_TOKENS', '').strip()
    if fallback:
        try:
            v = int(fallback)
            if v > 0:
                return v
        except ValueError:
            pass
    return DEFAULT_CONTEXT_TOKENS
