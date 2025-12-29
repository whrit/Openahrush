"""
Data synchronization service for fetching and storing provider data.

Orchestrates data fetching from external providers and storing to fact tables.
Emits integration sync events per ARCHITECTURE.md Section 7.2.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from semrush_integrations.adapters.data.base import DataAdapter, DateRange
from semrush_integrations.adapters.data.bwt_data import BWTDataAdapter
from semrush_integrations.adapters.data.ga4_data import GA4DataAdapter
from semrush_integrations.adapters.data.gsc_data import GSCDataAdapter
from semrush_integrations.events import (
    BaseIntegrationEventEmitter,
    NoOpIntegrationEventEmitter,
)
from semrush_integrations.schemas.analytics_data import AnalyticsDataRow
from semrush_integrations.schemas.search_data import SearchDataRow

if TYPE_CHECKING:
    from semrush_core.models.integration_mapping import IntegrationMapping
    from semrush_core.models.sync_run import SyncRun
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Batch size for database inserts
BATCH_SIZE = 1000


class DataSyncService:
    """
    Service for synchronizing data from external providers.

    Handles the complete sync workflow:
    1. Create SyncRun record to track progress
    2. Get appropriate adapter for the provider
    3. Fetch data from provider API
    4. Transform to fact table format
    5. Batch insert to database
    6. Update SyncRun with results

    Example:
        >>> service = DataSyncService(session=db_session)
        >>> sync_run = await service.sync_search_data(
        ...     mapping=integration_mapping,
        ...     date_range=DateRange(date(2024, 1, 1), date(2024, 1, 7)),
        ... )
        >>> print(f"Synced {sync_run.records_written} records")
    """

    def __init__(
        self,
        session: AsyncSession,
        event_emitter: BaseIntegrationEventEmitter | None = None,
    ) -> None:
        """
        Initialize the sync service.

        Args:
            session: SQLAlchemy async session for database operations.
            event_emitter: Optional event emitter for sync lifecycle events.
                If not provided, a NoOpIntegrationEventEmitter is used.
        """
        self.session = session
        self.event_emitter = event_emitter or NoOpIntegrationEventEmitter()

    async def sync_search_data(
        self,
        mapping: IntegrationMapping,
        date_range: DateRange,
    ) -> SyncRun:
        """
        Sync search data for an integration mapping.

        Fetches search performance data from the provider and stores
        it in the search_fact_daily table. Emits integration sync events
        for tracking and monitoring.

        Args:
            mapping: Integration mapping with property and account info.
            date_range: Date range to sync.

        Returns:
            SyncRun with status and results.
        """
        from semrush_core.models.sync_run import SyncMode, SyncRun, SyncStatus

        provider = mapping.integration_property.provider
        property_id = mapping.integration_property.property_id
        account_id = mapping.integration_property.account_id

        # Emit sync requested event
        await self.event_emitter.emit_sync_requested(
            project_id=mapping.project_id,
            provider=provider,
            integration_account_id=account_id,
            property_id=property_id,
            date_range_start=date_range.start_date,
            date_range_end=date_range.end_date,
            mode=SyncMode.INCREMENTAL.value,
        )

        # Create sync run record
        sync_run = SyncRun(
            integration_mapping_id=mapping.id,
            provider=provider,
            property_id=property_id,
            mode=SyncMode.INCREMENTAL.value,
            status=SyncStatus.RUNNING.value,
            date_range_start=date_range.start_date,
            date_range_end=date_range.end_date,
            started_at=datetime.now(UTC),
        )
        self.session.add(sync_run)

        try:
            records_written = await self._fetch_and_store_search_data(
                mapping=mapping,
                date_range=date_range,
            )
            sync_run.mark_completed(records_written)

            # Emit sync completed event
            await self.event_emitter.emit_sync_completed(
                project_id=mapping.project_id,
                provider=provider,
                integration_account_id=account_id,
                property_id=property_id,
                date_range_start=date_range.start_date,
                date_range_end=date_range.end_date,
                mode=SyncMode.INCREMENTAL.value,
                records_written=records_written,
            )
        except Exception as e:
            logger.exception(f"Error syncing search data for mapping {mapping.id}")
            sync_run.mark_failed(str(e))

            # Emit sync failed event
            await self.event_emitter.emit_sync_failed(
                project_id=mapping.project_id,
                provider=provider,
                integration_account_id=account_id,
                property_id=property_id,
                error=str(e),
            )

        await self.session.commit()
        return sync_run

    async def sync_analytics_data(
        self,
        mapping: IntegrationMapping,
        date_range: DateRange,
    ) -> SyncRun:
        """
        Sync analytics data for an integration mapping.

        Fetches analytics data from the provider and stores
        it in the analytics_fact_daily table. Emits integration sync events
        for tracking and monitoring.

        Args:
            mapping: Integration mapping with property and account info.
            date_range: Date range to sync.

        Returns:
            SyncRun with status and results.
        """
        from semrush_core.models.sync_run import SyncMode, SyncRun, SyncStatus

        provider = mapping.integration_property.provider
        property_id = mapping.integration_property.property_id
        account_id = mapping.integration_property.account_id

        # Emit sync requested event
        await self.event_emitter.emit_sync_requested(
            project_id=mapping.project_id,
            provider=provider,
            integration_account_id=account_id,
            property_id=property_id,
            date_range_start=date_range.start_date,
            date_range_end=date_range.end_date,
            mode=SyncMode.INCREMENTAL.value,
        )

        # Create sync run record
        sync_run = SyncRun(
            integration_mapping_id=mapping.id,
            provider=provider,
            property_id=property_id,
            mode=SyncMode.INCREMENTAL.value,
            status=SyncStatus.RUNNING.value,
            date_range_start=date_range.start_date,
            date_range_end=date_range.end_date,
            started_at=datetime.now(UTC),
        )
        self.session.add(sync_run)

        try:
            records_written = await self._fetch_and_store_analytics_data(
                mapping=mapping,
                date_range=date_range,
            )
            sync_run.mark_completed(records_written)

            # Emit sync completed event
            await self.event_emitter.emit_sync_completed(
                project_id=mapping.project_id,
                provider=provider,
                integration_account_id=account_id,
                property_id=property_id,
                date_range_start=date_range.start_date,
                date_range_end=date_range.end_date,
                mode=SyncMode.INCREMENTAL.value,
                records_written=records_written,
            )
        except Exception as e:
            logger.exception(f"Error syncing analytics data for mapping {mapping.id}")
            sync_run.mark_failed(str(e))

            # Emit sync failed event
            await self.event_emitter.emit_sync_failed(
                project_id=mapping.project_id,
                provider=provider,
                integration_account_id=account_id,
                property_id=property_id,
                error=str(e),
            )

        await self.session.commit()
        return sync_run

    async def _fetch_and_store_search_data(
        self,
        mapping: IntegrationMapping,
        date_range: DateRange,
    ) -> int:
        """
        Fetch search data from provider and store in database.

        Args:
            mapping: Integration mapping with property and account info.
            date_range: Date range to sync.

        Returns:
            Number of records written.
        """
        provider = mapping.integration_property.provider
        property_id = mapping.integration_property.property_id
        access_token = mapping.integration_property.account.access_token  # type: ignore[attr-defined]

        # Get appropriate adapter
        adapter = self._get_data_adapter(provider, access_token)

        # Determine engine based on provider
        engine = "bing" if provider == "bing_webmaster_tools" else "google"

        # Fetch data
        response = await adapter.fetch_data(property_id, date_range)

        # Store in batches
        records_written = await self._batch_insert_search_facts(
            rows=response.rows,
            project_id=mapping.project_id,
            site_id=mapping.site_id,
            engine=engine,
        )

        return records_written

    async def _fetch_and_store_analytics_data(
        self,
        mapping: IntegrationMapping,
        date_range: DateRange,
    ) -> int:
        """
        Fetch analytics data from provider and store in database.

        Args:
            mapping: Integration mapping with property and account info.
            date_range: Date range to sync.

        Returns:
            Number of records written.
        """
        provider = mapping.integration_property.provider
        property_id = mapping.integration_property.property_id
        access_token = mapping.integration_property.account.access_token  # type: ignore[attr-defined]

        # Get appropriate adapter
        adapter = self._get_data_adapter(provider, access_token)

        # Fetch data
        response = await adapter.fetch_data(property_id, date_range)

        # Store in batches
        records_written = await self._batch_insert_analytics_facts(
            rows=response.rows,
            project_id=mapping.project_id,
            site_id=mapping.site_id,
        )

        return records_written

    def _get_data_adapter(self, provider: str, access_token: str) -> DataAdapter:
        """
        Get the appropriate data adapter for a provider.

        Args:
            provider: Provider name (google_search_console, google_analytics, etc.).
            access_token: OAuth access token.

        Returns:
            Configured data adapter instance.

        Raises:
            ValueError: If provider is not recognized.
        """
        if provider == "google_search_console":
            return GSCDataAdapter(access_token=access_token)
        elif provider == "google_analytics":
            return GA4DataAdapter(access_token=access_token)
        elif provider == "bing_webmaster_tools":
            return BWTDataAdapter(access_token=access_token)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _batch_insert_search_facts(
        self,
        rows: list[SearchDataRow],
        project_id: uuid.UUID,
        site_id: uuid.UUID | None = None,
        engine: str = "google",
    ) -> int:
        """
        Batch insert search fact records.

        Args:
            rows: List of search data rows to insert.
            project_id: Project UUID.
            site_id: Optional site UUID.
            engine: Search engine (google, bing).

        Returns:
            Number of records inserted.
        """
        from semrush_core.models.search_fact import SearchFactDaily

        total_inserted = 0

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            facts = [
                SearchFactDaily(
                    project_id=project_id,
                    site_id=site_id,
                    engine=engine,
                    date=row.date,
                    query=row.query,
                    page_url=row.page_url,
                    country=row.country,
                    device=row.device,
                    search_type=row.search_type,
                    impressions=row.impressions,
                    clicks=row.clicks,
                    ctr=row.ctr,
                    avg_position=row.position,
                    data_quality_flags={},
                )
                for row in batch
            ]
            self.session.add_all(facts)
            total_inserted += len(facts)

        return total_inserted

    async def _batch_insert_analytics_facts(
        self,
        rows: list[AnalyticsDataRow],
        project_id: uuid.UUID,
        site_id: uuid.UUID | None = None,
    ) -> int:
        """
        Batch insert analytics fact records.

        Args:
            rows: List of analytics data rows to insert.
            project_id: Project UUID.
            site_id: Optional site UUID.

        Returns:
            Number of records inserted.
        """
        from semrush_core.models.analytics_fact import AnalyticsFactDaily

        total_inserted = 0

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            facts = [
                AnalyticsFactDaily(
                    project_id=project_id,
                    site_id=site_id,
                    date=row.date,
                    page_url=row.page_url,
                    country=row.country,
                    device=row.device,
                    source_medium=row.source_medium,
                    campaign=row.campaign,
                    sessions=row.sessions,
                    users=row.users,
                    engagement_rate=row.engagement_rate,
                    conversions=row.conversions,
                    revenue=row.revenue,
                    data_quality_flags={},
                )
                for row in batch
            ]
            self.session.add_all(facts)
            total_inserted += len(facts)

        return total_inserted
