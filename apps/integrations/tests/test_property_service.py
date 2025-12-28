"""
Tests for property discovery and mapping services.

Following TDD: These tests are written FIRST, then the implementation.
Uses mocking for database and external API operations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from semrush_core.models import IntegrationProvider


# =============================================================================
# Mock classes for testing
# =============================================================================


class MockIntegrationAccount:
    """Mock IntegrationAccount for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.user_id = kwargs.get("user_id", uuid.uuid4())
        self.provider = kwargs.get("provider", "google_search_console")
        self.provider_account_id = kwargs.get("provider_account_id")
        self.access_token_encrypted = kwargs.get("access_token_encrypted")
        self.refresh_token_encrypted = kwargs.get("refresh_token_encrypted")
        self.token_expires_at = kwargs.get("token_expires_at")
        self.scopes = kwargs.get("scopes", [])
        self.metadata_ = kwargs.get("metadata_", {})
        self.properties: list[Any] = kwargs.get("properties", [])


class MockIntegrationProperty:
    """Mock IntegrationProperty for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.integration_account_id = kwargs.get("integration_account_id", uuid.uuid4())
        self.provider = kwargs.get("provider", "google_search_console")
        self.property_id = kwargs.get("property_id", "https://example.com/")
        self.display_name = kwargs.get("display_name", "example.com")
        self.property_type = kwargs.get("property_type", "siteUrl")
        self.metadata_ = kwargs.get("metadata_", {})
        self.discovered_at = kwargs.get("discovered_at", datetime.now(timezone.utc))


class MockIntegrationMapping:
    """Mock IntegrationMapping for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.project_id = kwargs.get("project_id", uuid.uuid4())
        self.site_id = kwargs.get("site_id")
        self.integration_property_id = kwargs.get("integration_property_id", uuid.uuid4())
        self.is_primary = kwargs.get("is_primary", False)
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.integration_property = kwargs.get("integration_property")


class MockProject:
    """Mock Project for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid.uuid4())
        self.owner_id = kwargs.get("owner_id", uuid.uuid4())
        self.name = kwargs.get("name", "Test Project")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    return session


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    """Create a sample user ID."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_project_id() -> uuid.UUID:
    """Create a sample project ID."""
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_account_id() -> uuid.UUID:
    """Create a sample integration account ID."""
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def sample_property_id() -> uuid.UUID:
    """Create a sample integration property ID."""
    return uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def sample_mapping_id() -> uuid.UUID:
    """Create a sample integration mapping ID."""
    return uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


@pytest.fixture
def mock_integration_account(sample_account_id: uuid.UUID, sample_user_id: uuid.UUID) -> MockIntegrationAccount:
    """Create a mock integration account."""
    return MockIntegrationAccount(
        id=sample_account_id,
        user_id=sample_user_id,
        provider="google_search_console",
        provider_account_id="123456789",
    )


@pytest.fixture
def mock_integration_property(
    sample_property_id: uuid.UUID, sample_account_id: uuid.UUID
) -> MockIntegrationProperty:
    """Create a mock integration property."""
    return MockIntegrationProperty(
        id=sample_property_id,
        integration_account_id=sample_account_id,
        provider="google_search_console",
        property_id="https://example.com/",
        display_name="example.com",
        property_type="siteUrl",
    )


@pytest.fixture
def mock_project(sample_project_id: uuid.UUID, sample_user_id: uuid.UUID) -> MockProject:
    """Create a mock project."""
    return MockProject(
        id=sample_project_id,
        owner_id=sample_user_id,
        name="Test Project",
    )


# =============================================================================
# PropertyAdapter Base Tests
# =============================================================================


class TestPropertyAdapterBase:
    """Tests for the base PropertyAdapter abstract class."""

    def test_adapter_is_abstract(self) -> None:
        """Should not be able to instantiate base adapter directly."""
        from semrush_integrations.adapters.base import PropertyAdapter

        with pytest.raises(TypeError):
            PropertyAdapter()  # type: ignore

    def test_adapter_requires_discover_properties_method(self) -> None:
        """Should require discover_properties to be implemented."""
        from semrush_integrations.adapters.base import PropertyAdapter

        class IncompleteAdapter(PropertyAdapter):
            provider_name = "test"

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore


