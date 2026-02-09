"""Tests for the cache service module."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.cache_service import CacheService


class TestCacheServiceHashKey:
    """Test hash key generation."""

    def test_hash_key_deterministic(self):
        key1 = CacheService.hash_key("prefix", "Samsung Galaxy S25")
        key2 = CacheService.hash_key("prefix", "Samsung Galaxy S25")
        assert key1 == key2

    def test_hash_key_case_insensitive(self):
        key1 = CacheService.hash_key("prefix", "Samsung Galaxy S25")
        key2 = CacheService.hash_key("prefix", "samsung galaxy s25")
        assert key1 == key2

    def test_hash_key_strips_whitespace(self):
        key1 = CacheService.hash_key("prefix", "  Samsung Galaxy S25  ")
        key2 = CacheService.hash_key("prefix", "Samsung Galaxy S25")
        assert key1 == key2

    def test_hash_key_includes_prefix(self):
        key = CacheService.hash_key("product_cache", "iPhone 15")
        assert key.startswith("product_cache:")

    def test_hash_key_different_values_different_keys(self):
        key1 = CacheService.hash_key("prefix", "iPhone 15 Pro")
        key2 = CacheService.hash_key("prefix", "iPhone 16 Pro")
        assert key1 != key2


class TestCacheServiceGracefulDegradation:
    """Test that cache service degrades gracefully when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_disconnected(self):
        cs = CacheService()
        # No connect() called — _redis is None
        result = await cs.get("some_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_noop_when_disconnected(self):
        cs = CacheService()
        # Should not raise
        await cs.set("some_key", {"data": "value"}, ttl=60)

    @pytest.mark.asyncio
    async def test_delete_noop_when_disconnected(self):
        cs = CacheService()
        await cs.delete("some_key")

    @pytest.mark.asyncio
    async def test_connect_handles_failure_gracefully(self):
        cs = CacheService()
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://nonexistent:9999/0"
            await cs.connect()
        # Should not raise, _redis should be None
        assert cs._redis is None


class TestCacheServiceWithMockRedis:
    """Test cache get/set with mocked Redis."""

    @pytest.mark.asyncio
    async def test_get_returns_cached_value(self):
        cs = CacheService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"status": "found", "data": 123}')
        cs._redis = mock_redis

        result = await cs.get("test_key")
        assert result == {"status": "found", "data": 123}
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self):
        cs = CacheService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cs._redis = mock_redis

        result = await cs.get("missing_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_value(self):
        cs = CacheService()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        cs._redis = mock_redis

        await cs.set("test_key", {"hello": "world"}, ttl=300)
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[1]["ex"] == 300

    @pytest.mark.asyncio
    async def test_get_handles_redis_error(self):
        cs = CacheService()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        cs._redis = mock_redis

        result = await cs.get("test_key")
        assert result is None  # Graceful degradation

    @pytest.mark.asyncio
    async def test_set_handles_redis_error(self):
        cs = CacheService()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        cs._redis = mock_redis

        # Should not raise
        await cs.set("test_key", {"data": "value"})
