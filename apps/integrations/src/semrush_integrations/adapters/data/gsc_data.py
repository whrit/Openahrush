"""
Google Search Console data adapter.

Fetches search performance data from Google Search Console using the
searchAnalytics.query API endpoint.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from semrush_integrations.adapters.data.base import DataAdapter, DateRange
from semrush_integrations.schemas.search_data import SearchDataResponse, SearchDataRow

logger = logging.getLogger(__name__)

# GSC API constants
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
GSC_MAX_ROWS = 25000  # Maximum rows per request
DEFAULT_DIMENSIONS = ["query", "page", "device", "country", "searchAppearance"]


class GSCDataAdapter(DataAdapter):
    """
    Google Search Console data adapter.

    Fetches search performance data using the searchAnalytics.query API.
    Supports all GSC dimensions (query, page, device, country, searchAppearance)
    and handles pagination for large result sets.

    Example:
        >>> adapter = GSCDataAdapter(access_token="ya29.xxx")
        >>> response = await adapter.fetch_data(
        ...     property_id="https://example.com/",
        ...     date_range=DateRange(date(2024, 1, 1), date(2024, 1, 7)),
        ...     dimensions=["query", "page"],
        ... )
        >>> for row in response.rows:
        ...     print(f"{row.query}: {row.clicks} clicks")
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "google_search_console"

    @property
    def data_type(self) -> str:
        """Return the data type."""
        return "search"

    async def fetch_data(
        self,
        property_id: str,
        date_range: DateRange,
        dimensions: list[str] | None = None,
        search_type: str = "web",
        row_limit: int | None = None,
        **kwargs,
    ) -> SearchDataResponse:
        """
        Fetch search performance data from Google Search Console.

        Args:
            property_id: GSC property URL (e.g., "https://example.com/").
            date_range: Date range to fetch data for.
            dimensions: List of dimensions to include (query, page, device, country).
            search_type: Type of search (web, image, video, news, discover).
            row_limit: Maximum total rows to fetch (None for all available).
            **kwargs: Additional filters to apply.

        Returns:
            SearchDataResponse containing all fetched rows.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        if dimensions is None:
            dimensions = DEFAULT_DIMENSIONS

        all_rows: list[SearchDataRow] = []
        start_row = 0
        total_fetched = 0
        max_rows = row_limit or float("inf")

        # URL-encode the property ID for the API URL
        encoded_property = quote(property_id, safe="")
        url = f"{GSC_API_BASE}/sites/{encoded_property}/searchAnalytics/query"

        while total_fetched < max_rows:
            rows_to_fetch = min(GSC_MAX_ROWS, max_rows - total_fetched)

            request_body = {
                "startDate": date_range.start_date.isoformat(),
                "endDate": date_range.end_date.isoformat(),
                "dimensions": dimensions,
                "searchType": search_type,
                "rowLimit": rows_to_fetch,
                "startRow": start_row,
            }

            # Add any additional filters
            if kwargs.get("dimension_filter_groups"):
                request_body["dimensionFilterGroups"] = kwargs["dimension_filter_groups"]

            response_data = await self._retry_with_backoff(
                self._make_request,
                url=url,
                body=request_body,
            )

            rows = response_data.get("rows", [])
            if not rows:
                break

            # Parse the response rows
            for row in rows:
                parsed_row = self._parse_row(row, dimensions, date_range.start_date)
                all_rows.append(parsed_row)

            total_fetched += len(rows)
            start_row += len(rows)

            # If we got fewer rows than requested, we've reached the end
            if len(rows) < rows_to_fetch:
                break

        return SearchDataResponse(
            rows=all_rows,
            total_rows=len(all_rows),
            response_aggregation_type=response_data.get("responseAggregationType"),
        )

    async def _make_request(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """
        Make an authenticated request to the GSC API.

        Args:
            url: Full API URL.
            body: Request body as a dictionary.

        Returns:
            Parsed JSON response.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def _parse_row(
        self,
        row: dict[str, Any],
        dimensions: list[str],
        fallback_date: date,
    ) -> SearchDataRow:
        """
        Parse a GSC API row into a SearchDataRow.

        Args:
            row: Raw row from GSC API response.
            dimensions: List of dimensions that were requested.
            fallback_date: Date to use if date is not in dimensions.

        Returns:
            Parsed SearchDataRow.
        """
        keys = row.get("keys", [])

        # Map dimension indices to values
        dimension_values: dict[str, str] = {}
        for i, dim in enumerate(dimensions):
            if i < len(keys):
                dimension_values[dim] = keys[i]

        # Extract metrics
        clicks = int(row.get("clicks", 0))
        impressions = int(row.get("impressions", 0))
        ctr = Decimal(str(row.get("ctr", 0)))
        position = Decimal(str(row.get("position", 0)))

        # Round CTR and position to 4 decimal places
        ctr = ctr.quantize(Decimal("0.0001"))
        position = position.quantize(Decimal("0.01"))

        return SearchDataRow(
            date=fallback_date,
            query=dimension_values.get("query"),
            page_url=dimension_values.get("page"),
            clicks=clicks,
            impressions=impressions,
            ctr=ctr,
            position=position,
            device=dimension_values.get("device"),
            country=dimension_values.get("country"),
            search_type=dimension_values.get("searchAppearance"),
        )
