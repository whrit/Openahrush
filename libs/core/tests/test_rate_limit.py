"""
Tests for API rate limiting module.

Uses TDD approach - tests are written first to define expected behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import Response


class TestRateLimitConfig:
    """Tests for rate limit configuration."""

    def test_endpoint_category_enum_has_required_values(self) -> None:
        from semrush_core.rate_limit.config import EndpointCategory

        assert hasattr(EndpointCategory, "AUTH")
        assert hasattr(EndpointCategory, "CRAWL_TRIGGER")
        assert hasattr(EndpointCategory, "EXPORT_TRIGGER")
        assert hasattr(EndpointCategory, "API_READ")
        assert hasattr(EndpointCategory, "WEBHOOK_CONFIG")

    def test_rate_limit_settings_has_auth_limit(self) -> None:
        from semrush_core.rate_limit.config import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.auth_limit == 5
        assert settings.auth_window_seconds == 60  # 5/min

    def test_rate_limit_settings_has_crawl_trigger_limit(self) -> None:
        from semrush_core.rate_limit.config import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.crawl_trigger_limit == 10
        assert settings.crawl_trigger_window_seconds == 3600  # 10/hour

    def test_rate_limit_settings_has_export_trigger_limit(self) -> None:
        from semrush_core.rate_limit.config import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.export_trigger_limit == 20
        assert settings.export_trigger_window_seconds == 3600  # 20/hour

    def test_rate_limit_settings_has_api_read_limit(self) -> None:
        from semrush_core.rate_limit.config import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.api_read_limit == 100
        assert settings.api_read_window_seconds == 60  # 100/min

    def test_rate_limit_settings_has_webhook_config_limit(self) -> None:
        from semrush_core.rate_limit.config import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.webhook_config_limit == 10
        assert settings.webhook_config_window_seconds == 60  # 10/min

    def test_get_limit_for_category_returns_correct_values(self) -> None:
        from semrush_core.rate_limit.config import EndpointCategory, RateLimitSettings

        settings = RateLimitSettings()

        limit, window = settings.get_limit_for_category(EndpointCategory.AUTH)
        assert limit == 5
        assert window == 60

        limit, window = settings.get_limit_for_category(EndpointCategory.CRAWL_TRIGGER)
        assert limit == 10
        assert window == 3600

    def test_endpoint_mappings_maps_paths_to_categories(self) -> None:
        from semrush_core.rate_limit.config import (
            ENDPOINT_CATEGORY_MAPPINGS,
            EndpointCategory,
        )

        # Auth endpoints
        assert ENDPOINT_CATEGORY_MAPPINGS["/auth/login"] == EndpointCategory.AUTH
        assert ENDPOINT_CATEGORY_MAPPINGS["/auth/register"] == EndpointCategory.AUTH

        # Crawl triggers
        assert (
            ENDPOINT_CATEGORY_MAPPINGS["/projects/{project_id}/crawl"]
            == EndpointCategory.CRAWL_TRIGGER
        )

        # Export triggers
        assert (
            ENDPOINT_CATEGORY_MAPPINGS["/projects/{project_id}/exports"]
            == EndpointCategory.EXPORT_TRIGGER
        )

    def test_get_category_for_path_matches_exact_paths(self) -> None:
        from semrush_core.rate_limit.config import EndpointCategory, get_category_for_path

        category = get_category_for_path("/auth/login", "POST")
        assert category == EndpointCategory.AUTH

    def test_get_category_for_path_matches_dynamic_paths(self) -> None:
        from semrush_core.rate_limit.config import EndpointCategory, get_category_for_path

        category = get_category_for_path(
            "/projects/123e4567-e89b-12d3-a456-426614174000/crawl", "POST"
        )
        assert category == EndpointCategory.CRAWL_TRIGGER

    def test_get_category_for_path_returns_api_read_for_get(self) -> None:
        from semrush_core.rate_limit.config import EndpointCategory, get_category_for_path

        category = get_category_for_path("/projects/123/issues", "GET")
        assert category == EndpointCategory.API_READ

    def test_get_category_for_path_returns_none_for_unknown(self) -> None:
        from semrush_core.rate_limit.config import get_category_for_path

        category = get_category_for_path("/unknown/path", "DELETE")
        assert category is None


class TestRateLimitBackend:
    """Tests for Redis rate limit backend using sliding window algorithm."""

    @pytest.mark.asyncio
    async def test_init_creates_redis_client(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")

            mock_redis_class.from_url.assert_called_once()
            assert backend._client == mock_client

    @pytest.mark.asyncio
    async def test_is_allowed_returns_true_when_under_limit(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = MagicMock()
            # Create mock pipeline that returns proper results
            mock_pipeline = MagicMock()
            mock_pipeline.zremrangebyscore.return_value = None
            mock_pipeline.zcount.return_value = None
            mock_pipeline.zadd.return_value = None
            mock_pipeline.expire.return_value = None
            mock_pipeline.execute = AsyncMock(return_value=[1, 3])  # 3 requests in window
            mock_client.pipeline.return_value = mock_pipeline
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            allowed, remaining, _reset_at = await backend.is_allowed(
                key="user:123",
                limit=5,
                window_seconds=60,
            )

            assert allowed is True
            assert remaining == 1  # 5 - 3 - 1 = 1 remaining after this request

    @pytest.mark.asyncio
    async def test_is_allowed_returns_false_when_at_limit(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.zremrangebyscore.return_value = None
            mock_pipeline.zcount.return_value = None
            mock_pipeline.execute = AsyncMock(return_value=[1, 5])  # At limit
            mock_client.pipeline.return_value = mock_pipeline
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            allowed, remaining, _reset_at = await backend.is_allowed(
                key="user:123",
                limit=5,
                window_seconds=60,
            )

            assert allowed is False
            assert remaining == 0

    @pytest.mark.asyncio
    async def test_is_allowed_adds_request_to_sorted_set(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.zremrangebyscore.return_value = None
            mock_pipeline.zcount.return_value = None
            mock_pipeline.zadd.return_value = None
            mock_pipeline.expire.return_value = None
            mock_pipeline.execute = AsyncMock(return_value=[1, 0])  # 0 requests in window
            mock_client.pipeline.return_value = mock_pipeline
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            await backend.is_allowed(key="user:123", limit=5, window_seconds=60)

            # Should add current request with timestamp as score
            mock_pipeline.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_is_allowed_removes_expired_entries(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.zremrangebyscore.return_value = None
            mock_pipeline.zcount.return_value = None
            mock_pipeline.zadd.return_value = None
            mock_pipeline.expire.return_value = None
            mock_pipeline.execute = AsyncMock(return_value=[1, 0])
            mock_client.pipeline.return_value = mock_pipeline
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            await backend.is_allowed(key="user:123", limit=5, window_seconds=60)

            # Should remove entries older than window
            mock_pipeline.zremrangebyscore.assert_called()

    @pytest.mark.asyncio
    async def test_is_allowed_sets_expiry_on_key(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.zremrangebyscore.return_value = None
            mock_pipeline.zcount.return_value = None
            mock_pipeline.zadd.return_value = None
            mock_pipeline.expire.return_value = None
            mock_pipeline.execute = AsyncMock(return_value=[1, 0])
            mock_client.pipeline.return_value = mock_pipeline
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            await backend.is_allowed(key="user:123", limit=5, window_seconds=60)

            # Should set expiry to prevent key accumulation
            mock_pipeline.expire.assert_called()

    @pytest.mark.asyncio
    async def test_get_current_count_returns_count(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.zcount.return_value = 7
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            count = await backend.get_current_count(key="user:123", window_seconds=60)

            assert count == 7

    @pytest.mark.asyncio
    async def test_close_closes_redis_connection(self) -> None:
        from semrush_core.rate_limit.backend import RateLimitBackend

        with patch("semrush_core.rate_limit.backend.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_redis_class.from_url.return_value = mock_client

            backend = RateLimitBackend(redis_url="redis://localhost:6379/0")
            await backend.close()

            mock_client.close.assert_called_once()


class TestRateLimitMiddleware:
    """Tests for FastAPI rate limiting middleware."""

    def _create_mock_request(
        self,
        path: str = "/test",
        method: str = "GET",
        user_id: str | None = "user-123",
        client_ip: str = "127.0.0.1",
    ) -> MagicMock:
        """Create a mock request for testing."""
        request = MagicMock(spec=Request)
        request.url.path = path
        request.method = method
        request.client.host = client_ip
        request.state = MagicMock()
        if user_id:
            request.state.user = MagicMock()
            request.state.user.id = user_id
        else:
            request.state.user = None
        request.headers = Headers({})
        return request

    @pytest.mark.asyncio
    async def test_middleware_allows_request_when_under_limit(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.return_value = (True, 4, 1234567890)

        request = self._create_mock_request(path="/auth/login", method="POST")

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_returns_429_when_rate_limited(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.return_value = (False, 0, 1234567890)

        request = self._create_mock_request(path="/auth/login", method="POST")

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_middleware_adds_rate_limit_headers(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.return_value = (True, 4, 1234567890)

        request = self._create_mock_request(path="/auth/login", method="POST")

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        response = await middleware.dispatch(request, call_next)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_adds_retry_after_header_on_429(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.return_value = (False, 0, 1234567890)

        request = self._create_mock_request(path="/auth/login", method="POST")

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        response = await middleware.dispatch(request, call_next)

        assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_uses_user_id_for_key_when_authenticated(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.return_value = (True, 4, 1234567890)

        request = self._create_mock_request(
            path="/projects/123/issues", method="GET", user_id="user-456"
        )

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        await middleware.dispatch(request, call_next)

        # Verify the key contains user_id
        call_args = mock_backend.is_allowed.call_args
        assert "user-456" in call_args.kwargs["key"]

    @pytest.mark.asyncio
    async def test_middleware_uses_ip_for_key_when_not_authenticated(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.return_value = (True, 4, 1234567890)

        request = self._create_mock_request(path="/auth/login", method="POST", user_id=None)

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        await middleware.dispatch(request, call_next)

        # Verify the key contains IP
        call_args = mock_backend.is_allowed.call_args
        assert "127.0.0.1" in call_args.kwargs["key"]

    @pytest.mark.asyncio
    async def test_middleware_skips_uncategorized_endpoints(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()

        request = self._create_mock_request(path="/health", method="GET")

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        response = await middleware.dispatch(request, call_next)

        # Should not call rate limit backend for health check
        mock_backend.is_allowed.assert_not_called()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_handles_backend_errors_gracefully(self) -> None:
        from semrush_core.rate_limit.middleware import RateLimitMiddleware

        mock_backend = AsyncMock()
        mock_backend.is_allowed.side_effect = Exception("Redis connection error")

        request = self._create_mock_request(path="/auth/login", method="POST")

        async def call_next(req: Request) -> Response:
            return Response(content="OK", status_code=200)

        middleware = RateLimitMiddleware(app=MagicMock(), backend=mock_backend)
        response = await middleware.dispatch(request, call_next)

        # Should allow request when backend fails (fail open)
        assert response.status_code == 200


class TestRateLimitKeyGeneration:
    """Tests for rate limit key generation."""

    def test_build_key_with_user_id(self) -> None:
        from semrush_core.rate_limit.backend import build_rate_limit_key
        from semrush_core.rate_limit.config import EndpointCategory

        key = build_rate_limit_key(
            category=EndpointCategory.AUTH,
            identifier="user-123",
        )

        assert key == "ratelimit:auth:user-123"

    def test_build_key_with_ip_address(self) -> None:
        from semrush_core.rate_limit.backend import build_rate_limit_key
        from semrush_core.rate_limit.config import EndpointCategory

        key = build_rate_limit_key(
            category=EndpointCategory.API_READ,
            identifier="192.168.1.1",
        )

        assert key == "ratelimit:api_read:192.168.1.1"

    def test_build_key_includes_category(self) -> None:
        from semrush_core.rate_limit.backend import build_rate_limit_key
        from semrush_core.rate_limit.config import EndpointCategory

        key_crawl = build_rate_limit_key(
            category=EndpointCategory.CRAWL_TRIGGER,
            identifier="user-123",
        )
        key_export = build_rate_limit_key(
            category=EndpointCategory.EXPORT_TRIGGER,
            identifier="user-123",
        )

        assert key_crawl != key_export
        assert "crawl_trigger" in key_crawl
        assert "export_trigger" in key_export
