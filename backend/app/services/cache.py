from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any, Optional

from redis import asyncio as aioredis

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_redis_pool = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
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

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
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
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
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
            await redis.setex(key, ttl_seconds, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            redis = await self._get_redis()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")
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
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0

    async def get_or_set(
        self,
        key: str,
        factory,
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
        """Increment rate limit counter and return current count."""
        try:
            redis = await self._get_redis()
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning(f"Rate limit increment failed: {e}")
            return None


cache_service = CacheService()
