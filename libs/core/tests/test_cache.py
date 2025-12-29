"""
Tests for response caching module.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestCacheBackendInit:
    @pytest.mark.asyncio
    async def test_creates_redis_client_from_url(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            mock_redis_class.from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                encoding="utf-8",
                decode_responses=True,
            )
            assert backend._client == mock_client

    @pytest.mark.asyncio
    async def test_accepts_custom_prefix(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_redis_class.from_url.return_value = AsyncMock()
            backend = CacheBackend(redis_url="redis://localhost:6379/0", prefix="myapp:")
            assert backend._prefix == "myapp:"

    @pytest.mark.asyncio
    async def test_default_prefix_is_cache(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_redis_class.from_url.return_value = AsyncMock()
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            assert backend._prefix == "cache:"


class TestCacheBackendGet:
    @pytest.mark.asyncio
    async def test_returns_cached_value_when_exists(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = '{"data": "test"}'
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.get("mykey")
            mock_client.get.assert_called_once_with("cache:mykey")
            assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_returns_none_when_key_not_found(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = None
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.get("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_handles_invalid_json_gracefully(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = "not valid json {"
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.get("badkey")
            assert result is None


class TestCacheBackendSet:
    @pytest.mark.asyncio
    async def test_stores_value_with_ttl(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            await backend.set("mykey", {"data": "test"}, ttl=300)
            mock_client.setex.assert_called_once_with("cache:mykey", 300, '{"data": "test"}')


class TestCacheBackendDelete:
    @pytest.mark.asyncio
    async def test_deletes_single_key(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.delete.return_value = 1
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.delete("mykey")
            mock_client.delete.assert_called_once_with("cache:mykey")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_key_not_found(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.delete.return_value = 0
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.delete("nonexistent")
            assert result is False


class TestCacheBackendDeletePattern:
    @pytest.mark.asyncio
    async def test_deletes_keys_matching_pattern(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scan.return_value = (0, ["cache:issues:proj1:a", "cache:issues:proj1:b"])
            mock_client.delete.return_value = 2
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.delete_pattern("issues:proj1:*")
            mock_client.scan.assert_called()
            assert result == 2

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_matches(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.scan.return_value = (0, [])
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.delete_pattern("nonexistent:*")
            assert result == 0


class TestCacheBackendExists:
    @pytest.mark.asyncio
    async def test_returns_true_when_key_exists(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.exists.return_value = 1
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            result = await backend.exists("mykey")
            mock_client.exists.assert_called_once_with("cache:mykey")
            assert result is True


class TestCacheBackendClose:
    @pytest.mark.asyncio
    async def test_closes_redis_connection(self) -> None:
        from semrush_core.cache.backend import CacheBackend

        with patch("semrush_core.cache.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client
            backend = CacheBackend(redis_url="redis://localhost:6379/0")
            await backend.close()
            mock_client.close.assert_called_once()


class TestBuildCacheKey:
    def test_builds_key_with_endpoint_and_id(self) -> None:
        from semrush_core.cache.keys import build_cache_key

        key = build_cache_key(endpoint="issues", resource_id="proj-123")
        assert key == "issues:proj-123"

    def test_builds_key_with_params_hash(self) -> None:
        from semrush_core.cache.keys import build_cache_key

        key = build_cache_key(
            endpoint="issues", resource_id="proj-123", params={"page": 1, "limit": 20}
        )
        assert key.startswith("issues:proj-123:")

    def test_params_order_does_not_affect_hash(self) -> None:
        from semrush_core.cache.keys import build_cache_key

        key1 = build_cache_key(
            endpoint="issues", resource_id="proj-123", params={"page": 1, "limit": 20}
        )
        key2 = build_cache_key(
            endpoint="issues", resource_id="proj-123", params={"limit": 20, "page": 1}
        )
        assert key1 == key2

    def test_empty_params_no_hash_suffix(self) -> None:
        from semrush_core.cache.keys import build_cache_key

        key = build_cache_key(endpoint="snapshots", resource_id="list", params={})
        assert key == "snapshots:list"


class TestHashParams:
    def test_returns_md5_hash(self) -> None:
        from semrush_core.cache.keys import hash_params

        result = hash_params({"a": 1, "b": 2})
        assert len(result) == 32

    def test_produces_consistent_hash(self) -> None:
        from semrush_core.cache.keys import hash_params

        hash1 = hash_params({"page": 1, "sort": "name"})
        hash2 = hash_params({"page": 1, "sort": "name"})
        assert hash1 == hash2


class TestCachedDecoratorTTLValues:
    def test_issues_ttl_is_5_minutes(self) -> None:
        from semrush_core.cache import TTL_ISSUES

        assert TTL_ISSUES == 300

    def test_refdomains_ttl_is_1_hour(self) -> None:
        from semrush_core.cache import TTL_REFDOMAINS

        assert TTL_REFDOMAINS == 3600

    def test_snapshots_ttl_is_1_hour(self) -> None:
        from semrush_core.cache import TTL_SNAPSHOTS

        assert TTL_SNAPSHOTS == 3600

    def test_settings_ttl_is_10_minutes(self) -> None:
        from semrush_core.cache import TTL_SETTINGS

        assert TTL_SETTINGS == 600


class TestCacheHeaders:
    def test_build_cache_control_header(self) -> None:
        from semrush_core.cache.headers import build_cache_control

        header = build_cache_control(max_age=300, private=True)
        assert header == "private, max-age=300"

    def test_build_cache_control_public(self) -> None:
        from semrush_core.cache.headers import build_cache_control

        header = build_cache_control(max_age=3600, private=False)
        assert header == "public, max-age=3600"

    def test_build_cache_control_no_store(self) -> None:
        from semrush_core.cache.headers import build_cache_control

        header = build_cache_control(no_store=True)
        assert header == "no-store"


class TestCacheControlConstants:
    def test_cache_control_private(self) -> None:
        from semrush_core.cache.headers import CACHE_CONTROL_PRIVATE

        assert CACHE_CONTROL_PRIVATE == "private"

    def test_cache_control_public(self) -> None:
        from semrush_core.cache.headers import CACHE_CONTROL_PUBLIC

        assert CACHE_CONTROL_PUBLIC == "public"

    def test_cache_control_no_store(self) -> None:
        from semrush_core.cache.headers import CACHE_CONTROL_NO_STORE

        assert CACHE_CONTROL_NO_STORE == "no-store"
