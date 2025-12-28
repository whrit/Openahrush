"""
Bing Webmaster Tools data adapter.

Fetches search performance data from Bing Webmaster Tools using the
GetQueryStats and GetPageStats API endpoints.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from semrush_integrations.adapters.data.base import DataAdapter, DateRange
from semrush_integrations.schemas.search_data import SearchDataResponse, SearchDataRow

logger = logging.getLogger(__name__)

# BWT API constants
BWT_API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"


class BWTDataAdapter(DataAdapter):
    """
    Bing Webmaster Tools data adapter.

    Fetches search performance data using the BWT API.
    Provides methods to fetch both query stats and page stats.

    Example:
        >>> adapter = BWTDataAdapter(access_token="xxx")
        >>> response = await adapter.fetch_data(
        ...     property_id="https://example.com",
        ...     date_range=DateRange(date(2024, 1, 1), date(2024, 1, 7)),
        ... )
        >>> for row in response.rows:
        ...     print(f"{row.query}: {row.clicks} clicks")
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "bing_webmaster_tools"

    @property
    def data_type(self) -> str:
        """Return the data type."""
        return "search"

    @property
    def engine(self) -> str:
        """Return the search engine name."""
        return "bing"

    async def fetch_data(
        self,
        property_id: str,
        date_range: DateRange,
        include_query_stats: bool = True,
        include_page_stats: bool = True,
        **kwargs,
    ) -> SearchDataResponse:
        """
        Fetch search performance data from Bing Webmaster Tools.

        Combines data from both GetQueryStats and GetPageStats endpoints.

        Args:
            property_id: BWT site URL (e.g., "https://example.com").
            date_range: Date range to fetch data for.
            include_query_stats: Whether to fetch query-level data.
            include_page_stats: Whether to fetch page-level data.
            **kwargs: Additional options.

        Returns:
            SearchDataResponse containing all fetched rows.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        all_rows: list[SearchDataRow] = []

        if include_query_stats:
            query_response = await self.fetch_query_stats(property_id, date_range)
            all_rows.extend(query_response.rows)

        if include_page_stats:
            page_response = await self.fetch_page_stats(property_id, date_range)
            all_rows.extend(page_response.rows)

        return SearchDataResponse(
            rows=all_rows,
            total_rows=len(all_rows),
        )

    async def fetch_query_stats(
        self,
        property_id: str,
        date_range: DateRange,
    ) -> SearchDataResponse:
        """
        Fetch query-level statistics from BWT.

        Args:
            property_id: BWT site URL.
            date_range: Date range to fetch data for.

        Returns:
            SearchDataResponse with query-level data.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        url = f"{BWT_API_BASE}/GetQueryStats"
        params = {
            "siteUrl": property_id,
            "apikey": self.access_token,
        }

        response_data = await self._retry_with_backoff(
            self._make_request,
            url=url,
            params=params,
        )

        rows = self._parse_query_stats(response_data, date_range)

        return SearchDataResponse(
            rows=rows,
            total_rows=len(rows),
        )

    async def fetch_page_stats(
        self,
        property_id: str,
        date_range: DateRange,
    ) -> SearchDataResponse:
        """
        Fetch page-level statistics from BWT.

        Args:
            property_id: BWT site URL.
            date_range: Date range to fetch data for.

        Returns:
            SearchDataResponse with page-level data.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        url = f"{BWT_API_BASE}/GetPageStats"
        params = {
            "siteUrl": property_id,
            "apikey": self.access_token,
        }

        response_data = await self._retry_with_backoff(
            self._make_request,
            url=url,
            params=params,
        )

        rows = self._parse_page_stats(response_data, date_range)

        return SearchDataResponse(
            rows=rows,
            total_rows=len(rows),
        )

    async def _make_request(
        self,
        url: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Make an authenticated request to the BWT API.

        Args:
            url: Full API URL.
            params: Query parameters.

        Returns:
            Parsed JSON response (list of stats).

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result: list[dict[str, Any]] = response.json()
            return result

    def _parse_query_stats(
        self,
        data: list[dict[str, Any]],
        date_range: DateRange,
    ) -> list[SearchDataRow]:
        """
        Parse BWT query stats into SearchDataRows.

        Args:
            data: Raw API response data.
            date_range: Date range for filtering.

        Returns:
            List of parsed SearchDataRows.
        """
        rows: list[SearchDataRow] = []

        for item in data:
            try:
                # Parse date from ISO format
                date_str = item.get("Date", "")
                row_date = self._parse_bwt_date(date_str)

                # Filter to date range
                if row_date and (row_date < date_range.start_date or row_date > date_range.end_date):
                    continue

                impressions = int(item.get("Impressions", 0))
                clicks = int(item.get("Clicks", 0))

                # Calculate CTR
                ctr = None
                if impressions > 0:
                    ctr = Decimal(clicks) / Decimal(impressions)
                    ctr = ctr.quantize(Decimal("0.0001"))

                rows.append(
                    SearchDataRow(
                        date=row_date or date_range.start_date,
                        query=item.get("Query"),
                        page_url=None,
                        clicks=clicks,
                        impressions=impressions,
                        ctr=ctr,
                        position=None,  # BWT doesn't provide position
                        device=None,
                        country=None,
                        search_type="web",
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse BWT query stats row: {e}")
                continue

        return rows

    def _parse_page_stats(
        self,
        data: list[dict[str, Any]],
        date_range: DateRange,
    ) -> list[SearchDataRow]:
        """
        Parse BWT page stats into SearchDataRows.

        Args:
            data: Raw API response data.
            date_range: Date range for filtering.

        Returns:
            List of parsed SearchDataRows.
        """
        rows: list[SearchDataRow] = []

        for item in data:
            try:
                # Parse date from ISO format
                date_str = item.get("Date", "")
                row_date = self._parse_bwt_date(date_str)

                # Filter to date range
                if row_date and (row_date < date_range.start_date or row_date > date_range.end_date):
                    continue

                impressions = int(item.get("Impressions", 0))
                clicks = int(item.get("Clicks", 0))

                # Calculate CTR
                ctr = None
                if impressions > 0:
                    ctr = Decimal(clicks) / Decimal(impressions)
                    ctr = ctr.quantize(Decimal("0.0001"))

                rows.append(
                    SearchDataRow(
                        date=row_date or date_range.start_date,
                        query=None,
                        page_url=item.get("Url"),
                        clicks=clicks,
                        impressions=impressions,
                        ctr=ctr,
                        position=None,
                        device=None,
                        country=None,
                        search_type="web",
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse BWT page stats row: {e}")
                continue

        return rows

    def _parse_bwt_date(self, date_str: str) -> date | None:
        """
        Parse a BWT date string into a date object.

        Args:
            date_str: Date string in ISO format (e.g., "2024-01-01T00:00:00Z").

        Returns:
            Parsed date, or None if parsing fails.
        """
        if not date_str:
            return None

        try:
            # Handle ISO format with timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.date()
        except ValueError:
            try:
                # Try simple date format
                return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
