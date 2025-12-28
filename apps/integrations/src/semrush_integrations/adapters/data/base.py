"""
Base data adapter abstract class.

Defines the interface that all data adapters must implement.
Each adapter handles fetching SEO data from a specific provider.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from semrush_integrations.schemas.analytics_data import AnalyticsDataResponse
    from semrush_integrations.schemas.search_data import SearchDataResponse

logger = logging.getLogger(__name__)


@dataclass
class DateRange:
    """
    Represents a date range for data fetching.

    Attributes:
        start_date: First date in the range (inclusive).
        end_date: Last date in the range (inclusive).
    """

    start_date: date
    end_date: date

    @property
    def days(self) -> int:
        """Calculate the number of days in the range (inclusive)."""
        return (self.end_date - self.start_date).days + 1

    def __iter__(self) -> Iterator[date]:
        """Iterate over all dates in the range."""
        current = self.start_date
        while current <= self.end_date:
            yield current
            current += timedelta(days=1)

    def __str__(self) -> str:
        """String representation of the date range."""
        return f"{self.start_date.isoformat()} to {self.end_date.isoformat()}"


class DataAdapter(ABC):
    """
    Abstract base class for data fetching adapters.

    Each integration provider (GSC, GA4, BWT) has a data adapter that knows
    how to fetch and parse SEO data for a specific property.

    Class Attributes:
        provider_name: Unique identifier for this provider.
        data_type: Type of data this adapter fetches (search, analytics).

    Attributes:
        access_token: OAuth access token for API authentication.
        requests_per_minute: Rate limit for API requests.
        retry_count: Number of retries on transient failures.
        retry_delay: Base delay between retries in seconds.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider."""
        pass

    @property
    @abstractmethod
    def data_type(self) -> str:
        """Type of data this adapter fetches (search, analytics)."""
        pass

    def __init__(
        self,
        access_token: str,
        requests_per_minute: int = 60,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize the data adapter.

        Args:
            access_token: Valid OAuth access token for the provider.
            requests_per_minute: Maximum API requests per minute.
            retry_count: Number of retries on transient failures.
            retry_delay: Base delay between retries in seconds.
        """
        self.access_token = access_token
        self.requests_per_minute = requests_per_minute
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._request_times: list[float] = []

    @abstractmethod
    async def fetch_data(
        self,
        property_id: str,
        date_range: DateRange,
        **kwargs,
    ) -> SearchDataResponse | AnalyticsDataResponse:
        """
        Fetch data from the provider for a specific property.

        Args:
            property_id: Unique identifier for the property on the provider.
            date_range: Date range to fetch data for.
            **kwargs: Provider-specific options (dimensions, filters, etc.).

        Returns:
            Response containing the fetched data rows.

        Raises:
            httpx.HTTPStatusError: If the API request fails after retries.
        """
        pass

    async def _wait_for_rate_limit(self) -> None:
        """
        Wait if necessary to respect rate limits.

        Implements a sliding window rate limiter based on requests_per_minute.
        """
        import time

        now = time.time()
        window_start = now - 60  # 1 minute window

        # Remove requests outside the window
        self._request_times = [t for t in self._request_times if t > window_start]

        # If at limit, wait until oldest request falls out of window
        if len(self._request_times) >= self.requests_per_minute:
            wait_time = self._request_times[0] - window_start
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        # Record this request
        self._request_times.append(now)

    async def _retry_with_backoff(self, coro_func, *args, **kwargs):
        """
        Execute a coroutine with exponential backoff retry logic.

        Args:
            coro_func: Async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Result of the coroutine.

        Raises:
            The last exception if all retries fail.
        """
        import httpx

        last_exception = None

        for attempt in range(self.retry_count):
            try:
                await self._wait_for_rate_limit()
                return await coro_func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429:
                    # Rate limited - use exponential backoff
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                elif e.response.status_code >= 500:
                    # Server error - retry with backoff
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(f"Server error, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                else:
                    # Client error - don't retry
                    raise

        # All retries exhausted
        raise last_exception
