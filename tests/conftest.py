"""
공유 픽스처 및 테스트 환경 설정.

이 모듈은 pytest가 가장 먼저 import하므로,
agent 모듈보다 먼저 환경변수를 세팅해 LLM·Vault 의존성을 차단한다.
"""

import os
import tempfile
import pytest

# ── 최소 환경변수 — agent 모듈 import 전에 반드시 설정 ──────────────
os.environ.setdefault("OPENAI_API_KEY", "test-key-placeholder")
os.environ.setdefault("LLM_ACTIVE", "openai")
os.environ.setdefault("LLM_OPENAI_BASE_URL", "http://test.invalid/v1")
os.environ.setdefault("LLM_OPENAI_MODEL", "gpt-test")
os.environ.setdefault("OBSIDIAN_VAULT_PATH", tempfile.mkdtemp(prefix="mes_test_"))
os.environ.setdefault("OBSIDIAN_HOST", "")
os.environ.setdefault("OBSIDIAN_API_KEY", "")


# ── 싱글턴 격리 ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_singletons():
    """각 테스트 전후로 모듈 레벨 싱글턴·오버라이드를 초기화해 테스트 격리를 보장한다."""
    import agent.obsidian_session as _obs
    import agent.config as _cfg
    _obs._instance = None
    _cfg._active_override = None
    yield
    _obs._instance = None
    _cfg._active_override = None


# ── Vault 픽스처 ──────────────────────────────────────────────────────

@pytest.fixture
def vault(tmp_path, monkeypatch):
    """테스트마다 격리된 임시 Vault 디렉토리를 제공한다."""
    import agent.obsidian_session as _obs
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _obs._instance = None
    yield tmp_path


# ── 가짜 LLM 클라이언트 ───────────────────────────────────────────────

class _FakeDelta:
    def __init__(self, content=None):
        self.content = content
        self.tool_calls = None


class _FakeChoice:
    def __init__(self, content=None, finish_reason=None):
        self.delta = _FakeDelta(content)
        self.finish_reason = finish_reason


class _FakeChunk:
    def __init__(self, content=None, finish_reason=None):
        self.choices = [_FakeChoice(content, finish_reason)]


class _FakeStream:
    def __iter__(self):
        yield _FakeChunk(content="테스트 응답입니다.")
        yield _FakeChunk(finish_reason="stop")


class _FakeCompletions:
    def create(self, **kwargs):
        return _FakeStream()


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class FakeLLMClient:
    def __init__(self):
        self.chat = _FakeChat()


@pytest.fixture
def mock_llm(monkeypatch):
    """server.py의 LLM 클라이언트를 가짜로 교체해 실제 API 호출을 차단한다."""
    monkeypatch.setattr("agent.server.get_client", lambda: FakeLLMClient())
    monkeypatch.setattr("agent.server.get_model", lambda: "gpt-test")


# ── 통합 테스트용 HTTP 클라이언트 ─────────────────────────────────────

@pytest.fixture
async def client(vault, mock_llm):
    """FastAPI 앱을 인메모리로 구동하는 비동기 테스트 클라이언트."""
    from httpx import AsyncClient, ASGITransport
    from agent.server import app
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
