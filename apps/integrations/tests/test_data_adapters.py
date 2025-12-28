"""
Comprehensive tests for provider data adapters.

Tests cover:
- GSC (Google Search Console) data adapter
- GA4 (Google Analytics 4) data adapter
- BWT (Bing Webmaster Tools) data adapter
- DataSyncService orchestration
- Rate limiting and error handling
- Batch insert operations
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
from semrush_integrations.adapters.data.base import DataAdapter, DateRange
from semrush_integrations.adapters.data.bwt_data import BWTDataAdapter
from semrush_integrations.adapters.data.ga4_data import GA4DataAdapter
from semrush_integrations.adapters.data.gsc_data import GSCDataAdapter
from semrush_integrations.schemas.analytics_data import AnalyticsDataResponse, AnalyticsDataRow
from semrush_integrations.schemas.search_data import SearchDataResponse, SearchDataRow
from semrush_integrations.services.data_sync_service import DataSyncService

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def date_range() -> DateRange:
    """Create a sample date range for testing."""
    return DateRange(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 7),
    )


@pytest.fixture
def access_token() -> str:
    """Sample OAuth access token."""
    return "ya29.test-access-token"


@pytest.fixture
def gsc_property_id() -> str:
    """Sample GSC property ID (site URL)."""
    return "https://example.com/"


@pytest.fixture
def ga4_property_id() -> str:
    """Sample GA4 property ID."""
    return "properties/123456789"


@pytest.fixture
def bwt_property_id() -> str:
    """Sample BWT site URL."""
    return "https://example.com"


@pytest.fixture
def project_id() -> uuid.UUID:
    """Sample project UUID."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def site_id() -> uuid.UUID:
    """Sample site UUID."""
    return uuid.UUID("87654321-4321-8765-4321-876543218765")


@pytest.fixture
def mapping_id() -> uuid.UUID:
    """Sample integration mapping UUID."""
    return uuid.UUID("abcdef12-1234-5678-abcd-abcdef123456")


# =============================================================================
# Pydantic Schema Tests
# =============================================================================


class TestSearchDataSchemas:
    """Test Pydantic schemas for search data."""

    def test_search_data_row_creation(self) -> None:
        """Test creating a SearchDataRow with all fields."""
        row = SearchDataRow(
            date=date(2024, 1, 1),
            query="test query",
            page_url="https://example.com/page",
            clicks=100,
            impressions=1000,
            ctr=Decimal("0.1000"),
            position=Decimal("3.50"),
            device="desktop",
            country="usa",
            search_type="web",
        )
        assert row.query == "test query"
        assert row.clicks == 100
        assert row.impressions == 1000
        assert row.ctr == Decimal("0.1000")
        assert row.position == Decimal("3.50")

    def test_search_data_row_optional_fields(self) -> None:
        """Test SearchDataRow with minimal fields."""
        row = SearchDataRow(
            date=date(2024, 1, 1),
            clicks=50,
            impressions=500,
        )
        assert row.query is None
        assert row.page_url is None
        assert row.device is None
        assert row.country is None

    def test_search_data_response(self) -> None:
        """Test SearchDataResponse container."""
        rows = [
            SearchDataRow(date=date(2024, 1, 1), clicks=10, impressions=100),
            SearchDataRow(date=date(2024, 1, 2), clicks=20, impressions=200),
        ]
        response = SearchDataResponse(rows=rows, total_rows=2)
        assert len(response.rows) == 2
        assert response.total_rows == 2

    def test_search_data_row_ctr_validation(self) -> None:
        """Test CTR is between 0 and 1."""
        row = SearchDataRow(
            date=date(2024, 1, 1),
            clicks=10,
            impressions=100,
            ctr=Decimal("0.1000"),
        )
        assert Decimal("0") <= row.ctr <= Decimal("1")


class TestAnalyticsDataSchemas:
    """Test Pydantic schemas for analytics data."""

    def test_analytics_data_row_creation(self) -> None:
        """Test creating an AnalyticsDataRow with all fields."""
        row = AnalyticsDataRow(
            date=date(2024, 1, 1),
            page_url="/page",
            sessions=100,
            users=80,
            engagement_rate=Decimal("0.6500"),
            conversions=10,
            revenue=Decimal("500.00"),
            country="usa",
            device="desktop",
            source_medium="google / organic",
            campaign=None,
        )
        assert row.sessions == 100
        assert row.users == 80
        assert row.engagement_rate == Decimal("0.6500")

    def test_analytics_data_row_optional_fields(self) -> None:
        """Test AnalyticsDataRow with minimal fields."""
        row = AnalyticsDataRow(
            date=date(2024, 1, 1),
            sessions=50,
        )
        assert row.page_url is None
        assert row.users is None
        assert row.engagement_rate is None

    def test_analytics_data_response(self) -> None:
        """Test AnalyticsDataResponse container."""
        rows = [
            AnalyticsDataRow(date=date(2024, 1, 1), sessions=100),
            AnalyticsDataRow(date=date(2024, 1, 2), sessions=200),
        ]
        response = AnalyticsDataResponse(rows=rows, total_rows=2)
        assert len(response.rows) == 2


