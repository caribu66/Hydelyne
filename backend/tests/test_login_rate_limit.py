"""Security regression tests: login brute-force rate limiting."""

from unittest.mock import AsyncMock

import pytest

from app.services.cache import cache_service

LOGIN_MUTATION = """
    mutation Login($email: String!, $password: String!) {
        login(email: $email, password: $password) { success token }
    }
"""


@pytest.mark.asyncio
async def test_login_rate_limited_after_5_attempts(client, monkeypatch):
    """After 5 logins in 5 min, the 6th must return 429 RATE_LIMITED."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(
            return_value={
                "token": "tok",
                "user": {"id": "test-id", "full_name": "Test", "email": "test@example.com"},
            }
        ),
    )

    call_count = {"n": 0}

    async def fake_increment(key, window):
        call_count["n"] += 1
        return call_count["n"]

    monkeypatch.setattr(
        "app.services.cache.cache_service.is_redis_available", AsyncMock(return_value=True)
    )
    monkeypatch.setattr("app.services.cache.cache_service.increment_rate_limit", fake_increment)

    statuses = []
    for i in range(6):
        response = await client.post(
            "/graphql",
            json={
                "query": LOGIN_MUTATION,
                "variables": {"email": "test@example.com", "password": "pass"},
            },
        )
        if "errors" in response.json():
            for err in response.json()["errors"]:
                if err.get("extensions", {}).get("code") == "RATE_LIMITED":
                    statuses.append("rate_limited")
                    break
            else:
                statuses.append("other_error")
        else:
            statuses.append("ok")

    # First 5 should succeed, 6th should be rate limited
    assert statuses[:5] == ["ok"] * 5
    assert statuses[5] == "rate_limited"


@pytest.mark.asyncio
async def test_login_rate_limit_not_triggered_when_redis_unavailable(client, monkeypatch):
    """If Redis is down, login should still work (rate limit is best-effort)."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(
            return_value={
                "token": "tok",
                "user": {"id": "test-id", "full_name": "Test", "email": "test@example.com"},
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.cache.cache_service.is_redis_available", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        "app.services.cache.cache_service.increment_rate_limit", AsyncMock(return_value=None)
    )

    response = await client.post(
        "/graphql",
        json={
            "query": LOGIN_MUTATION,
            "variables": {"email": "test@example.com", "password": "pass"},
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]["login"]
    assert data["success"] is True


@pytest.mark.asyncio
async def test_login_rate_limit_canonicalizes_email_whitespace(client, monkeypatch):
    """Whitespace variants must share one brute-force rate-limit bucket."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(
            return_value={
                "token": "tok",
                "user": {"id": "test-id", "full_name": "Test", "email": "test@example.com"},
            }
        ),
    )
    seen_keys = []

    async def fake_increment(key, window):
        seen_keys.append(key)
        return 1

    monkeypatch.setattr(
        "app.services.cache.cache_service.is_redis_available", AsyncMock(return_value=True)
    )
    monkeypatch.setattr("app.services.cache.cache_service.increment_rate_limit", fake_increment)

    for email in (" test@example.com ", "test@example.com"):
        response = await client.post(
            "/graphql",
            json={
                "query": LOGIN_MUTATION,
                "variables": {"email": email, "password": "pass"},
            },
        )
        assert response.json()["data"]["login"]["success"] is True

    assert len(seen_keys) == 2
    assert seen_keys[0] == seen_keys[1]


@pytest.mark.asyncio
async def test_rate_limit_repairs_counter_when_initial_expiry_failed(monkeypatch):
    """A counter without TTL must not become a permanent rate-limit lockout."""

    class FakeRedis:
        def __init__(self):
            self.expire_calls = []

        async def incr(self, key):
            assert key == "login:test"
            return 2

        async def ttl(self, key):
            assert key == "login:test"
            return -1

        async def expire(self, key, seconds):
            self.expire_calls.append((key, seconds))
            return True

    redis = FakeRedis()
    monkeypatch.setattr(cache_service, "_get_redis", AsyncMock(return_value=redis))

    assert await cache_service.increment_rate_limit("login:test", 300) == 2
    assert redis.expire_calls == [("login:test", 300)]
