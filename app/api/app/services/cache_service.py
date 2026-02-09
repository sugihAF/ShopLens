"""Redis caching service with graceful degradation."""

import hashlib
import json
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """
    Async Redis cache with graceful degradation.

    All operations return None / no-op if Redis is unavailable,
    so callers never need to handle connection errors.
    """

    def __init__(self):
        self._redis = None

    async def connect(self) -> None:
        """Connect to Redis. Logs warning on failure but does not raise."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # Verify connection
            await self._redis.ping()
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis cache unavailable — caching disabled: {e}")
            self._redis = None

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("Redis cache disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting Redis: {e}")
            finally:
                self._redis = None

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None on miss or error."""
        if not self._redis:
            return None
        try:
            data = await self._redis.get(key)
            if data is not None:
                return json.loads(data)
            return None
        except Exception as e:
            logger.debug(f"Cache get error for '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set a value in cache with TTL (seconds). No-op on error."""
        if not self._redis:
            return
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as e:
            logger.debug(f"Cache set error for '{key}': {e}")

    async def delete(self, key: str) -> None:
        """Delete a key from cache. No-op on error."""
        if not self._redis:
            return
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.debug(f"Cache delete error for '{key}': {e}")

    @staticmethod
    def hash_key(prefix: str, value: str) -> str:
        """Generate a deterministic, case-insensitive cache key."""
        normalized = value.strip().lower()
        digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"


# Module-level singleton
cache = CacheService()
