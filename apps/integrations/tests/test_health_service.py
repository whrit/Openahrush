"""
Tests for Integration Health Service.

Following TDD: These tests are written FIRST, then the implementation.
Uses mocking for database operations to avoid PostgreSQL-specific types.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from semrush_integrations.services.health_service import (
    PROVIDER_DATA_LAG_DAYS,
    DataFreshness,
    IntegrationHealth,
    IntegrationHealthService,
    SyncStatus,
)


# Mock classes to simulate database models
class MockSyncRun:
    """Mock SyncRun for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.integration_mapping_id = kwargs.get("integration_mapping_id")
        self.provider = kwargs.get("provider", "google_search_console")
        self.property_id = kwargs.get("property_id", "sc-domain:example.com")
        self.mode = kwargs.get("mode", "incremental")
        self.status = kwargs.get("status", "completed")
        self.date_range_start = kwargs.get("date_range_start")
        self.date_range_end = kwargs.get("date_range_end")
        self.records_written = kwargs.get("records_written", 100)
        self.error_message = kwargs.get("error_message")
        self.started_at = kwargs.get("started_at")
        self.completed_at = kwargs.get("completed_at")
        self.created_at = kwargs.get("created_at", datetime.now(UTC))


class MockIntegrationMapping:
    """Mock IntegrationMapping for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.project_id = kwargs.get("project_id", uuid.uuid4())
        self.site_id = kwargs.get("site_id")
        self.integration_property_id = kwargs.get("integration_property_id", uuid.uuid4())
        self.is_primary = kwargs.get("is_primary", True)
        self.created_at = kwargs.get("created_at", datetime.now(UTC))
        self.sync_runs = kwargs.get("sync_runs", [])
        self.integration_property = kwargs.get("integration_property")


class MockIntegrationProperty:
    """Mock IntegrationProperty for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.integration_account_id = kwargs.get("integration_account_id", uuid.uuid4())
        self.provider = kwargs.get("provider", "google_search_console")
        self.property_id = kwargs.get("property_id", "sc-domain:example.com")
        self.display_name = kwargs.get("display_name", "example.com")
        self.account = kwargs.get("account")


class MockIntegrationAccount:
    """Mock IntegrationAccount for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.user_id = kwargs.get("user_id", uuid.uuid4())
        self.provider = kwargs.get("provider", "google_search_console")
        self.provider_account_id = kwargs.get("provider_account_id")
        self.token_expires_at = kwargs.get("token_expires_at")
        self.token = kwargs.get("token")
        self.properties = kwargs.get("properties", [])


class MockIntegrationToken:
    """Mock IntegrationToken for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.integration_account_id = kwargs.get("integration_account_id")
        self.expires_at = kwargs.get("expires_at")
        self.access_token_encrypted = kwargs.get("access_token_encrypted", b"encrypted")
        self.refresh_token_encrypted = kwargs.get("refresh_token_encrypted", b"refresh_encrypted")


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.join.return_value.filter.return_value.first.return_value = None
    session.query.return_value.join.return_value.filter.return_value.all.return_value = []
    return session


@pytest.fixture
def sample_mapping_id():
    """Create a sample mapping ID."""
    return uuid.uuid4()


@pytest.fixture
def sample_user_id():
    """Create a sample user ID."""
    return uuid.uuid4()


@pytest.fixture
def sample_project_id():
    """Create a sample project ID."""
    return uuid.uuid4()


