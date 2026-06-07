"""보안 게이트(S1/S3) 통합 테스트 — 인증 토큰 + 원격 Origin 차단."""

import pytest


@pytest.mark.asyncio
async def test_remote_origin_blocked(client):
    """악성 웹페이지發 요청(원격 http Origin)은 403으로 차단."""
    res = await client.get("/profile", headers={"Origin": "https://evil.example.com"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_localhost_origin_allowed(client):
    res = await client.get("/profile", headers={"Origin": "http://localhost:8000"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_no_origin_allowed(client):
    """Electron 렌더러(file://)는 Origin이 없거나 null — 허용."""
    res = await client.get("/profile")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_token_required_when_set(client, monkeypatch):
    monkeypatch.setattr("agent.server._AUTH_TOKEN", "s3cret")
    # 토큰 없음 → 401
    res = await client.get("/profile")
    assert res.status_code == 401
    # 헤더 토큰 정확 → 200
    res = await client.get("/profile", headers={"X-Auth-Token": "s3cret"})
    assert res.status_code == 200
    # 쿼리 토큰 정확 → 200 (EventSource용 경로)
    res = await client.get("/profile?token=s3cret")
    assert res.status_code == 200
    # 틀린 토큰 → 401
    res = await client.get("/profile", headers={"X-Auth-Token": "wrong"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_health_is_auth_free(client, monkeypatch):
    """/health는 토큰이 설정돼 있어도 무인증 허용 (서버 기동 확인용)."""
    monkeypatch.setattr("agent.server._AUTH_TOKEN", "s3cret")
    res = await client.get("/health")
    assert res.status_code == 200