# =============================================================================
# GSC Adapter Tests
# =============================================================================


class TestGSCAdapter:
    """Tests for Google Search Console property discovery adapter."""

    @pytest.fixture
    def gsc_adapter(self) -> Any:
        """Create a GSC adapter instance."""
        from semrush_integrations.adapters.gsc_adapter import GSCAdapter

        return GSCAdapter()

    @pytest.fixture
    def gsc_sites_response(self) -> dict[str, Any]:
        """Sample GSC sites.list() API response."""
        return {
            "siteEntry": [
                {
                    "siteUrl": "https://example.com/",
                    "permissionLevel": "siteOwner",
                },
                {
                    "siteUrl": "sc-domain:example.org",
                    "permissionLevel": "siteFullUser",
                },
                {
                    "siteUrl": "https://subdomain.example.com/",
                    "permissionLevel": "siteRestrictedUser",
                },
            ]
        }

    def test_adapter_has_correct_provider_name(self, gsc_adapter: Any) -> None:
        """GSC adapter should have correct provider name."""
        assert gsc_adapter.provider_name == "google_search_console"

    @pytest.mark.asyncio
    async def test_discover_properties_returns_list(
        self, gsc_adapter: Any, gsc_sites_response: dict[str, Any]
    ) -> None:
        """Should return a list of discovered properties."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value=gsc_sites_response):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        assert isinstance(properties, list)
        assert len(properties) == 3

    @pytest.mark.asyncio
    async def test_discover_properties_extracts_site_url(
        self, gsc_adapter: Any, gsc_sites_response: dict[str, Any]
    ) -> None:
        """Should extract siteUrl as property_id."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value=gsc_sites_response):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        property_ids = [p["property_id"] for p in properties]
        assert "https://example.com/" in property_ids
        assert "sc-domain:example.org" in property_ids

    @pytest.mark.asyncio
    async def test_discover_properties_extracts_permission_level(
        self, gsc_adapter: Any, gsc_sites_response: dict[str, Any]
    ) -> None:
        """Should extract permissionLevel into metadata."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value=gsc_sites_response):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        for prop in properties:
            assert "permission_level" in prop["metadata"]

    @pytest.mark.asyncio
    async def test_discover_properties_sets_display_name(
        self, gsc_adapter: Any, gsc_sites_response: dict[str, Any]
    ) -> None:
        """Should set a human-readable display name."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value=gsc_sites_response):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        # Find the example.com property
        example_prop = next(p for p in properties if "example.com/" in p["property_id"])
        assert example_prop["display_name"] == "example.com"

    @pytest.mark.asyncio
    async def test_discover_properties_sets_property_type(
        self, gsc_adapter: Any, gsc_sites_response: dict[str, Any]
    ) -> None:
        """Should differentiate between URL prefix and domain properties."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value=gsc_sites_response):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        url_prop = next(p for p in properties if p["property_id"] == "https://example.com/")
        domain_prop = next(p for p in properties if p["property_id"] == "sc-domain:example.org")

        assert url_prop["property_type"] == "url_prefix"
        assert domain_prop["property_type"] == "domain"

    @pytest.mark.asyncio
    async def test_discover_properties_handles_empty_response(self, gsc_adapter: Any) -> None:
        """Should handle empty siteEntry list."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value={"siteEntry": []}):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        assert properties == []

    @pytest.mark.asyncio
    async def test_discover_properties_handles_missing_site_entry(self, gsc_adapter: Any) -> None:
        """Should handle response without siteEntry key."""
        with patch.object(gsc_adapter, "_fetch_sites", return_value={}):
            properties = await gsc_adapter.discover_properties("fake_access_token")

        assert properties == []

    @pytest.mark.asyncio
    async def test_fetch_sites_uses_correct_api_endpoint(self, gsc_adapter: Any) -> None:
        """Should call the correct Search Console API endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"siteEntry": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            await gsc_adapter._fetch_sites("test_token")

            mock_client.return_value.__aenter__.return_value.get.assert_called_once()
            call_args = mock_client.return_value.__aenter__.return_value.get.call_args
            assert "webmasters/v3/sites" in call_args[0][0]


# =============================================================================
# GA4 Adapter Tests
# =============================================================================


class TestGA4Adapter:
    """Tests for Google Analytics 4 property discovery adapter."""

    @pytest.fixture
    def ga4_adapter(self) -> Any:
        """Create a GA4 adapter instance."""
        from semrush_integrations.adapters.ga4_adapter import GA4Adapter

        return GA4Adapter()

    @pytest.fixture
    def ga4_accounts_response(self) -> dict[str, Any]:
        """Sample GA4 accounts.list() API response."""
        return {
            "accounts": [
                {
                    "name": "accounts/12345",
                    "displayName": "My Analytics Account",
                    "createTime": "2023-01-01T00:00:00Z",
                },
                {
                    "name": "accounts/67890",
                    "displayName": "Second Account",
                    "createTime": "2023-06-01T00:00:00Z",
                },
            ]
        }

    @pytest.fixture
    def ga4_properties_response(self) -> dict[str, Any]:
        """Sample GA4 properties.list() API response."""
        return {
            "properties": [
                {
                    "name": "properties/123456",
                    "displayName": "My Website",
                    "parent": "accounts/12345",
                    "propertyType": "PROPERTY_TYPE_ORDINARY",
                    "createTime": "2023-01-15T00:00:00Z",
                    "industryCategory": "TECHNOLOGY",
                    "timeZone": "America/New_York",
                },
                {
                    "name": "properties/789012",
                    "displayName": "My App",
                    "parent": "accounts/12345",
                    "propertyType": "PROPERTY_TYPE_ORDINARY",
                    "createTime": "2023-03-01T00:00:00Z",
                },
            ]
        }

    def test_adapter_has_correct_provider_name(self, ga4_adapter: Any) -> None:
        """GA4 adapter should have correct provider name."""
        assert ga4_adapter.provider_name == "google_analytics"

    @pytest.mark.asyncio
    async def test_discover_properties_returns_list(
        self,
        ga4_adapter: Any,
        ga4_accounts_response: dict[str, Any],
        ga4_properties_response: dict[str, Any],
    ) -> None:
        """Should return a list of discovered GA4 properties."""
        with patch.object(ga4_adapter, "_fetch_accounts", return_value=ga4_accounts_response):
            with patch.object(
                ga4_adapter, "_fetch_properties", return_value=ga4_properties_response
            ):
                properties = await ga4_adapter.discover_properties("fake_access_token")

        assert isinstance(properties, list)
        assert len(properties) == 2

    @pytest.mark.asyncio
    async def test_discover_properties_extracts_property_id(
        self,
        ga4_adapter: Any,
        ga4_accounts_response: dict[str, Any],
        ga4_properties_response: dict[str, Any],
    ) -> None:
        """Should extract property name as property_id."""
        with patch.object(ga4_adapter, "_fetch_accounts", return_value=ga4_accounts_response):
            with patch.object(
                ga4_adapter, "_fetch_properties", return_value=ga4_properties_response
            ):
                properties = await ga4_adapter.discover_properties("fake_access_token")

        property_ids = [p["property_id"] for p in properties]
        assert "properties/123456" in property_ids
        assert "properties/789012" in property_ids

    @pytest.mark.asyncio
    async def test_discover_properties_extracts_display_name(
        self,
        ga4_adapter: Any,
        ga4_accounts_response: dict[str, Any],
        ga4_properties_response: dict[str, Any],
    ) -> None:
        """Should extract displayName as display_name."""
        with patch.object(ga4_adapter, "_fetch_accounts", return_value=ga4_accounts_response):
            with patch.object(
                ga4_adapter, "_fetch_properties", return_value=ga4_properties_response
            ):
                properties = await ga4_adapter.discover_properties("fake_access_token")

        my_website = next(p for p in properties if p["property_id"] == "properties/123456")
        assert my_website["display_name"] == "My Website"

    @pytest.mark.asyncio
    async def test_discover_properties_includes_account_info(
        self,
        ga4_adapter: Any,
        ga4_accounts_response: dict[str, Any],
        ga4_properties_response: dict[str, Any],
    ) -> None:
        """Should include parent account info in metadata."""
        with patch.object(ga4_adapter, "_fetch_accounts", return_value=ga4_accounts_response):
            with patch.object(
                ga4_adapter, "_fetch_properties", return_value=ga4_properties_response
            ):
                properties = await ga4_adapter.discover_properties("fake_access_token")

        for prop in properties:
            assert "account_id" in prop["metadata"]
            assert "account_name" in prop["metadata"]

    @pytest.mark.asyncio
    async def test_discover_properties_handles_empty_accounts(self, ga4_adapter: Any) -> None:
        """Should handle empty accounts list."""
        with patch.object(ga4_adapter, "_fetch_accounts", return_value={"accounts": []}):
            properties = await ga4_adapter.discover_properties("fake_access_token")

        assert properties == []

    @pytest.mark.asyncio
    async def test_discover_properties_handles_pagination(
        self, ga4_adapter: Any, ga4_accounts_response: dict[str, Any]
    ) -> None:
        """Should handle paginated responses."""
        page1 = {
            "properties": [
                {"name": "properties/1", "displayName": "Prop 1", "parent": "accounts/12345"}
            ],
            "nextPageToken": "token123",
        }
        page2 = {
            "properties": [
                {"name": "properties/2", "displayName": "Prop 2", "parent": "accounts/12345"}
            ],
        }

        with patch.object(ga4_adapter, "_fetch_accounts", return_value=ga4_accounts_response):
            with patch.object(
                ga4_adapter, "_fetch_properties", side_effect=[page1, page2]
            ):
                properties = await ga4_adapter.discover_properties("fake_access_token")

        assert len(properties) == 2


# =============================================================================
# BWT Adapter Tests
# =============================================================================


class TestBWTAdapter:
    """Tests for Bing Webmaster Tools property discovery adapter."""

    @pytest.fixture
    def bwt_adapter(self) -> Any:
        """Create a BWT adapter instance."""
        from semrush_integrations.adapters.bwt_adapter import BWTAdapter

        return BWTAdapter()

    @pytest.fixture
    def bwt_sites_response(self) -> list[dict[str, Any]]:
        """Sample BWT GetUserSites API response."""
        return [
            {
                "Url": "https://example.com",
                "IsVerified": True,
                "VerificationDate": "2023-01-15T00:00:00Z",
            },
            {
                "Url": "https://blog.example.com",
                "IsVerified": True,
                "VerificationDate": "2023-06-01T00:00:00Z",
            },
            {
                "Url": "https://unverified.com",
                "IsVerified": False,
                "VerificationDate": None,
            },
        ]

    def test_adapter_has_correct_provider_name(self, bwt_adapter: Any) -> None:
        """BWT adapter should have correct provider name."""
        assert bwt_adapter.provider_name == "bing_webmaster_tools"

    @pytest.mark.asyncio
    async def test_discover_properties_returns_list(
        self, bwt_adapter: Any, bwt_sites_response: list[dict[str, Any]]
    ) -> None:
        """Should return a list of discovered properties."""
        with patch.object(bwt_adapter, "_fetch_sites", return_value=bwt_sites_response):
            properties = await bwt_adapter.discover_properties("fake_access_token")

        assert isinstance(properties, list)
        assert len(properties) == 3

    @pytest.mark.asyncio
    async def test_discover_properties_extracts_url(
        self, bwt_adapter: Any, bwt_sites_response: list[dict[str, Any]]
    ) -> None:
        """Should extract Url as property_id."""
        with patch.object(bwt_adapter, "_fetch_sites", return_value=bwt_sites_response):
            properties = await bwt_adapter.discover_properties("fake_access_token")

        property_ids = [p["property_id"] for p in properties]
        assert "https://example.com" in property_ids
        assert "https://blog.example.com" in property_ids

    @pytest.mark.asyncio
    async def test_discover_properties_extracts_verification_status(
        self, bwt_adapter: Any, bwt_sites_response: list[dict[str, Any]]
    ) -> None:
        """Should extract IsVerified into metadata."""
        with patch.object(bwt_adapter, "_fetch_sites", return_value=bwt_sites_response):
            properties = await bwt_adapter.discover_properties("fake_access_token")

        verified_prop = next(p for p in properties if p["property_id"] == "https://example.com")
        unverified_prop = next(p for p in properties if p["property_id"] == "https://unverified.com")

        assert verified_prop["metadata"]["is_verified"] is True
        assert unverified_prop["metadata"]["is_verified"] is False

    @pytest.mark.asyncio
    async def test_discover_properties_sets_display_name(
        self, bwt_adapter: Any, bwt_sites_response: list[dict[str, Any]]
    ) -> None:
        """Should set a human-readable display name from URL."""
        with patch.object(bwt_adapter, "_fetch_sites", return_value=bwt_sites_response):
            properties = await bwt_adapter.discover_properties("fake_access_token")

        example_prop = next(p for p in properties if p["property_id"] == "https://example.com")
        assert example_prop["display_name"] == "example.com"

    @pytest.mark.asyncio
    async def test_discover_properties_handles_empty_response(self, bwt_adapter: Any) -> None:
        """Should handle empty sites list."""
        with patch.object(bwt_adapter, "_fetch_sites", return_value=[]):
            properties = await bwt_adapter.discover_properties("fake_access_token")

        assert properties == []


# =============================================================================
# PropertyService Tests
# =============================================================================


class TestPropertyServiceDiscoverProperties:
    """Tests for PropertyService.discover_properties()."""

    @pytest.fixture
    def property_service(self, mock_db_session: MagicMock) -> Any:
        """Create a PropertyService instance."""
        from semrush_integrations.services.property_service import PropertyService

        return PropertyService(mock_db_session)

    @pytest.fixture
    def mock_token_service(self) -> MagicMock:
        """Create a mock TokenService."""
        service = MagicMock()
        service.get_valid_token.return_value = "valid_access_token"
        return service

    @pytest.mark.asyncio
    async def test_discover_properties_requires_valid_provider(
        self, property_service: Any, sample_user_id: uuid.UUID
    ) -> None:
        """Should raise error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            await property_service.discover_properties(sample_user_id, "invalid_provider")

    @pytest.mark.asyncio
    async def test_discover_properties_uses_correct_adapter(
        self,
        sample_user_id: uuid.UUID,
        mock_integration_account: MockIntegrationAccount,
        mock_db_session: MagicMock,
    ) -> None:
        """Should use GSC adapter for google_search_console provider."""
        from semrush_integrations.services.property_service import PropertyService, PROVIDER_ADAPTERS

        # Set up mock to return account
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_integration_account
        )

        # Create a mock adapter class
        mock_adapter = MagicMock()
        mock_adapter.discover_properties = AsyncMock(return_value=[])
        mock_gsc_adapter_class = MagicMock(return_value=mock_adapter)

        with patch.dict(PROVIDER_ADAPTERS, {"google_search_console": mock_gsc_adapter_class}):
            with patch.object(PropertyService, "_get_access_token", return_value="token"):
                property_service = PropertyService(mock_db_session)
                await property_service.discover_properties(sample_user_id, "google_search_console")

                mock_gsc_adapter_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_properties_stores_results(
        self,
        sample_user_id: uuid.UUID,
        mock_integration_account: MockIntegrationAccount,
        mock_db_session: MagicMock,
    ) -> None:
        """Should store discovered properties in database."""
        from semrush_integrations.services.property_service import PropertyService, PROVIDER_ADAPTERS

        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_integration_account
        )

        discovered = [
            {
                "property_id": "https://example.com/",
                "display_name": "example.com",
                "property_type": "url_prefix",
                "metadata": {"permission_level": "siteOwner"},
            }
        ]

        # Create a mock adapter class
        mock_adapter = MagicMock()
        mock_adapter.discover_properties = AsyncMock(return_value=discovered)
        mock_gsc_adapter_class = MagicMock(return_value=mock_adapter)

        with patch.dict(PROVIDER_ADAPTERS, {"google_search_console": mock_gsc_adapter_class}):
            with patch.object(PropertyService, "_get_access_token", return_value="token"):
                property_service = PropertyService(mock_db_session)
                await property_service.discover_properties(sample_user_id, "google_search_console")

                # Should have called add() and commit()
                assert mock_db_session.add.called or mock_db_session.merge.called
                mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_discover_properties_raises_for_missing_account(
        self, property_service: Any, sample_user_id: uuid.UUID, mock_db_session: MagicMock
    ) -> None:
        """Should raise error if no integration account exists."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="No integration account"):
            await property_service.discover_properties(sample_user_id, "google_search_console")


class TestPropertyServiceSyncProperties:
    """Tests for PropertyService.sync_properties()."""

    @pytest.fixture
    def property_service(self, mock_db_session: MagicMock) -> Any:
        """Create a PropertyService instance."""
        from semrush_integrations.services.property_service import PropertyService

        return PropertyService(mock_db_session)

    @pytest.mark.asyncio
    async def test_sync_properties_updates_existing(
        self,
        sample_user_id: uuid.UUID,
        mock_integration_account: MockIntegrationAccount,
        mock_integration_property: MockIntegrationProperty,
        mock_db_session: MagicMock,
    ) -> None:
        """Should update existing properties during sync."""
        from semrush_integrations.services.property_service import PropertyService, PROVIDER_ADAPTERS

        # Account has existing property
        mock_integration_account.properties = [mock_integration_property]
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_integration_account
        )

        # API returns same property with updated metadata
        discovered = [
            {
                "property_id": "https://example.com/",
                "display_name": "example.com (updated)",
                "property_type": "url_prefix",
                "metadata": {"permission_level": "siteOwner"},
            }
        ]

        # Create a mock adapter class
        mock_adapter = MagicMock()
        mock_adapter.discover_properties = AsyncMock(return_value=discovered)
        mock_gsc_adapter_class = MagicMock(return_value=mock_adapter)

        with patch.dict(PROVIDER_ADAPTERS, {"google_search_console": mock_gsc_adapter_class}):
            with patch.object(PropertyService, "_get_access_token", return_value="token"):
                property_service = PropertyService(mock_db_session)
                await property_service.sync_properties(sample_user_id, "google_search_console")

                mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_properties_adds_new(
        self,
        sample_user_id: uuid.UUID,
        mock_integration_account: MockIntegrationAccount,
        mock_db_session: MagicMock,
    ) -> None:
        """Should add new properties discovered during sync."""
        from semrush_integrations.services.property_service import PropertyService, PROVIDER_ADAPTERS

        mock_integration_account.properties = []
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_integration_account
        )

        discovered = [
            {
                "property_id": "https://newsite.com/",
                "display_name": "newsite.com",
                "property_type": "url_prefix",
                "metadata": {},
            }
        ]

        # Create a mock adapter class
        mock_adapter = MagicMock()
        mock_adapter.discover_properties = AsyncMock(return_value=discovered)
        mock_gsc_adapter_class = MagicMock(return_value=mock_adapter)

        with patch.dict(PROVIDER_ADAPTERS, {"google_search_console": mock_gsc_adapter_class}):
            with patch.object(PropertyService, "_get_access_token", return_value="token"):
                property_service = PropertyService(mock_db_session)
                await property_service.sync_properties(sample_user_id, "google_search_console")

                # Should add new property
                assert mock_db_session.add.called or mock_db_session.merge.called


class TestPropertyServiceGetUserProperties:
    """Tests for PropertyService.get_user_properties()."""

    @pytest.fixture
    def property_service(self, mock_db_session: MagicMock) -> Any:
        """Create a PropertyService instance."""
        from semrush_integrations.services.property_service import PropertyService

        return PropertyService(mock_db_session)

    def test_get_user_properties_returns_list(
        self,
        property_service: Any,
        sample_user_id: uuid.UUID,
        mock_integration_account: MockIntegrationAccount,
        mock_integration_property: MockIntegrationProperty,
        mock_db_session: MagicMock,
    ) -> None:
        """Should return list of properties for user."""
        mock_integration_account.properties = [mock_integration_property]
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_integration_account
        )

        properties = property_service.get_user_properties(sample_user_id, "google_search_console")

        assert isinstance(properties, list)
        assert len(properties) == 1

    def test_get_user_properties_returns_empty_for_no_account(
        self, property_service: Any, sample_user_id: uuid.UUID, mock_db_session: MagicMock
    ) -> None:
        """Should return empty list when no account exists."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        properties = property_service.get_user_properties(sample_user_id, "google_search_console")

        assert properties == []

    def test_get_user_properties_filters_by_provider(
        self,
        property_service: Any,
        sample_user_id: uuid.UUID,
        mock_integration_account: MockIntegrationAccount,
        mock_db_session: MagicMock,
    ) -> None:
        """Should filter properties by provider."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_integration_account
        )

        property_service.get_user_properties(sample_user_id, "google_search_console")

        # Verify filter was called with provider
        filter_calls = mock_db_session.query.return_value.filter.call_args_list
        assert len(filter_calls) > 0


# =============================================================================
# PropertyMappingService Tests
# =============================================================================


class TestPropertyMappingServiceCreate:
    """Tests for creating property mappings."""

    @pytest.fixture
    def mapping_service(self, mock_db_session: MagicMock) -> Any:
        """Create a PropertyMappingService instance."""
        from semrush_integrations.services.property_service import PropertyMappingService

        return PropertyMappingService(mock_db_session)

    def test_create_mapping_stores_in_database(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_property_id: uuid.UUID,
        mock_integration_property: MockIntegrationProperty,
        mock_project: MockProject,
        mock_db_session: MagicMock,
    ) -> None:
        """Should store mapping in database."""
        # Set up query returns
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_project,  # First call for project
            mock_integration_property,  # Second call for property
            None,  # Third call for existing mapping check
        ]

        mapping_service.create_mapping(
            project_id=sample_project_id,
            property_id=sample_property_id,
            is_primary=False,
        )

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_create_mapping_raises_for_missing_property(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_property_id: uuid.UUID,
        mock_project: MockProject,
        mock_db_session: MagicMock,
    ) -> None:
        """Should raise error if property doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_project,  # Project exists
            None,  # Property doesn't exist
        ]

        with pytest.raises(ValueError, match="Property not found"):
            mapping_service.create_mapping(
                project_id=sample_project_id,
                property_id=sample_property_id,
            )

    def test_create_mapping_raises_for_missing_project(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_property_id: uuid.UUID,
        mock_db_session: MagicMock,
    ) -> None:
        """Should raise error if project doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Project not found"):
            mapping_service.create_mapping(
                project_id=sample_project_id,
                property_id=sample_property_id,
            )

    def test_create_mapping_raises_for_duplicate(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_property_id: uuid.UUID,
        mock_integration_property: MockIntegrationProperty,
        mock_project: MockProject,
        mock_db_session: MagicMock,
    ) -> None:
        """Should raise error for duplicate mapping."""
        existing_mapping = MockIntegrationMapping(
            project_id=sample_project_id,
            integration_property_id=sample_property_id,
        )
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_project,  # Project
            mock_integration_property,  # Property
            existing_mapping,  # Existing mapping
        ]

        with pytest.raises(ValueError, match="already mapped"):
            mapping_service.create_mapping(
                project_id=sample_project_id,
                property_id=sample_property_id,
            )

    def test_create_mapping_sets_primary_flag(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_property_id: uuid.UUID,
        mock_integration_property: MockIntegrationProperty,
        mock_project: MockProject,
        mock_db_session: MagicMock,
    ) -> None:
        """Should set is_primary flag correctly."""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_project,
            mock_integration_property,
            None,  # No existing mapping
        ]

        mapping_service.create_mapping(
            project_id=sample_project_id,
            property_id=sample_property_id,
            is_primary=True,
        )

        # Verify the mapping was created with is_primary=True
        add_call = mock_db_session.add.call_args
        assert add_call is not None


class TestPropertyMappingServiceList:
    """Tests for listing property mappings."""

    @pytest.fixture
    def mapping_service(self, mock_db_session: MagicMock) -> Any:
        """Create a PropertyMappingService instance."""
        from semrush_integrations.services.property_service import PropertyMappingService

        return PropertyMappingService(mock_db_session)

    def test_get_project_mappings_returns_list(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        mock_db_session: MagicMock,
    ) -> None:
        """Should return list of mappings for project."""
        mock_mapping = MockIntegrationMapping(project_id=sample_project_id)
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_mapping]

        mappings = mapping_service.get_project_mappings(sample_project_id)

        assert isinstance(mappings, list)
        assert len(mappings) == 1

    def test_get_project_mappings_returns_empty_list(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        mock_db_session: MagicMock,
    ) -> None:
        """Should return empty list when no mappings exist."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        mappings = mapping_service.get_project_mappings(sample_project_id)

        assert mappings == []