# =============================================================================
# Base DataAdapter Tests
# =============================================================================


class TestDateRange:
    """Test DateRange dataclass."""

    def test_date_range_days(self, date_range: DateRange) -> None:
        """Test calculating days in range."""
        assert date_range.days == 7

    def test_date_range_iteration(self, date_range: DateRange) -> None:
        """Test iterating over dates in range."""
        dates = list(date_range)
        assert len(dates) == 7
        assert dates[0] == date(2024, 1, 1)
        assert dates[-1] == date(2024, 1, 7)


class TestBaseDataAdapter:
    """Test abstract base DataAdapter."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Test that DataAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataAdapter()  # type: ignore

    def test_subclass_must_implement_fetch_data(self) -> None:
        """Test that subclasses must implement fetch_data."""

        class IncompleteAdapter(DataAdapter):
            @property
            def provider_name(self) -> str:
                return "test"

            @property
            def data_type(self) -> str:
                return "search"

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore


# =============================================================================
# GSC Data Adapter Tests
# =============================================================================


class TestGSCDataAdapter:
    """Test Google Search Console data adapter."""

    @pytest.fixture
    def gsc_adapter(self, access_token: str) -> GSCDataAdapter:
        """Create GSC adapter instance."""
        return GSCDataAdapter(access_token=access_token)

    @pytest.fixture
    def sample_gsc_response(self) -> dict[str, Any]:
        """Sample GSC searchAnalytics.query response."""
        return {
            "rows": [
                {
                    "keys": ["test query", "https://example.com/page", "DESKTOP", "usa", "web"],
                    "clicks": 100,
                    "impressions": 1000,
                    "ctr": 0.1,
                    "position": 3.5,
                },
                {
                    "keys": ["another query", "https://example.com/other", "MOBILE", "gbr", "web"],
                    "clicks": 50,
                    "impressions": 500,
                    "ctr": 0.1,
                    "position": 5.2,
                },
            ],
            "responseAggregationType": "byProperty",
        }

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_data_success(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
        sample_gsc_response: dict[str, Any],
    ) -> None:
        """Test successful GSC data fetch."""
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(return_value=httpx.Response(200, json=sample_gsc_response))

        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
        )

        assert isinstance(response, SearchDataResponse)
        assert len(response.rows) == 2
        assert response.rows[0].query == "test query"
        assert response.rows[0].clicks == 100
        assert response.rows[0].impressions == 1000
        assert response.rows[0].device == "desktop"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_data_with_dimensions(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GSC fetch with specific dimensions."""
        mock_response = {
            "rows": [
                {"keys": ["query1"], "clicks": 10, "impressions": 100, "ctr": 0.1, "position": 2.0}
            ]
        }
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
            dimensions=["query"],
        )

        assert len(response.rows) == 1
        assert response.rows[0].query == "query1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_data_empty_response(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GSC fetch with no data."""
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(return_value=httpx.Response(200, json={}))

        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
        )

        assert len(response.rows) == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_data_api_error(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GSC fetch handles API errors gracefully."""
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(return_value=httpx.Response(500, json={"error": {"message": "Internal error"}}))

        with pytest.raises(httpx.HTTPStatusError):
            await gsc_adapter.fetch_data(
                property_id=gsc_property_id,
                date_range=date_range,
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_data_rate_limiting(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GSC adapter respects rate limits."""
        # First request returns 429
        route = respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        )
        route.side_effect = [
            httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}}),
            httpx.Response(200, json={"rows": []}),
        ]

        # Should retry after rate limit
        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
        )
        assert len(response.rows) == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_handles_pagination(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GSC adapter handles paginated responses."""
        page1 = {
            "rows": [
                {"keys": [f"query{i}"], "clicks": i, "impressions": i * 10, "ctr": 0.1, "position": 1.0}
                for i in range(25000)
            ]
        }
        page2 = {
            "rows": [
                {"keys": [f"query{i}"], "clicks": i, "impressions": i * 10, "ctr": 0.1, "position": 1.0}
                for i in range(25000, 30000)
            ]
        }

        route = respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        )
        route.side_effect = [
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]

        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
            row_limit=50000,
        )

        assert len(response.rows) == 30000

    def test_gsc_adapter_provider_name(self, gsc_adapter: GSCDataAdapter) -> None:
        """Test GSC adapter provider name."""
        assert gsc_adapter.provider_name == "google_search_console"

    def test_gsc_adapter_data_type(self, gsc_adapter: GSCDataAdapter) -> None:
        """Test GSC adapter data type."""
        assert gsc_adapter.data_type == "search"


# =============================================================================
# GA4 Data Adapter Tests
# =============================================================================


class TestGA4DataAdapter:
    """Test Google Analytics 4 data adapter."""

    @pytest.fixture
    def ga4_adapter(self, access_token: str) -> GA4DataAdapter:
        """Create GA4 adapter instance."""
        return GA4DataAdapter(access_token=access_token)

    @pytest.fixture
    def sample_ga4_response(self) -> dict[str, Any]:
        """Sample GA4 runReport response."""
        return {
            "dimensionHeaders": [
                {"name": "date"},
                {"name": "pagePath"},
                {"name": "country"},
                {"name": "deviceCategory"},
                {"name": "sessionSourceMedium"},
            ],
            "metricHeaders": [
                {"name": "sessions", "type": "TYPE_INTEGER"},
                {"name": "totalUsers", "type": "TYPE_INTEGER"},
                {"name": "engagementRate", "type": "TYPE_FLOAT"},
                {"name": "conversions", "type": "TYPE_INTEGER"},
                {"name": "totalRevenue", "type": "TYPE_FLOAT"},
            ],
            "rows": [
                {
                    "dimensionValues": [
                        {"value": "20240101"},
                        {"value": "/page"},
                        {"value": "United States"},
                        {"value": "desktop"},
                        {"value": "google / organic"},
                    ],
                    "metricValues": [
                        {"value": "100"},
                        {"value": "80"},
                        {"value": "0.65"},
                        {"value": "10"},
                        {"value": "500.00"},
                    ],
                },
                {
                    "dimensionValues": [
                        {"value": "20240101"},
                        {"value": "/other"},
                        {"value": "United Kingdom"},
                        {"value": "mobile"},
                        {"value": "bing / cpc"},
                    ],
                    "metricValues": [
                        {"value": "50"},
                        {"value": "40"},
                        {"value": "0.55"},
                        {"value": "5"},
                        {"value": "200.00"},
                    ],
                },
            ],
            "rowCount": 2,
        }

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_analytics_data_success(
        self,
        ga4_adapter: GA4DataAdapter,
        ga4_property_id: str,
        date_range: DateRange,
        sample_ga4_response: dict[str, Any],
    ) -> None:
        """Test successful GA4 data fetch."""
        respx.post(
            "https://analyticsdata.googleapis.com/v1beta/properties/123456789:runReport"
        ).mock(return_value=httpx.Response(200, json=sample_ga4_response))

        response = await ga4_adapter.fetch_data(
            property_id=ga4_property_id,
            date_range=date_range,
        )

        assert isinstance(response, AnalyticsDataResponse)
        assert len(response.rows) == 2
        assert response.rows[0].sessions == 100
        assert response.rows[0].users == 80
        assert response.rows[0].engagement_rate == Decimal("0.6500")
        assert response.rows[0].page_url == "/page"
        assert response.rows[0].device == "desktop"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_analytics_data_empty_response(
        self,
        ga4_adapter: GA4DataAdapter,
        ga4_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GA4 fetch with no data."""
        respx.post(
            "https://analyticsdata.googleapis.com/v1beta/properties/123456789:runReport"
        ).mock(return_value=httpx.Response(200, json={"rowCount": 0}))

        response = await ga4_adapter.fetch_data(
            property_id=ga4_property_id,
            date_range=date_range,
        )

        assert len(response.rows) == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_analytics_data_api_error(
        self,
        ga4_adapter: GA4DataAdapter,
        ga4_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GA4 fetch handles API errors gracefully."""
        respx.post(
            "https://analyticsdata.googleapis.com/v1beta/properties/123456789:runReport"
        ).mock(return_value=httpx.Response(403, json={"error": {"message": "Permission denied"}}))

        with pytest.raises(httpx.HTTPStatusError):
            await ga4_adapter.fetch_data(
                property_id=ga4_property_id,
                date_range=date_range,
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_analytics_data_with_custom_dimensions(
        self,
        ga4_adapter: GA4DataAdapter,
        ga4_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test GA4 fetch with custom dimensions."""
        mock_response = {
            "dimensionHeaders": [{"name": "date"}, {"name": "pagePath"}],
            "metricHeaders": [{"name": "sessions", "type": "TYPE_INTEGER"}],
            "rows": [
                {
                    "dimensionValues": [{"value": "20240101"}, {"value": "/custom"}],
                    "metricValues": [{"value": "50"}],
                }
            ],
            "rowCount": 1,
        }
        respx.post(
            "https://analyticsdata.googleapis.com/v1beta/properties/123456789:runReport"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        response = await ga4_adapter.fetch_data(
            property_id=ga4_property_id,
            date_range=date_range,
            dimensions=["date", "pagePath"],
        )

        assert len(response.rows) == 1
        assert response.rows[0].page_url == "/custom"

    def test_ga4_adapter_provider_name(self, ga4_adapter: GA4DataAdapter) -> None:
        """Test GA4 adapter provider name."""
        assert ga4_adapter.provider_name == "google_analytics"

    def test_ga4_adapter_data_type(self, ga4_adapter: GA4DataAdapter) -> None:
        """Test GA4 adapter data type."""
        assert ga4_adapter.data_type == "analytics"


# =============================================================================
# BWT Data Adapter Tests
# =============================================================================


class TestBWTDataAdapter:
    """Test Bing Webmaster Tools data adapter."""

    @pytest.fixture
    def bwt_adapter(self, access_token: str) -> BWTDataAdapter:
        """Create BWT adapter instance."""
        return BWTDataAdapter(access_token=access_token)

    @pytest.fixture
    def sample_bwt_query_response(self) -> list[dict[str, Any]]:
        """Sample BWT GetQueryStats response."""
        return [
            {
                "Query": "test query",
                "Impressions": 1000,
                "Clicks": 100,
                "Date": "2024-01-01T00:00:00Z",
            },
            {
                "Query": "another query",
                "Impressions": 500,
                "Clicks": 50,
                "Date": "2024-01-01T00:00:00Z",
            },
        ]

    @pytest.fixture
    def sample_bwt_page_response(self) -> list[dict[str, Any]]:
        """Sample BWT GetPageStats response."""
        return [
            {
                "Url": "https://example.com/page",
                "Impressions": 1000,
                "Clicks": 100,
                "Date": "2024-01-01T00:00:00Z",
            },
            {
                "Url": "https://example.com/other",
                "Impressions": 500,
                "Clicks": 50,
                "Date": "2024-01-01T00:00:00Z",
            },
        ]

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_search_data_success(
        self,
        bwt_adapter: BWTDataAdapter,
        bwt_property_id: str,
        date_range: DateRange,
        sample_bwt_query_response: list[dict[str, Any]],
        sample_bwt_page_response: list[dict[str, Any]],
    ) -> None:
        """Test successful BWT data fetch."""
        # Mock query stats
        respx.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats"
        ).mock(return_value=httpx.Response(200, json=sample_bwt_query_response))

        # Mock page stats
        respx.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetPageStats"
        ).mock(return_value=httpx.Response(200, json=sample_bwt_page_response))

        response = await bwt_adapter.fetch_data(
            property_id=bwt_property_id,
            date_range=date_range,
        )

        assert isinstance(response, SearchDataResponse)
        assert len(response.rows) >= 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_query_stats(
        self,
        bwt_adapter: BWTDataAdapter,
        bwt_property_id: str,
        date_range: DateRange,
        sample_bwt_query_response: list[dict[str, Any]],
    ) -> None:
        """Test fetching BWT query stats."""
        respx.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats"
        ).mock(return_value=httpx.Response(200, json=sample_bwt_query_response))

        response = await bwt_adapter.fetch_query_stats(
            property_id=bwt_property_id,
            date_range=date_range,
        )

        assert len(response.rows) == 2
        assert response.rows[0].query == "test query"
        assert response.rows[0].clicks == 100
        assert response.rows[0].impressions == 1000

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_page_stats(
        self,
        bwt_adapter: BWTDataAdapter,
        bwt_property_id: str,
        date_range: DateRange,
        sample_bwt_page_response: list[dict[str, Any]],
    ) -> None:
        """Test fetching BWT page stats."""
        respx.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetPageStats"
        ).mock(return_value=httpx.Response(200, json=sample_bwt_page_response))

        response = await bwt_adapter.fetch_page_stats(
            property_id=bwt_property_id,
            date_range=date_range,
        )

        assert len(response.rows) == 2
        assert response.rows[0].page_url == "https://example.com/page"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_data_api_error(
        self,
        bwt_adapter: BWTDataAdapter,
        bwt_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test BWT fetch handles API errors gracefully."""
        respx.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats"
        ).mock(return_value=httpx.Response(401, json={"message": "Unauthorized"}))

        with pytest.raises(httpx.HTTPStatusError):
            await bwt_adapter.fetch_query_stats(
                property_id=bwt_property_id,
                date_range=date_range,
            )

    def test_bwt_adapter_provider_name(self, bwt_adapter: BWTDataAdapter) -> None:
        """Test BWT adapter provider name."""
        assert bwt_adapter.provider_name == "bing_webmaster_tools"

    def test_bwt_adapter_data_type(self, bwt_adapter: BWTDataAdapter) -> None:
        """Test BWT adapter data type."""
        assert bwt_adapter.data_type == "search"

    def test_bwt_adapter_engine(self, bwt_adapter: BWTDataAdapter) -> None:
        """Test BWT adapter engine is bing."""
        assert bwt_adapter.engine == "bing"


# =============================================================================
# DataSyncService Tests
# =============================================================================


class TestDataSyncService:
    """Test DataSyncService orchestration."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock SQLAlchemy session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        session.add_all = MagicMock()
        return session

    @pytest.fixture
    def mock_mapping(self, mapping_id: uuid.UUID, project_id: uuid.UUID) -> MagicMock:
        """Create mock IntegrationMapping."""
        mapping = MagicMock()
        mapping.id = mapping_id
        mapping.project_id = project_id
        mapping.site_id = None
        mapping.integration_property = MagicMock()
        mapping.integration_property.provider = "google_search_console"
        mapping.integration_property.property_id = "https://example.com/"
        mapping.integration_property.account = MagicMock()
        mapping.integration_property.account.access_token = "test-token"
        return mapping

    @pytest.fixture
    def sync_service(self, mock_session: MagicMock) -> DataSyncService:
        """Create DataSyncService instance."""
        return DataSyncService(session=mock_session)

    @pytest.mark.asyncio
    async def test_sync_search_data_creates_sync_run(
        self,
        sync_service: DataSyncService,
        mock_mapping: MagicMock,
        date_range: DateRange,
    ) -> None:
        """Test that sync_search_data creates a SyncRun record."""
        with patch.object(sync_service, "_fetch_and_store_search_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = 100

            sync_run = await sync_service.sync_search_data(
                mapping=mock_mapping,
                date_range=date_range,
            )

            assert sync_run.status == "completed"
            assert sync_run.records_written == 100

    @pytest.mark.asyncio
    async def test_sync_search_data_handles_errors(
        self,
        sync_service: DataSyncService,
        mock_mapping: MagicMock,
        date_range: DateRange,
    ) -> None:
        """Test that sync_search_data handles errors and marks sync as failed."""
        with patch.object(sync_service, "_fetch_and_store_search_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            sync_run = await sync_service.sync_search_data(
                mapping=mock_mapping,
                date_range=date_range,
            )

            assert sync_run.status == "failed"
            assert "API Error" in sync_run.error_message

    @pytest.mark.asyncio
    async def test_sync_analytics_data_creates_sync_run(
        self,
        sync_service: DataSyncService,
        mock_session: MagicMock,
        project_id: uuid.UUID,
        date_range: DateRange,
    ) -> None:
        """Test that sync_analytics_data creates a SyncRun record."""
        mock_mapping = MagicMock()
        mock_mapping.id = uuid.uuid4()
        mock_mapping.project_id = project_id
        mock_mapping.site_id = None
        mock_mapping.integration_property = MagicMock()
        mock_mapping.integration_property.provider = "google_analytics"
        mock_mapping.integration_property.property_id = "properties/123456789"
        mock_mapping.integration_property.account = MagicMock()
        mock_mapping.integration_property.account.access_token = "test-token"

        with patch.object(sync_service, "_fetch_and_store_analytics_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = 50

            sync_run = await sync_service.sync_analytics_data(
                mapping=mock_mapping,
                date_range=date_range,
            )

            assert sync_run.status == "completed"
            assert sync_run.records_written == 50

    @pytest.mark.asyncio
    async def test_batch_insert_search_facts(
        self,
        sync_service: DataSyncService,
        mock_session: MagicMock,
        project_id: uuid.UUID,
    ) -> None:
        """Test batch insert of search facts."""
        rows = [
            SearchDataRow(
                date=date(2024, 1, 1),
                query=f"query{i}",
                clicks=i,
                impressions=i * 10,
            )
            for i in range(2500)  # More than batch size of 1000
        ]

        count = await sync_service._batch_insert_search_facts(
            rows=rows,
            project_id=project_id,
            engine="google",
        )

        assert count == 2500
        # Should have been called 3 times (1000, 1000, 500)
        assert mock_session.add_all.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_insert_analytics_facts(
        self,
        sync_service: DataSyncService,
        mock_session: MagicMock,
        project_id: uuid.UUID,
    ) -> None:
        """Test batch insert of analytics facts."""
        rows = [
            AnalyticsDataRow(date=date(2024, 1, 1), sessions=i)
            for i in range(1500)
        ]

        count = await sync_service._batch_insert_analytics_facts(
            rows=rows,
            project_id=project_id,
        )

        assert count == 1500
        # Should have been called 2 times (1000, 500)
        assert mock_session.add_all.call_count == 2

    @pytest.mark.asyncio
    async def test_get_adapter_for_gsc(self, sync_service: DataSyncService) -> None:
        """Test getting correct adapter for GSC."""
        adapter = sync_service._get_data_adapter(
            provider="google_search_console",
            access_token="test-token",
        )
        assert isinstance(adapter, GSCDataAdapter)

    @pytest.mark.asyncio
    async def test_get_adapter_for_ga4(self, sync_service: DataSyncService) -> None:
        """Test getting correct adapter for GA4."""
        adapter = sync_service._get_data_adapter(
            provider="google_analytics",
            access_token="test-token",
        )
        assert isinstance(adapter, GA4DataAdapter)

    @pytest.mark.asyncio
    async def test_get_adapter_for_bwt(self, sync_service: DataSyncService) -> None:
        """Test getting correct adapter for BWT."""
        adapter = sync_service._get_data_adapter(
            provider="bing_webmaster_tools",
            access_token="test-token",
        )
        assert isinstance(adapter, BWTDataAdapter)

    @pytest.mark.asyncio
    async def test_get_adapter_unknown_provider(self, sync_service: DataSyncService) -> None:
        """Test getting adapter for unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            sync_service._get_data_adapter(
                provider="unknown",
                access_token="test-token",
            )


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Test rate limiting behavior across adapters."""

    @pytest.fixture
    def gsc_adapter(self, access_token: str) -> GSCDataAdapter:
        """Create GSC adapter with rate limiting."""
        return GSCDataAdapter(
            access_token=access_token,
            requests_per_minute=10,
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_backoff(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test exponential backoff on rate limit errors."""
        call_count = 0

        def handle_request(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(429, json={"error": {"message": "Rate limited"}})
            return httpx.Response(200, json={"rows": []})

        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(side_effect=handle_request)

        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
        )

        assert call_count == 3
        assert len(response.rows) == 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling across adapters."""

    @pytest.fixture
    def gsc_adapter(self, access_token: str) -> GSCDataAdapter:
        """Create GSC adapter."""
        return GSCDataAdapter(access_token=access_token)

    @respx.mock
    @pytest.mark.asyncio
    async def test_handles_malformed_response(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test handling of malformed API responses."""
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(return_value=httpx.Response(200, json={"invalid": "structure"}))

        response = await gsc_adapter.fetch_data(
            property_id=gsc_property_id,
            date_range=date_range,
        )

        # Should return empty response for invalid structure
        assert len(response.rows) == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_handles_timeout(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test handling of request timeouts."""
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(side_effect=httpx.TimeoutException("Connection timed out"))

        with pytest.raises(httpx.TimeoutException):
            await gsc_adapter.fetch_data(
                property_id=gsc_property_id,
                date_range=date_range,
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_handles_network_error(
        self,
        gsc_adapter: GSCDataAdapter,
        gsc_property_id: str,
        date_range: DateRange,
    ) -> None:
        """Test handling of network errors."""
        respx.post(
            "https://www.googleapis.com/webmasters/v3/sites/https%3A%2F%2Fexample.com%2F/searchAnalytics/query"
        ).mock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(httpx.ConnectError):
            await gsc_adapter.fetch_data(
                property_id=gsc_property_id,
                date_range=date_range,
            )