class TestGetSyncStatus:
    """Tests for get_sync_status method."""

    def test_returns_sync_status_for_valid_mapping(self, mock_db_session, sample_mapping_id):
        """Should return SyncStatus for a valid mapping with completed sync."""
        now = datetime.now(UTC)
        last_sync = now - timedelta(hours=1)

        mock_sync_run = MockSyncRun(
            integration_mapping_id=sample_mapping_id,
            status="completed",
            completed_at=last_sync,
            error_message=None,
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert isinstance(result, SyncStatus)
        assert result.last_sync_at == last_sync
        assert result.status == "completed"
        assert result.error_message is None

    def test_returns_none_for_missing_mapping(self, mock_db_session, sample_mapping_id):
        """Should return None when mapping does not exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result is None

    def test_returns_never_synced_status_when_no_runs(self, mock_db_session, sample_mapping_id):
        """Should return status='never' when no sync runs exist."""
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result.status == "never"
        assert result.last_sync_at is None
        assert result.error_count == 0

    def test_calculates_consecutive_error_count(self, mock_db_session, sample_mapping_id):
        """Should count consecutive failures."""
        now = datetime.now(UTC)

        # Create 3 failed syncs followed by 1 success
        runs = [
            MockSyncRun(status="failed", completed_at=now - timedelta(hours=1), error_message="Error 1"),
            MockSyncRun(status="failed", completed_at=now - timedelta(hours=2), error_message="Error 2"),
            MockSyncRun(status="failed", completed_at=now - timedelta(hours=3), error_message="Error 3"),
            MockSyncRun(status="completed", completed_at=now - timedelta(hours=4)),
        ]
        mock_mapping = MockIntegrationMapping(id=sample_mapping_id, sync_runs=runs)
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result.error_count == 3
        assert result.status == "failed"
        assert result.error_message == "Error 1"

    def test_calculates_next_sync_time(self, mock_db_session, sample_mapping_id):
        """Should calculate next sync time based on last sync."""
        now = datetime.now(UTC)
        last_sync = now - timedelta(hours=12)

        mock_sync_run = MockSyncRun(
            status="completed",
            completed_at=last_sync,
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        # Default sync interval is 24 hours
        expected_next = last_sync + timedelta(hours=24)
        assert result.next_sync_at is not None
        # Allow 1 second tolerance for test execution time
        assert abs((result.next_sync_at - expected_next).total_seconds()) < 1

    def test_handles_running_sync(self, mock_db_session, sample_mapping_id):
        """Should report running status when sync is in progress."""
        mock_sync_run = MockSyncRun(
            status="running",
            started_at=datetime.now(UTC) - timedelta(minutes=5),
            completed_at=None,
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result.status == "running"
        assert result.next_sync_at is None  # No next sync when running


class TestGetDataFreshness:
    """Tests for get_data_freshness method."""

    def test_returns_data_freshness_for_gsc_mapping(self, mock_db_session, sample_mapping_id):
        """Should return DataFreshness for GSC with correct lag calculation."""
        today = date.today()
        latest_data_date = today - timedelta(days=3)

        mock_property = MockIntegrationProperty(provider="google_search_console")
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            integration_property=mock_property,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        # Mock the date query - side_effect for multiple calls: first is latest date, second is coverage count
        mock_db_session.query.return_value.filter.return_value.scalar.side_effect = [
            latest_data_date,  # latest data date
            25,  # coverage count
        ]

        service = IntegrationHealthService(mock_db_session)
        result = service.get_data_freshness(sample_mapping_id)

        assert isinstance(result, DataFreshness)
        assert result.latest_data_date == latest_data_date
        # GSC has 3-day expected lag
        assert result.days_behind == 0  # On target for GSC

    def test_returns_data_freshness_for_ga4_mapping(self, mock_db_session, sample_mapping_id):
        """Should return DataFreshness for GA4 with correct lag calculation."""
        today = date.today()
        latest_data_date = today - timedelta(days=1)

        mock_property = MockIntegrationProperty(provider="google_analytics")
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            integration_property=mock_property,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping
        mock_db_session.query.return_value.filter.return_value.scalar.side_effect = [
            latest_data_date,  # latest data date
            25,  # coverage count
        ]

        service = IntegrationHealthService(mock_db_session)
        result = service.get_data_freshness(sample_mapping_id)

        assert result.latest_data_date == latest_data_date
        # GA4 has 1-day expected lag
        assert result.days_behind == 0

    def test_returns_none_for_missing_mapping(self, mock_db_session, sample_mapping_id):
        """Should return None when mapping does not exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        service = IntegrationHealthService(mock_db_session)
        result = service.get_data_freshness(sample_mapping_id)

        assert result is None

    def test_calculates_days_behind_correctly(self, mock_db_session, sample_mapping_id):
        """Should calculate days behind expected based on provider lag."""
        today = date.today()
        # For GSC (3-day lag), if data is 5 days old, we're 2 days behind
        latest_data_date = today - timedelta(days=5)

        mock_property = MockIntegrationProperty(provider="google_search_console")
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            integration_property=mock_property,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping
        mock_db_session.query.return_value.filter.return_value.scalar.side_effect = [
            latest_data_date,  # latest data date
            20,  # coverage count
        ]

        service = IntegrationHealthService(mock_db_session)
        result = service.get_data_freshness(sample_mapping_id)

        assert result.days_behind == 2  # 5 days actual - 3 days expected

    def test_calculates_coverage_percentage(self, mock_db_session, sample_mapping_id):
        """Should calculate coverage as percentage of expected dates with data."""
        mock_property = MockIntegrationProperty(provider="google_search_console")
        mock_mapping = MockIntegrationMapping(id=sample_mapping_id, integration_property=mock_property)
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        # Mock: 25 days of data out of expected 30
        mock_db_session.query.return_value.filter.return_value.scalar.side_effect = [
            date.today() - timedelta(days=3),  # latest date
            25,  # count of distinct dates
        ]

        service = IntegrationHealthService(mock_db_session)
        result = service.get_data_freshness(sample_mapping_id, lookback_days=30)

        assert result.coverage_pct >= 80.0  # 25/30 = ~83%

    def test_handles_no_data(self, mock_db_session, sample_mapping_id):
        """Should handle case with no data at all."""
        mock_property = MockIntegrationProperty(provider="google_search_console")
        mock_mapping = MockIntegrationMapping(id=sample_mapping_id, integration_property=mock_property)
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping
        mock_db_session.query.return_value.filter.return_value.scalar.return_value = None

        service = IntegrationHealthService(mock_db_session)
        result = service.get_data_freshness(sample_mapping_id)

        assert result.latest_data_date is None
        assert result.coverage_pct == 0.0


class TestGetIntegrationHealth:
    """Tests for get_integration_health method."""

    def test_returns_health_for_all_user_integrations(self, mock_db_session, sample_user_id):
        """Should return health status for all user integrations."""
        now = datetime.now(UTC)

        mock_token = MockIntegrationToken(expires_at=now + timedelta(hours=1))
        mock_property = MockIntegrationProperty(provider="google_search_console")
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
            properties=[mock_property],
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_account]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_integration_health(sample_user_id)

        assert len(results) == 1
        assert isinstance(results[0], IntegrationHealth)
        assert results[0].provider == "google_search_console"
        assert results[0].connected is True
        assert results[0].token_valid is True

    def test_returns_empty_list_for_no_integrations(self, mock_db_session, sample_user_id):
        """Should return empty list when user has no integrations."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        service = IntegrationHealthService(mock_db_session)
        results = service.get_integration_health(sample_user_id)

        assert results == []

    def test_reports_expired_token_without_refresh(self, mock_db_session, sample_user_id):
        """Should report token_valid=False when token is expired and no refresh token."""
        now = datetime.now(UTC)

        mock_token = MockIntegrationToken(
            expires_at=now - timedelta(hours=1),
            refresh_token_encrypted=None,  # No refresh token
        )
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
            properties=[],
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_account]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_integration_health(sample_user_id)

        assert results[0].token_valid is False

    def test_reports_missing_token(self, mock_db_session, sample_user_id):
        """Should report token_valid=False when no token exists."""
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=None,
            properties=[],
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_account]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_integration_health(sample_user_id)

        assert results[0].token_valid is False

    def test_counts_properties_correctly(self, mock_db_session, sample_user_id):
        """Should correctly count connected properties."""
        properties = [
            MockIntegrationProperty(property_id="prop1"),
            MockIntegrationProperty(property_id="prop2"),
            MockIntegrationProperty(property_id="prop3"),
        ]
        mock_token = MockIntegrationToken(expires_at=datetime.now(UTC) + timedelta(hours=1))
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
            properties=properties,
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_account]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_integration_health(sample_user_id)

        assert results[0].properties_count == 3

    def test_includes_last_sync_time(self, mock_db_session, sample_user_id):
        """Should include last sync time from most recent sync run."""
        now = datetime.now(UTC)
        last_sync = now - timedelta(hours=2)

        mock_property = MockIntegrationProperty(provider="google_search_console")
        mock_property.mappings = [
            MockIntegrationMapping(
                sync_runs=[MockSyncRun(completed_at=last_sync, status="completed")]
            )
        ]
        mock_token = MockIntegrationToken(expires_at=now + timedelta(hours=1))
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
            properties=[mock_property],
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_account]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_integration_health(sample_user_id)

        assert results[0].last_sync == last_sync


class TestCheckTokenValidity:
    """Tests for check_token_validity method."""

    def test_returns_true_for_valid_token(self, mock_db_session, sample_user_id):
        """Should return True when token is valid and not expired."""
        now = datetime.now(UTC)

        mock_token = MockIntegrationToken(expires_at=now + timedelta(hours=1))
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account

        service = IntegrationHealthService(mock_db_session)
        result = service.check_token_validity(sample_user_id, "google_search_console")

        assert result is True

    def test_returns_false_for_expired_token_without_refresh(self, mock_db_session, sample_user_id):
        """Should return False when token is expired and no refresh token available."""
        now = datetime.now(UTC)

        mock_token = MockIntegrationToken(
            expires_at=now - timedelta(hours=1),
            refresh_token_encrypted=None,  # No refresh token
        )
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account

        service = IntegrationHealthService(mock_db_session)
        result = service.check_token_validity(sample_user_id, "google_search_console")

        assert result is False

    def test_returns_false_for_missing_account(self, mock_db_session, sample_user_id):
        """Should return False when integration account does not exist."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        service = IntegrationHealthService(mock_db_session)
        result = service.check_token_validity(sample_user_id, "google_search_console")

        assert result is False

    def test_returns_false_for_missing_token(self, mock_db_session, sample_user_id):
        """Should return False when token is missing."""
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=None,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account

        service = IntegrationHealthService(mock_db_session)
        result = service.check_token_validity(sample_user_id, "google_search_console")

        assert result is False

    def test_handles_refresh_token_check(self, mock_db_session, sample_user_id):
        """Should check for refresh token availability."""
        now = datetime.now(UTC)

        # Token near expiry but has refresh token
        mock_token = MockIntegrationToken(
            expires_at=now + timedelta(minutes=3),  # Near expiry
            refresh_token_encrypted=b"refresh_token",
        )
        mock_account = MockIntegrationAccount(
            user_id=sample_user_id,
            provider="google_search_console",
            token=mock_token,
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account

        service = IntegrationHealthService(mock_db_session)
        result = service.check_token_validity(sample_user_id, "google_search_console")

        # Should be valid because refresh token is available
        assert result is True


class TestSyncHealthCheck:
    """Tests for sync health determination."""

    def test_sync_healthy_when_recent(self, mock_db_session, sample_mapping_id):
        """Should report healthy when last sync was within 48 hours."""
        now = datetime.now(UTC)

        mock_sync_run = MockSyncRun(
            status="completed",
            completed_at=now - timedelta(hours=24),
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result.is_healthy is True

    def test_sync_unhealthy_when_stale(self, mock_db_session, sample_mapping_id):
        """Should report unhealthy when last sync was more than 48 hours ago."""
        now = datetime.now(UTC)

        mock_sync_run = MockSyncRun(
            status="completed",
            completed_at=now - timedelta(hours=50),
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result.is_healthy is False

    def test_sync_unhealthy_with_consecutive_failures(self, mock_db_session, sample_mapping_id):
        """Should report unhealthy with 2+ consecutive failures."""
        now = datetime.now(UTC)

        runs = [
            MockSyncRun(status="failed", completed_at=now - timedelta(hours=1)),
            MockSyncRun(status="failed", completed_at=now - timedelta(hours=2)),
        ]
        mock_mapping = MockIntegrationMapping(id=sample_mapping_id, sync_runs=runs)
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert result.is_healthy is False
        assert result.error_count >= 2


class TestDataFreshnessProviderLag:
    """Tests for provider-specific data lag expectations."""

    def test_gsc_expected_lag_is_3_days(self):
        """GSC should have 3-day expected data lag."""
        assert PROVIDER_DATA_LAG_DAYS["google_search_console"] == 3

    def test_ga4_expected_lag_is_1_day(self):
        """GA4 should have 1-day expected data lag."""
        assert PROVIDER_DATA_LAG_DAYS["google_analytics"] == 1

    def test_bwt_expected_lag_is_2_days(self):
        """BWT should have 2-day expected data lag."""
        assert PROVIDER_DATA_LAG_DAYS["bing_webmaster_tools"] == 2


class TestActionableStatusMessages:
    """Tests for actionable status message generation."""

    def test_status_message_for_healthy_sync(self, mock_db_session, sample_mapping_id):
        """Should provide reassuring message for healthy sync."""
        now = datetime.now(UTC)

        mock_sync_run = MockSyncRun(
            status="completed",
            completed_at=now - timedelta(hours=1),
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert "healthy" in result.status_message.lower() or "up to date" in result.status_message.lower()

    def test_status_message_for_stale_data(self, mock_db_session, sample_mapping_id):
        """Should provide actionable message for stale data."""
        now = datetime.now(UTC)

        mock_sync_run = MockSyncRun(
            status="completed",
            completed_at=now - timedelta(hours=72),
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert "stale" in result.status_message.lower() or "overdue" in result.status_message.lower()

    def test_status_message_for_failed_sync(self, mock_db_session, sample_mapping_id):
        """Should provide helpful message for failed sync."""
        now = datetime.now(UTC)

        mock_sync_run = MockSyncRun(
            status="failed",
            completed_at=now - timedelta(hours=1),
            error_message="API rate limit exceeded",
        )
        mock_mapping = MockIntegrationMapping(
            id=sample_mapping_id,
            sync_runs=[mock_sync_run],
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_mapping

        service = IntegrationHealthService(mock_db_session)
        result = service.get_sync_status(sample_mapping_id)

        assert "failed" in result.status_message.lower() or "error" in result.status_message.lower()


class TestGetProjectSyncStatus:
    """Tests for getting sync status for all mappings in a project."""

    def test_returns_all_mappings_status(self, mock_db_session, sample_project_id):
        """Should return sync status for all mappings in project."""
        now = datetime.now(UTC)

        mapping_id_1 = uuid.uuid4()
        mapping_id_2 = uuid.uuid4()
        mock_property_1 = MockIntegrationProperty(provider="google_search_console")
        mock_property_2 = MockIntegrationProperty(provider="google_analytics")

        mapping_1 = MockIntegrationMapping(
            id=mapping_id_1,
            project_id=sample_project_id,
            integration_property=mock_property_1,
            sync_runs=[MockSyncRun(status="completed", completed_at=now - timedelta(hours=1))],
        )
        mapping_2 = MockIntegrationMapping(
            id=mapping_id_2,
            project_id=sample_project_id,
            integration_property=mock_property_2,
            sync_runs=[MockSyncRun(status="failed", completed_at=now - timedelta(hours=2), error_message="Test error")],
        )

        # Mock: first call returns list of mappings, subsequent first() calls return each mapping
        mock_db_session.query.return_value.filter.return_value.all.return_value = [mapping_1, mapping_2]
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [mapping_1, mapping_2]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_project_sync_status(sample_project_id)

        assert len(results) == 2
        assert results[0].status == "completed"
        assert results[1].status == "failed"

    def test_returns_empty_for_project_without_mappings(self, mock_db_session, sample_project_id):
        """Should return empty list for project without mappings."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        service = IntegrationHealthService(mock_db_session)
        results = service.get_project_sync_status(sample_project_id)

        assert results == []


class TestGetProjectDataFreshness:
    """Tests for getting data freshness for all mappings in a project."""

    def test_returns_freshness_for_all_mappings(self, mock_db_session, sample_project_id):
        """Should return data freshness for all mappings in project."""
        today = date.today()

        mapping_id_1 = uuid.uuid4()
        mapping_id_2 = uuid.uuid4()
        mock_property_1 = MockIntegrationProperty(provider="google_search_console")
        mock_property_2 = MockIntegrationProperty(provider="google_analytics")

        mapping_1 = MockIntegrationMapping(
            id=mapping_id_1,
            project_id=sample_project_id,
            integration_property=mock_property_1,
        )
        mapping_2 = MockIntegrationMapping(
            id=mapping_id_2,
            project_id=sample_project_id,
            integration_property=mock_property_2,
        )

        mock_db_session.query.return_value.filter.return_value.all.return_value = [mapping_1, mapping_2]
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [mapping_1, mapping_2]
        # Each mapping needs 2 scalar calls (latest date + coverage count)
        mock_db_session.query.return_value.filter.return_value.scalar.side_effect = [
            today - timedelta(days=3),  # mapping 1 latest date
            25,  # mapping 1 coverage
            today - timedelta(days=1),  # mapping 2 latest date
            25,  # mapping 2 coverage
        ]

        service = IntegrationHealthService(mock_db_session)
        results = service.get_project_data_freshness(sample_project_id)

        assert len(results) == 2

    def test_returns_empty_for_project_without_mappings(self, mock_db_session, sample_project_id):
        """Should return empty list for project without mappings."""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        service = IntegrationHealthService(mock_db_session)
        results = service.get_project_data_freshness(sample_project_id)

        assert results == []
