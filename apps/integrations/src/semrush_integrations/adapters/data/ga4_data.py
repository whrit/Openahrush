"""
Google Analytics 4 data adapter.

Fetches analytics data from Google Analytics 4 using the
Data API runReport endpoint.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from semrush_integrations.adapters.data.base import DataAdapter, DateRange
from semrush_integrations.schemas.analytics_data import AnalyticsDataResponse, AnalyticsDataRow

logger = logging.getLogger(__name__)

# GA4 API constants
GA4_API_BASE = "https://analyticsdata.googleapis.com/v1beta"
GA4_MAX_ROWS = 100000  # Maximum rows per request

DEFAULT_DIMENSIONS = [
    "date",
    "pagePath",
    "country",
    "deviceCategory",
    "sessionSourceMedium",
]

DEFAULT_METRICS = [
    "sessions",
    "totalUsers",
    "engagementRate",
    "conversions",
    "totalRevenue",
]


class GA4DataAdapter(DataAdapter):
    """
    Google Analytics 4 data adapter.

    Fetches analytics data using the GA4 Data API runReport endpoint.
    Supports various dimensions and metrics for comprehensive analytics data.

    Example:
        >>> adapter = GA4DataAdapter(access_token="ya29.xxx")
        >>> response = await adapter.fetch_data(
        ...     property_id="properties/123456789",
        ...     date_range=DateRange(date(2024, 1, 1), date(2024, 1, 7)),
        ...     dimensions=["date", "pagePath"],
        ... )
        >>> for row in response.rows:
        ...     print(f"{row.page_url}: {row.sessions} sessions")
    """

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "google_analytics"

    @property
    def data_type(self) -> str:
        """Return the data type."""
        return "analytics"

    async def fetch_data(
        self,
        property_id: str,
        date_range: DateRange,
        dimensions: list[str] | None = None,
        metrics: list[str] | None = None,
        row_limit: int | None = None,
        **kwargs,
    ) -> AnalyticsDataResponse:
        """
        Fetch analytics data from Google Analytics 4.

        Args:
            property_id: GA4 property ID (e.g., "properties/123456789").
            date_range: Date range to fetch data for.
            dimensions: List of dimensions to include.
            metrics: List of metrics to include.
            row_limit: Maximum total rows to fetch (None for all available).
            **kwargs: Additional options like dimension_filter.

        Returns:
            AnalyticsDataResponse containing all fetched rows.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        if dimensions is None:
            dimensions = DEFAULT_DIMENSIONS
        if metrics is None:
            metrics = DEFAULT_METRICS

        # Extract numeric property ID from the full property string
        numeric_id = property_id.replace("properties/", "")
        url = f"{GA4_API_BASE}/properties/{numeric_id}:runReport"

        all_rows: list[AnalyticsDataRow] = []
        offset = 0
        max_rows = row_limit or float("inf")

        while len(all_rows) < max_rows:
            rows_to_fetch = min(GA4_MAX_ROWS, max_rows - len(all_rows))

            request_body = {
                "dateRanges": [
                    {
                        "startDate": date_range.start_date.isoformat(),
                        "endDate": date_range.end_date.isoformat(),
                    }
                ],
                "dimensions": [{"name": dim} for dim in dimensions],
                "metrics": [{"name": metric} for metric in metrics],
                "limit": rows_to_fetch,
                "offset": offset,
            }

            # Add dimension filter if provided
            if kwargs.get("dimension_filter"):
                request_body["dimensionFilter"] = kwargs["dimension_filter"]

            response_data = await self._retry_with_backoff(
                self._make_request,
                url=url,
                body=request_body,
            )

            rows = response_data.get("rows", [])
            if not rows:
                break

            # Get headers for parsing
            dimension_headers = [h["name"] for h in response_data.get("dimensionHeaders", [])]
            metric_headers = [h["name"] for h in response_data.get("metricHeaders", [])]

            # Parse the response rows
            for row in rows:
                parsed_row = self._parse_row(row, dimension_headers, metric_headers)
                if parsed_row:
                    all_rows.append(parsed_row)

            offset += len(rows)

            # Check if we've fetched all available rows
            total_rows = response_data.get("rowCount", 0)
            if offset >= total_rows:
                break

        return AnalyticsDataResponse(
            rows=all_rows,
            total_rows=len(all_rows),
            sampling_info=self._extract_sampling_info(response_data) if response_data else None,
        )

    async def _make_request(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """
        Make an authenticated request to the GA4 API.

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
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    def _parse_row(
        self,
        row: dict[str, Any],
        dimension_headers: list[str],
        metric_headers: list[str],
    ) -> AnalyticsDataRow | None:
        """
        Parse a GA4 API row into an AnalyticsDataRow.

        Args:
            row: Raw row from GA4 API response.
            dimension_headers: List of dimension names.
            metric_headers: List of metric names.

        Returns:
            Parsed AnalyticsDataRow, or None if parsing fails.
        """
        try:
            # Extract dimension values
            dimension_values = row.get("dimensionValues", [])
            dimensions: dict[str, str] = {}
            for i, header in enumerate(dimension_headers):
                if i < len(dimension_values):
                    dimensions[header] = dimension_values[i].get("value", "")

            # Extract metric values
            metric_values = row.get("metricValues", [])
            metrics: dict[str, str] = {}
            for i, header in enumerate(metric_headers):
                if i < len(metric_values):
                    metrics[header] = metric_values[i].get("value", "0")

            # Parse date from YYYYMMDD format
            date_str = dimensions.get("date", "")
            row_date = datetime.strptime(date_str, "%Y%m%d").date() if date_str else date.today()

            # Parse numeric values with proper handling
            sessions = int(metrics.get("sessions", 0))
            users = int(metrics.get("totalUsers", 0)) if "totalUsers" in metrics else None
            engagement_rate = (
                Decimal(metrics.get("engagementRate", "0")).quantize(Decimal("0.0001"))
                if "engagementRate" in metrics
                else None
            )
            conversions = (
                int(metrics.get("conversions", 0)) if "conversions" in metrics else None
            )
            revenue = (
                Decimal(metrics.get("totalRevenue", "0")).quantize(Decimal("0.01"))
                if "totalRevenue" in metrics
                else None
            )

            return AnalyticsDataRow(
                date=row_date,
                page_url=dimensions.get("pagePath"),
                sessions=sessions,
                users=users,
                engagement_rate=engagement_rate,
                conversions=conversions,
                revenue=revenue,
                country=dimensions.get("country"),
                device=dimensions.get("deviceCategory"),
                source_medium=dimensions.get("sessionSourceMedium"),
                campaign=dimensions.get("sessionCampaignName"),
            )
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse GA4 row: {e}")
            return None

    def _extract_sampling_info(self, response_data: dict[str, Any]) -> dict[str, str] | None:
        """
        Extract sampling information from GA4 response.

        Args:
            response_data: Full API response.

        Returns:
            Dictionary with sampling info, or None if not sampled.
        """
        metadata = response_data.get("metadata", {})
        if metadata.get("dataLossFromOtherRow"):
            return {"dataLossFromOtherRow": "true"}
        if "samplingMetadatas" in metadata:
            return {"sampled": "true"}
        return None
