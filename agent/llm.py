from openai import OpenAI
from agent import config
from agent.config import active_llm


def get_client() -> OpenAI:
    cfg = active_llm()
    return OpenAI(base_url=cfg['base_url'], api_key=cfg['api_key'])


def get_model() -> str:
    # 런타임 모델 오버라이드(개선 아이디어 D)가 있으면 우선 사용
    return config.get_model_override() or active_llm()['model']


def list_available_models() -> dict:
    """현재 프로파일에서 선택 가능한 모델 목록을 반환한다.

    동적 우선: OpenAI 호환 /v1/models API로 조회를 시도하고,
    실패하면 .env의 LLM_{PROFILE}_MODELS 프리셋으로 폴백한다.
    """
    current = get_model()
    default = active_llm()['model']
    models: list[str] = []
    source = 'preset'

    # 1) 동적 조회 시도 (폐쇄망에서 멈추지 않도록 짧은 타임아웃)
    try:
        cfg = active_llm()
        client = OpenAI(base_url=cfg['base_url'], api_key=cfg['api_key'], timeout=3.0, max_retries=0)
        resp = client.models.list()
        models = [m.id for m in resp.data]
        if models:
            source = 'dynamic'
    except Exception:
        models = []

    # 2) 폴백: .env 프리셋
    if not models:
        models = config.env_model_presets()

    # 3) 기본 모델과 현재 모델은 항상 포함
    for m in (default, current):
        if m and m not in models:
            models.insert(0, m)

    # 중복 제거(순서 유지)
    seen = set()
    uniq = [m for m in models if not (m in seen or seen.add(m))]

    return {"current": current, "default": default, "models": uniq, "source": source}
