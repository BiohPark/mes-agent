from openai import OpenAI
from agent.config import active_llm


def get_client() -> OpenAI:
    cfg = active_llm()
    return OpenAI(base_url=cfg['base_url'], api_key=cfg['api_key'])


def get_model() -> str:
    return active_llm()['model']
