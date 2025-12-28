"""
Integration Health Service for monitoring sync status and data freshness.

Provides visibility into:
- Sync health and status for integration mappings
- Data freshness based on provider-specific lag expectations
- Token validity for OAuth integrations
- Overall integration health across all connected accounts
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from semrush_core.models import (
        IntegrationAccount,
        IntegrationMapping,
        SyncRun,
    )

# Expected data lag in days for each provider
PROVIDER_DATA_LAG_DAYS: dict[str, int] = {
    "google_search_console": 3,  # GSC has ~3 day lag
    "google_analytics": 1,  # GA4 typically has ~1 day lag
    "bing_webmaster_tools": 2,  # BWT has ~2 day lag
}

# Default sync interval in hours
DEFAULT_SYNC_INTERVAL_HOURS = 24

# Threshold for considering sync stale (in hours)
STALE_SYNC_THRESHOLD_HOURS = 48

# Threshold for consecutive failures to mark unhealthy
CONSECUTIVE_FAILURE_THRESHOLD = 2


@dataclass
class SyncStatus:
    """Data class representing sync status for a mapping."""

    mapping_id: UUID
    provider: str
    property_id: str | None
    status: str
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    error_count: int
    error_message: str | None
    is_healthy: bool
    status_message: str


@dataclass
class DataFreshness:
    """Data class representing data freshness for a mapping."""

    mapping_id: UUID
    provider: str
    property_id: str | None
    latest_data_date: date | None
    expected_lag_days: int
    days_behind: int
    coverage_pct: float
    is_fresh: bool
    status_message: str


@dataclass
class IntegrationHealth:
    """Data class representing overall health of an integration."""

    provider: str
    connected: bool
    token_valid: bool
    properties_count: int
    last_sync: datetime | None
    is_healthy: bool
    status_message: str


class IntegrationHealthService:
    """
    Service for monitoring integration health and data quality.

    Provides methods to check:
    - Sync status and health for individual mappings
    - Data freshness based on provider-specific expectations
    - Token validity for OAuth integrations
    - Overall integration health across all accounts

    Example:
        >>> service = IntegrationHealthService(db_session)
        >>> status = service.get_sync_status(mapping_id)
        >>> print(f"Last sync: {status.last_sync_at}, healthy: {status.is_healthy}")
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize health service.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db

    def get_sync_status(self, mapping_id: UUID) -> SyncStatus | None:
        """
        Get sync status for an integration mapping.

        Args:
            mapping_id: UUID of the integration mapping.

        Returns:
            SyncStatus with sync details, or None if mapping not found.
        """
        from semrush_core.models import IntegrationMapping

        mapping = self.db.query(IntegrationMapping).filter(
            IntegrationMapping.id == mapping_id
        ).first()

        if not mapping:
            return None

        # Get sync runs ordered by created_at desc
        sync_runs = mapping.sync_runs or []

        if not sync_runs:
            return SyncStatus(
                mapping_id=mapping_id,
                provider=self._get_provider(mapping),
                property_id=self._get_property_id(mapping),
                status="never",
                last_sync_at=None,
                next_sync_at=None,
                error_count=0,
                error_message=None,
                is_healthy=False,
                status_message="Integration has never been synced",
            )

        latest_run = sync_runs[0]
        status = latest_run.status
        last_sync_at = latest_run.completed_at
        error_message = latest_run.error_message if status == "failed" else None

        # Count consecutive errors
        error_count = self._count_consecutive_errors(sync_runs)

        # Calculate next sync time
        next_sync_at = None
        if status not in ("running", "queued") and last_sync_at:
            next_sync_at = last_sync_at + timedelta(hours=DEFAULT_SYNC_INTERVAL_HOURS)

        # Determine health
        is_healthy = self._is_sync_healthy(last_sync_at, error_count, status)

        # Generate status message
        status_message = self._generate_sync_status_message(
            status, last_sync_at, error_count, error_message
        )

        return SyncStatus(
            mapping_id=mapping_id,
            provider=self._get_provider(mapping),
            property_id=self._get_property_id(mapping),
            status=status,
            last_sync_at=last_sync_at,
            next_sync_at=next_sync_at,
            error_count=error_count,
            error_message=error_message,
            is_healthy=is_healthy,
            status_message=status_message,
        )

    def get_data_freshness(
        self, mapping_id: UUID, lookback_days: int = 30
    ) -> DataFreshness | None:
        """
        Get data freshness metrics for an integration mapping.

        Args:
            mapping_id: UUID of the integration mapping.
            lookback_days: Number of days to check for coverage.

        Returns:
            DataFreshness with freshness metrics, or None if mapping not found.
        """
        from semrush_core.models import IntegrationMapping

        mapping = self.db.query(IntegrationMapping).filter(
            IntegrationMapping.id == mapping_id
        ).first()

        if not mapping:
            return None

        provider = self._get_provider(mapping)
        property_id = self._get_property_id(mapping)
        expected_lag = PROVIDER_DATA_LAG_DAYS.get(provider, 2)

        # Get latest data date from fact tables
        latest_data_date = self._get_latest_data_date(mapping)

        # Calculate days behind
        days_behind = 0
        if latest_data_date:
            today = date.today()
            actual_lag = (today - latest_data_date).days
            days_behind = max(0, actual_lag - expected_lag)

        # Calculate coverage
        coverage_pct = self._calculate_coverage(mapping, lookback_days)

        # Determine if data is fresh
        is_fresh = days_behind <= 1 and coverage_pct >= 80.0

        # Generate status message
        status_message = self._generate_freshness_message(
            latest_data_date, days_behind, coverage_pct, provider
        )

        return DataFreshness(
            mapping_id=mapping_id,
            provider=provider,
            property_id=property_id,
            latest_data_date=latest_data_date,
            expected_lag_days=expected_lag,
            days_behind=days_behind,
            coverage_pct=coverage_pct,
            is_fresh=is_fresh,
            status_message=status_message,
        )

    def get_integration_health(self, user_id: UUID) -> list[IntegrationHealth]:
        """
        Get health status for all integrations belonging to a user.

        Args:
            user_id: UUID of the user.

        Returns:
            List of IntegrationHealth for each connected integration.
        """
        from semrush_core.models import IntegrationAccount

        accounts = self.db.query(IntegrationAccount).filter(
            IntegrationAccount.user_id == user_id
        ).all()

        results = []
        for account in accounts:
            provider = account.provider
            connected = True
            token_valid = self._check_token_valid(account)
            properties_count = len(account.properties) if account.properties else 0
            last_sync = self._get_account_last_sync(account)

            is_healthy = connected and token_valid
            status_message = self._generate_health_message(
                connected, token_valid, properties_count, last_sync
            )

            results.append(IntegrationHealth(
                provider=provider,
                connected=connected,
                token_valid=token_valid,
                properties_count=properties_count,
                last_sync=last_sync,
                is_healthy=is_healthy,
                status_message=status_message,
            ))

        return results

    def check_token_validity(self, user_id: UUID, provider: str) -> bool:
        """
        Check if an OAuth token is valid for a user and provider.

        Args:
            user_id: UUID of the user.
            provider: Provider name (e.g., 'google_search_console').

        Returns:
            True if token is valid and not expired, False otherwise.
        """
        from semrush_core.models import IntegrationAccount

        account = self.db.query(IntegrationAccount).filter(
            IntegrationAccount.user_id == user_id,
            IntegrationAccount.provider == provider,
        ).first()

        if not account:
            return False

        return self._check_token_valid(account)

    def get_project_sync_status(self, project_id: UUID) -> list[SyncStatus]:
        """
        Get sync status for all mappings in a project.

        Args:
            project_id: UUID of the project.

        Returns:
            List of SyncStatus for each mapping in the project.
        """
        from semrush_core.models import IntegrationMapping

        mappings = self.db.query(IntegrationMapping).filter(
            IntegrationMapping.project_id == project_id
        ).all()

        results = []
        for mapping in mappings:
            status = self.get_sync_status(mapping.id)
            if status:
                results.append(status)

        return results

    def get_project_data_freshness(
        self, project_id: UUID, lookback_days: int = 30
    ) -> list[DataFreshness]:
        """
        Get data freshness for all mappings in a project.

        Args:
            project_id: UUID of the project.
            lookback_days: Number of days to check for coverage.

        Returns:
            List of DataFreshness for each mapping in the project.
        """
        from semrush_core.models import IntegrationMapping

        mappings = self.db.query(IntegrationMapping).filter(
            IntegrationMapping.project_id == project_id
        ).all()

        results = []
        for mapping in mappings:
            freshness = self.get_data_freshness(mapping.id, lookback_days)
            if freshness:
                results.append(freshness)

        return results

    # Private helper methods

    def _get_provider(self, mapping: "IntegrationMapping") -> str:
        """Get provider name from mapping."""
        if mapping.integration_property:
            return mapping.integration_property.provider
        return "unknown"

    def _get_property_id(self, mapping: "IntegrationMapping") -> str | None:
        """Get property ID from mapping."""
        if mapping.integration_property:
            return mapping.integration_property.property_id
        return None

    def _count_consecutive_errors(self, sync_runs: list["SyncRun"]) -> int:
        """Count consecutive failed sync runs from the most recent."""
        count = 0
        for run in sync_runs:
            if run.status == "failed":
                count += 1
            else:
                break
        return count

    def _is_sync_healthy(
        self,
        last_sync_at: datetime | None,
        error_count: int,
        status: str,
    ) -> bool:
        """Determine if sync is healthy based on recency and error count."""
        if status in ("running", "queued"):
            return True

        if error_count >= CONSECUTIVE_FAILURE_THRESHOLD:
            return False

        if not last_sync_at:
            return False

        now = datetime.now(UTC)
        last_sync_tz = last_sync_at
        if last_sync_at.tzinfo is None:
            last_sync_tz = last_sync_at.replace(tzinfo=UTC)

        hours_since_sync = (now - last_sync_tz).total_seconds() / 3600
        return hours_since_sync <= STALE_SYNC_THRESHOLD_HOURS

    def _generate_sync_status_message(
        self,
        status: str,
        last_sync_at: datetime | None,
        error_count: int,
        error_message: str | None,
    ) -> str:
        """Generate a human-readable status message."""
        if status == "running":
            return "Sync is currently in progress"

        if status == "queued":
            return "Sync is queued and waiting to start"

        if status == "failed":
            if error_count >= CONSECUTIVE_FAILURE_THRESHOLD:
                return f"Sync failed {error_count} times consecutively. Last error: {error_message or 'Unknown'}"
            return f"Last sync failed: {error_message or 'Unknown error'}"

        if not last_sync_at:
            return "Integration has never been synced"

        now = datetime.now(UTC)
        last_sync_tz = last_sync_at
        if last_sync_at.tzinfo is None:
            last_sync_tz = last_sync_at.replace(tzinfo=UTC)

        hours_since = (now - last_sync_tz).total_seconds() / 3600

        if hours_since > STALE_SYNC_THRESHOLD_HOURS:
            return f"Data is stale. Last sync was {int(hours_since)} hours ago"

        return f"Sync is healthy. Last synced {int(hours_since)} hours ago"

    def _get_latest_data_date(self, mapping: "IntegrationMapping") -> date | None:
        """Get the latest data date from fact tables for a mapping."""
        from semrush_core.models import AnalyticsFactDaily, SearchFactDaily

        provider = self._get_provider(mapping)
        project_id = mapping.project_id

        if provider in ("google_search_console", "bing_webmaster_tools"):
            result = self.db.query(func.max(SearchFactDaily.date)).filter(
                SearchFactDaily.project_id == project_id
            ).scalar()
        elif provider == "google_analytics":
            result = self.db.query(func.max(AnalyticsFactDaily.date)).filter(
                AnalyticsFactDaily.project_id == project_id
            ).scalar()
        else:
            result = None

        return result

    def _calculate_coverage(
        self, mapping: "IntegrationMapping", lookback_days: int
    ) -> float:
        """Calculate coverage percentage of expected dates with data."""
        from semrush_core.models import AnalyticsFactDaily, SearchFactDaily

        provider = self._get_provider(mapping)
        project_id = mapping.project_id
        expected_lag = PROVIDER_DATA_LAG_DAYS.get(provider, 2)

        # Calculate expected date range
        today = date.today()
        end_date = today - timedelta(days=expected_lag)
        start_date = end_date - timedelta(days=lookback_days)
        expected_days = lookback_days

        # Count distinct dates with data
        if provider in ("google_search_console", "bing_webmaster_tools"):
            count = self.db.query(func.count(func.distinct(SearchFactDaily.date))).filter(
                SearchFactDaily.project_id == project_id,
                SearchFactDaily.date >= start_date,
                SearchFactDaily.date <= end_date,
            ).scalar() or 0
        elif provider == "google_analytics":
            count = self.db.query(func.count(func.distinct(AnalyticsFactDaily.date))).filter(
                AnalyticsFactDaily.project_id == project_id,
                AnalyticsFactDaily.date >= start_date,
                AnalyticsFactDaily.date <= end_date,
            ).scalar() or 0
        else:
            count = 0

        if expected_days == 0:
            return 0.0

        return (count / expected_days) * 100.0

    def _generate_freshness_message(
        self,
        latest_data_date: date | None,
        days_behind: int,
        coverage_pct: float,
        provider: str,
    ) -> str:
        """Generate a human-readable freshness message."""
        if latest_data_date is None:
            return "No data available for this integration"

        expected_lag = PROVIDER_DATA_LAG_DAYS.get(provider, 2)

        if days_behind == 0:
            return f"Data is up to date (within expected {expected_lag}-day lag)"

        if days_behind <= 1:
            return f"Data is slightly behind ({days_behind} day beyond expected lag)"

        return f"Data is {days_behind} days behind expected freshness. Coverage: {coverage_pct:.1f}%"

    def _check_token_valid(self, account: "IntegrationAccount") -> bool:
        """Check if an account's token is valid."""
        token = account.token
        if not token:
            return False

        # Check if token has an expiration and if it's expired
        if token.expires_at is None:
            # If no expiry, check if refresh token exists
            return token.refresh_token_encrypted is not None

        now = datetime.now(UTC)
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        # Token is valid if not expired, or if near expiry but has refresh token
        if now < expires_at:
            return True

        # If expired, still valid if refresh token exists
        return token.refresh_token_encrypted is not None

    def _get_account_last_sync(self, account: "IntegrationAccount") -> datetime | None:
        """Get the most recent sync time across all properties of an account."""
        last_sync: datetime | None = None

        for prop in account.properties or []:
            if hasattr(prop, "mappings"):
                for mapping in prop.mappings or []:
                    for run in mapping.sync_runs or []:
                        if run.completed_at:
                            if last_sync is None or run.completed_at > last_sync:
                                last_sync = run.completed_at

        return last_sync

    def _generate_health_message(
        self,
        connected: bool,
        token_valid: bool,
        properties_count: int,
        last_sync: datetime | None,
    ) -> str:
        """Generate a human-readable health message."""
        if not connected:
            return "Integration is not connected"

        if not token_valid:
            return "OAuth token is invalid or expired. Please reconnect the integration"

        if properties_count == 0:
            return "Connected but no properties discovered"

        if last_sync is None:
            return f"Connected with {properties_count} properties. No syncs completed yet"

        now = datetime.now(UTC)
        last_sync_tz = last_sync
        if last_sync.tzinfo is None:
            last_sync_tz = last_sync.replace(tzinfo=UTC)

        hours_since = (now - last_sync_tz).total_seconds() / 3600

        if hours_since > STALE_SYNC_THRESHOLD_HOURS:
            return f"Connected with {properties_count} properties. Data may be stale (last sync: {int(hours_since)}h ago)"

        return f"Healthy. {properties_count} properties connected, last sync {int(hours_since)}h ago"
