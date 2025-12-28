"""
Tests for async HTTP fetcher.

TDD tests covering:
- Async HTTP requests with httpx
- Redirect handling
- Response time tracking
- User-Agent setting
- Politeness delays
- Concurrency limiting via semaphore
- Connection pooling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from semrush_workers.crawl.fetcher import (
    Fetcher,
    FetchError,
    FetcherSettings,
    FetchResult,
)


class TestFetcherSettings:
    """Tests for FetcherSettings configuration."""

    def test_default_settings(self) -> None:
        """Default settings should have sensible values."""
        settings = FetcherSettings()
        assert settings.user_agent == "Openahrush/1.0"
        assert settings.politeness_delay_ms == 1000
        assert settings.max_redirects == 5
        assert settings.timeout_seconds == 30
        assert settings.max_concurrent == 10

    def test_custom_settings(self) -> None:
        """Custom settings should override defaults."""
        settings = FetcherSettings(
            user_agent="CustomBot/1.0",
            politeness_delay_ms=500,
            max_redirects=3,
            timeout_seconds=15,
            max_concurrent=5,
        )
        assert settings.user_agent == "CustomBot/1.0"
        assert settings.politeness_delay_ms == 500
        assert settings.max_redirects == 3
        assert settings.timeout_seconds == 15
        assert settings.max_concurrent == 5


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_fetch_result_creation(self) -> None:
        """FetchResult should store all response data."""
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            content_type="text/html",
            body=b"<html>Test</html>",
            response_time_ms=150,
            headers={},
        )
        assert result.url == "https://example.com"
        assert result.final_url == "https://example.com/"
        assert result.status_code == 200
        assert result.content_type == "text/html"
        assert result.body == b"<html>Test</html>"
        assert result.response_time_ms == 150

    def test_fetch_result_is_success(self) -> None:
        """is_success should return True for 2xx status codes."""
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result.is_success is True

        result_201 = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=201,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result_201.is_success is True

    def test_fetch_result_is_redirect(self) -> None:
        """is_redirect should return True for 3xx status codes."""
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/new",
            status_code=301,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result.is_redirect is True

    def test_fetch_result_is_client_error(self) -> None:
        """is_client_error should return True for 4xx status codes."""
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=404,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result.is_client_error is True

    def test_fetch_result_is_server_error(self) -> None:
        """is_server_error should return True for 5xx status codes."""
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=500,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result.is_server_error is True

    def test_fetch_result_was_redirected(self) -> None:
        """was_redirected should return True if url != final_url."""
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/redirected",
            status_code=200,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result.was_redirected is True

        result_no_redirect = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            content_type="text/html",
            body=b"",
            response_time_ms=100,
            headers={},
        )
        assert result_no_redirect.was_redirected is False


class TestFetcherCreation:
    """Tests for Fetcher creation and configuration."""

    @pytest.mark.asyncio
    async def test_create_fetcher_default_settings(self) -> None:
        """Fetcher should work with default settings."""
        async with Fetcher() as fetcher:
            assert fetcher.settings.user_agent == "Openahrush/1.0"

    @pytest.mark.asyncio
    async def test_create_fetcher_custom_settings(self) -> None:
        """Fetcher should accept custom settings."""
        settings = FetcherSettings(user_agent="TestBot/1.0")
        async with Fetcher(settings=settings) as fetcher:
            assert fetcher.settings.user_agent == "TestBot/1.0"

    @pytest.mark.asyncio
    async def test_fetcher_context_manager(self) -> None:
        """Fetcher should work as async context manager."""
        async with Fetcher() as fetcher:
            assert fetcher is not None
        # After exiting context, client should be closed


class TestFetcherFetch:
    """Tests for fetching URLs."""

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Successful fetch should return FetchResult."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.content = b"<html>Test</html>"
        mock_response.url = httpx.URL("https://example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                result = await fetcher.fetch("https://example.com")

            assert result.status_code == 200
            assert result.body == b"<html>Test</html>"
            assert "text/html" in result.content_type

    @pytest.mark.asyncio
    async def test_fetch_tracks_response_time(self) -> None:
        """Fetch should track response time in milliseconds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html>Test</html>"
        mock_response.url = httpx.URL("https://example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                result = await fetcher.fetch("https://example.com")

            assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_fetch_handles_redirect(self) -> None:
        """Fetch should capture final URL after redirects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html>Redirected</html>"
        mock_response.url = httpx.URL("https://example.com/redirected")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                result = await fetcher.fetch("https://example.com")

            assert result.url == "https://example.com"
            assert result.final_url == "https://example.com/redirected"
            assert result.was_redirected is True

    @pytest.mark.asyncio
    async def test_fetch_sets_user_agent(self) -> None:
        """Fetch should set the configured User-Agent header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html>Test</html>"
        mock_response.url = httpx.URL("https://example.com")

        settings = FetcherSettings(user_agent="TestBot/2.0")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher(settings=settings) as fetcher:
                fetcher._client = mock_client
                await fetcher.fetch("https://example.com")

            # Verify User-Agent was passed in headers
            call_args = mock_client.get.call_args
            headers = call_args.kwargs.get("headers", {})
            assert headers.get("User-Agent") == "TestBot/2.0"


class TestFetcherErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_fetch_timeout_raises_fetch_error(self) -> None:
        """Timeout should raise FetchError."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                with pytest.raises(FetchError) as exc_info:
                    await fetcher.fetch("https://example.com")

            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_connection_error_raises_fetch_error(self) -> None:
        """Connection error should raise FetchError."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("connection failed")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                with pytest.raises(FetchError) as exc_info:
                    await fetcher.fetch("https://example.com")

            assert "connection" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_too_many_redirects_raises_fetch_error(self) -> None:
        """Too many redirects should raise FetchError."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.TooManyRedirects("too many redirects")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                with pytest.raises(FetchError) as exc_info:
                    await fetcher.fetch("https://example.com")

            assert "redirect" in str(exc_info.value).lower()


class TestFetcherConcurrency:
    """Tests for concurrency limiting."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_requests(self) -> None:
        """Semaphore should limit concurrent requests."""
        settings = FetcherSettings(max_concurrent=2)
        async with Fetcher(settings=settings) as fetcher:
            # Verify semaphore was created with correct limit
            assert fetcher._semaphore._value == 2

    @pytest.mark.asyncio
    async def test_fetch_many_urls_concurrently(self) -> None:
        """fetch_many should fetch multiple URLs with concurrency limit."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"<html>Test</html>"
        mock_response.url = httpx.URL("https://example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            settings = FetcherSettings(max_concurrent=2, politeness_delay_ms=0)
            async with Fetcher(settings=settings) as fetcher:
                fetcher._client = mock_client
                urls = [
                    "https://example.com/page1",
                    "https://example.com/page2",
                    "https://example.com/page3",
                ]
                results = await fetcher.fetch_many(urls)

            assert len(results) == 3
            for result in results:
                assert isinstance(result, (FetchResult, FetchError))


class TestFetcherPoliteness:
    """Tests for politeness delays."""

    @pytest.mark.asyncio
    async def test_politeness_delay_applied_per_domain(self) -> None:
        """Fetcher should track last request time per domain."""
        settings = FetcherSettings(politeness_delay_ms=100)
        async with Fetcher(settings=settings) as fetcher:
            # Initially no last request time for domain
            assert "example.com" not in fetcher._last_request_time

    @pytest.mark.asyncio
    async def test_get_delay_returns_correct_wait_time(self) -> None:
        """get_delay should return correct wait time for domain."""
        settings = FetcherSettings(politeness_delay_ms=1000)
        async with Fetcher(settings=settings) as fetcher:
            # For new domain, delay should be 0
            delay = fetcher.get_delay("https://example.com")
            assert delay == 0


class TestFetcherHeaders:
    """Tests for HTTP headers."""

    @pytest.mark.asyncio
    async def test_fetch_captures_response_headers(self) -> None:
        """Fetch should capture response headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/html",
            "x-custom": "value",
        }
        mock_response.content = b"<html>Test</html>"
        mock_response.url = httpx.URL("https://example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            async with Fetcher() as fetcher:
                fetcher._client = mock_client
                result = await fetcher.fetch("https://example.com")

            assert "content-type" in result.headers or "x-custom" in result.headers
