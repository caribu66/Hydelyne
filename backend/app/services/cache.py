from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Optional

from redis import asyncio as aioredis

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        # redis-py ships py.typed, but `from_url` itself has no parameter/
        # return annotations in its own source (checked directly), so this
        # one call is genuinely unclassifiable by mypy — not a stub gap we
        # can route around. The module-level annotation above is what gives
        # every *caller* of get_redis() a real `Redis` type regardless.
        _redis_pool = aioredis.from_url(  # type: ignore[no-untyped-call]
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=False,
            health_check_interval=30,
        )
    return _redis_pool


class CacheService:
    """Service for caching frequently accessed data."""

    DEFAULT_TTL = timedelta(minutes=5)
    CREW_LIST_TTL = timedelta(minutes=2)
    COMPLIANCE_TTL = timedelta(minutes=10)
    REPORT_TTL = timedelta(minutes=30)
    # A safety net, not the primary consistency mechanism: explicit
    # invalidation on profile edit / CV re-processing keeps this fresh in
    # practice (see ConsultantKnowledgeService.summarize).
    SUMMARY_TTL = timedelta(minutes=30)

    # Bound for the process-local rate-limit fallback below. Login keys are
    # per (ip, email), so an attacker could mint distinct keys; the cap keeps
    # that memory bounded while still throttling every key it retains.
    MEMORY_RATE_LIMIT_MAX_KEYS = 10000

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None
        # key -> (count, window_expires_at_monotonic). Populated only when
        # Redis is unreachable; buckets are per-process, not distributed.
        self._memory_rate_limits: dict[str, tuple[int, float]] = {}

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def _make_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from prefix and arguments."""
        key_data = f"{prefix}:{json.dumps(args, sort_keys=True, default=str)}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        hashed = hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()
        return f"hydenlyne:{prefix}:{hashed}"

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        try:
            redis = await self._get_redis()
            value = await redis.get(key)
            if value:
                return json.loads(value)
        except Exception as exc:
            logger.warning("Cache get failed (%s)", type(exc).__name__)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None,
    ) -> bool:
        """Set a value in cache."""
        try:
            redis = await self._get_redis()
            ttl_seconds = int((ttl or self.DEFAULT_TTL).total_seconds())
            await redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)
            return True
        except Exception as exc:
            logger.warning("Cache set failed (%s)", type(exc).__name__)
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            redis = await self._get_redis()
            await redis.delete(key)
            return True
        except Exception as exc:
            logger.warning("Cache delete failed (%s)", type(exc).__name__)
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        try:
            redis = await self._get_redis()
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await redis.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning("Cache invalidation failed (%s)", type(exc).__name__)
            return 0

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[Any]],
        ttl: Optional[timedelta] = None,
    ) -> Any:
        """Get from cache or set using factory function."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory()
        if value is not None:
            await self.set(key, value, ttl)
        return value

    async def is_redis_available(self) -> bool:
        """Check if Redis is available."""
        try:
            redis = await self._get_redis()
            await redis.ping()
            return True
        except Exception:
            return False

    async def increment_rate_limit(self, key: str, window_seconds: int) -> Optional[int]:
        """Increment rate limit counter and return current count.

        Fixed window: TTL is set only when the counter is first created so
        sustained traffic cannot extend the window indefinitely.
        When Redis is unreachable, falls back to a process-local counter so
        brute-force protection degrades instead of disappearing. The fallback
        buckets are per-process (not distributed across replicas) and bounded;
        callers must still treat a None return as "unmetered" — it only
        happens if the in-process bookkeeping itself fails.
        """
        try:
            redis = await self._get_redis()
            count = int(await redis.incr(key))
            if count == 1:
                await redis.expire(key, window_seconds)
            elif int(await redis.ttl(key)) < 0:
                # Repair counters whose initial EXPIRE failed without turning
                # the fixed window into a sliding window.
                await redis.expire(key, window_seconds)
            return count
        except Exception as exc:
            logger.warning(
                "Rate limit increment failed, using process-local fallback (%s)",
                type(exc).__name__,
            )
            return self._increment_memory_rate_limit(key, window_seconds)

    def _increment_memory_rate_limit(self, key: str, window_seconds: int) -> int:
        """Process-local fixed-window counter used when Redis is down."""
        now = time.monotonic()
        for expired_key in [
            existing
            for existing, (_, expires_at) in self._memory_rate_limits.items()
            if expires_at <= now
        ]:
            del self._memory_rate_limits[expired_key]
        entry = self._memory_rate_limits.get(key)
        count = entry[0] + 1 if entry is not None else 1
        if (
            key not in self._memory_rate_limits
            and len(self._memory_rate_limits) >= self.MEMORY_RATE_LIMIT_MAX_KEYS
        ):
            # Full and no expired entries left: evict the oldest insertion to
            # stay bounded. Dicts preserve insertion order, and re-incremented
            # keys keep their original position, so this is FIFO eviction.
            self._memory_rate_limits.pop(next(iter(self._memory_rate_limits)))
        self._memory_rate_limits[key] = (count, now + window_seconds)
        return count


cache_service = CacheService()
