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
async def test_login_still_rate_limited_when_redis_unavailable(client, monkeypatch):
    """If Redis is down, logins keep working but brute-force protection must
    not disappear: the process-local fallback still rate-limits the 6th rapid
    attempt in the same window."""
    monkeypatch.setattr(
        "app.services.crew.auth_service.authenticate",
        AsyncMock(
            return_value={
                "token": "tok",
                "user": {"id": "test-id", "full_name": "Test", "email": "test@example.com"},
            }
        ),
    )
    cache_service._memory_rate_limits.clear()

    async def no_redis() -> object:
        raise ConnectionError("redis down")

    monkeypatch.setattr(cache_service, "_get_redis", no_redis)

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

    # First 5 succeed (availability preserved), 6th is still throttled.
    assert statuses[:5] == ["ok"] * 5
    assert statuses[5] == "rate_limited"


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
async def test_rate_limit_memory_fallback_resets_after_window(monkeypatch):
    """The process-local fallback must start a fresh window once the old one
    expires, or a Redis outage would permanently lock users out."""
    cache_service._memory_rate_limits.clear()

    async def no_redis() -> object:
        raise ConnectionError("redis down")

    monkeypatch.setattr(cache_service, "_get_redis", no_redis)

    assert await cache_service.increment_rate_limit("login:fallback-window", 300) == 1
    assert await cache_service.increment_rate_limit("login:fallback-window", 300) == 2

    # Simulate the window elapsing.
    count, _ = cache_service._memory_rate_limits["login:fallback-window"]
    assert count == 2
    import time as _time

    cache_service._memory_rate_limits["login:fallback-window"] = (count, _time.monotonic() - 1)

    assert await cache_service.increment_rate_limit("login:fallback-window", 300) == 1


@pytest.mark.asyncio
async def test_rate_limit_memory_fallback_is_bounded(monkeypatch):
    """An attacker minting distinct keys during an outage must not grow the
    fallback store without bound."""
    cache_service._memory_rate_limits.clear()

    async def no_redis() -> object:
        raise ConnectionError("redis down")

    monkeypatch.setattr(cache_service, "_get_redis", no_redis)
    monkeypatch.setattr(cache_service, "MEMORY_RATE_LIMIT_MAX_KEYS", 4)

    for i in range(6):
        await cache_service.increment_rate_limit(f"login:flood-{i}", 300)

    assert len(cache_service._memory_rate_limits) <= 4
    # The most recent keys survive; every retained key still counts.
    assert await cache_service.increment_rate_limit("login:flood-5", 300) == 2


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