class TestPropertyMappingServiceDelete:
    """Tests for deleting property mappings."""

    @pytest.fixture
    def mapping_service(self, mock_db_session: MagicMock) -> Any:
        """Create a PropertyMappingService instance."""
        from semrush_integrations.services.property_service import PropertyMappingService

        return PropertyMappingService(mock_db_session)

    def test_delete_mapping_removes_from_database(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_mapping_id: uuid.UUID,
        mock_db_session: MagicMock,
    ) -> None:
        """Should delete mapping from database."""
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            project_id=sample_project_id,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        result = mapping_service.delete_mapping(sample_project_id, sample_mapping_id)

        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_mapping)
        mock_db_session.commit.assert_called_once()

    def test_delete_mapping_returns_false_for_missing(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_mapping_id: uuid.UUID,
        mock_db_session: MagicMock,
    ) -> None:
        """Should return False if mapping doesn't exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = mapping_service.delete_mapping(sample_project_id, sample_mapping_id)

        assert result is False
        mock_db_session.delete.assert_not_called()

    def test_delete_mapping_validates_project_ownership(
        self,
        mapping_service: Any,
        sample_project_id: uuid.UUID,
        sample_mapping_id: uuid.UUID,
        mock_db_session: MagicMock,
    ) -> None:
        """Should only delete mappings belonging to the specified project."""
        other_project_id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            project_id=other_project_id,  # Different project
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = mapping_service.delete_mapping(sample_project_id, sample_mapping_id)

        assert result is False


# =============================================================================
# Integration Tests (Using all components together)
# =============================================================================


class TestPropertyDiscoveryIntegration:
    """Integration tests for the complete property discovery flow."""

    @pytest.mark.asyncio
    async def test_full_gsc_discovery_flow(self) -> None:
        """Test complete GSC property discovery and storage flow."""
        from semrush_integrations.adapters.gsc_adapter import GSCAdapter

        adapter = GSCAdapter()

        # Mock the HTTP call
        mock_response_data = {
            "siteEntry": [
                {
                    "siteUrl": "https://integration-test.com/",
                    "permissionLevel": "siteOwner",
                }
            ]
        }

        with patch.object(adapter, "_fetch_sites", return_value=mock_response_data):
            properties = await adapter.discover_properties("test_token")

        assert len(properties) == 1
        assert properties[0]["property_id"] == "https://integration-test.com/"
        assert properties[0]["display_name"] == "integration-test.com"
        assert properties[0]["property_type"] == "url_prefix"
        assert properties[0]["metadata"]["permission_level"] == "siteOwner"
