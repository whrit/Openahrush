"""
Async HTTP fetcher for crawling.

Provides an async HTTP client with:
- Connection pooling via httpx
- Redirect handling with configurable limits
- Response time tracking
- User-Agent configuration
- Politeness delays per domain
- Concurrency limiting via semaphore
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx


class FetchError(Exception):
    """Exception raised when a fetch operation fails."""

    def __init__(self, url: str, message: str, cause: Exception | None = None) -> None:
        self.url = url
        self.message = message
        self.cause = cause
        super().__init__(f"Failed to fetch {url}: {message}")


@dataclass
class FetcherSettings:
    """
    Configuration settings for the HTTP fetcher.

    Attributes:
        user_agent: User-Agent header to send with requests.
        politeness_delay_ms: Minimum delay between requests to same domain.
        max_redirects: Maximum number of redirects to follow.
        timeout_seconds: Request timeout in seconds.
        max_concurrent: Maximum concurrent requests allowed.
        max_keepalive_connections: Maximum keepalive connections in pool.
        keepalive_expiry_seconds: Keepalive connection expiry time.
        connect_timeout_seconds: Connection timeout (separate from read).
        read_timeout_seconds: Read timeout for response body.
        pool_timeout_seconds: Timeout waiting for connection from pool.
        http2: Enable HTTP/2 support.
    """

    user_agent: str = "Openahrush/1.0"
    politeness_delay_ms: int = 1000
    max_redirects: int = 5
    timeout_seconds: int = 30
    max_concurrent: int = 10
    # Connection pooling settings for high-throughput crawling
    max_keepalive_connections: int = 100
    keepalive_expiry_seconds: float = 30.0
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    pool_timeout_seconds: float = 10.0
    # HTTP/2 support - requires httpx[http2] (h2 package)
    http2: bool = False


@dataclass
class FetchResult:
    """
    Result of a successful HTTP fetch operation.

    Attributes:
        url: Original requested URL.
        final_url: URL after any redirects.
        status_code: HTTP status code.
        content_type: Content-Type header value.
        body: Response body as bytes.
        response_time_ms: Time taken for the request in milliseconds.
        headers: Response headers dictionary.
    """

    url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    response_time_ms: int
    headers: dict[str, str]

    @property
    def is_success(self) -> bool:
        """Check if response is a success (2xx status code)."""
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """Check if response is a redirect (3xx status code)."""
        return 300 <= self.status_code < 400

    @property
    def is_client_error(self) -> bool:
        """Check if response is a client error (4xx status code)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if response is a server error (5xx status code)."""
        return 500 <= self.status_code < 600

    @property
    def was_redirected(self) -> bool:
        """Check if the request was redirected."""
        return self.url != self.final_url


@dataclass
class Fetcher:
    """
    Async HTTP fetcher with connection pooling and rate limiting.

    Use as an async context manager:

        async with Fetcher() as fetcher:
            result = await fetcher.fetch("https://example.com")

    Attributes:
        settings: FetcherSettings configuration.
    """

    settings: FetcherSettings = field(default_factory=FetcherSettings)

    # Internal state
    _client: httpx.AsyncClient | None = field(default=None, init=False)
    _semaphore: asyncio.Semaphore = field(init=False)
    _last_request_time: dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Initialize the semaphore for concurrency limiting."""
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent)

    async def __aenter__(self) -> Fetcher:
        """Enter async context and create HTTP client with optimized pooling."""
        # Configure granular timeouts for better control
        timeout = httpx.Timeout(
            connect=self.settings.connect_timeout_seconds,
            read=self.settings.read_timeout_seconds,
            write=self.settings.timeout_seconds,
            pool=self.settings.pool_timeout_seconds,
        )

        # Configure connection pool limits for high-throughput crawling
        limits = httpx.Limits(
            max_keepalive_connections=self.settings.max_keepalive_connections,
            max_connections=self.settings.max_concurrent + 50,
            keepalive_expiry=self.settings.keepalive_expiry_seconds,
        )

        self._client = httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=self.settings.max_redirects,
            timeout=timeout,
            limits=limits,
            http2=self.settings.http2,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context and close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        parsed = urlparse(url)
        return parsed.netloc

    def get_delay(self, url: str) -> float:
        """
        Get the delay needed before fetching this URL.

        Args:
            url: URL to check.

        Returns:
            Delay in seconds (0 if no delay needed).
        """
        domain = self._get_domain(url)
        last_time = self._last_request_time.get(domain)

        if last_time is None:
            return 0

        elapsed = (time.monotonic() - last_time) * 1000  # Convert to ms
        delay_needed = self.settings.politeness_delay_ms - elapsed

        if delay_needed > 0:
            return delay_needed / 1000  # Convert back to seconds

        return 0

    async def _apply_politeness_delay(self, url: str) -> None:
        """Apply politeness delay before fetching URL."""
        delay = self.get_delay(url)
        if delay > 0:
            await asyncio.sleep(delay)

    def _record_request_time(self, url: str) -> None:
        """Record the time of the last request to this domain."""
        domain = self._get_domain(url)
        self._last_request_time[domain] = time.monotonic()

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch a URL and return the result.

        Args:
            url: URL to fetch.

        Returns:
            FetchResult with response data.

        Raises:
            FetchError: If the request fails.
        """
        if self._client is None:
            raise FetchError(url, "Fetcher not initialized. Use as async context manager.")

        async with self._semaphore:
            # Apply politeness delay
            await self._apply_politeness_delay(url)

            start_time = time.monotonic()

            try:
                response = await self._client.get(
                    url,
                    headers={"User-Agent": self.settings.user_agent},
                )

                # Record request time for rate limiting
                self._record_request_time(url)

                response_time_ms = int((time.monotonic() - start_time) * 1000)

                # Extract content type from headers
                content_type = response.headers.get("content-type", "")

                # Convert headers to dict
                headers_dict = dict(response.headers)

                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    body=response.content,
                    response_time_ms=response_time_ms,
                    headers=headers_dict,
                )

            except httpx.TimeoutException as e:
                raise FetchError(url, "Request timeout", e) from e
            except httpx.ConnectError as e:
                raise FetchError(url, "Connection failed", e) from e
            except httpx.TooManyRedirects as e:
                raise FetchError(url, "Too many redirects", e) from e
            except httpx.HTTPError as e:
                raise FetchError(url, f"HTTP error: {e}", e) from e
            except Exception as e:
                raise FetchError(url, f"Unexpected error: {e}", e) from e

    async def fetch_many(
        self, urls: list[str]
    ) -> list[FetchResult | FetchError]:
        """
        Fetch multiple URLs concurrently with rate limiting.

        Args:
            urls: List of URLs to fetch.

        Returns:
            List of FetchResult or FetchError for each URL.
        """
        async def fetch_one(url: str) -> FetchResult | FetchError:
            try:
                return await self.fetch(url)
            except FetchError as e:
                return e

        tasks = [fetch_one(url) for url in urls]
        return await asyncio.gather(*tasks)
