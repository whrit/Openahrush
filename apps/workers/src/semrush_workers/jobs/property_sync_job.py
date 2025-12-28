"""
PropertySyncJob for refreshing integration property lists.

Handles discovery and synchronization of properties from external
providers (GSC sites, GA4 properties, BWT sites) for an integration account.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import select, update

from semrush_workers.jobs.base import Job, JobType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PropertyDiscoveryServiceProtocol(Protocol):
    """Protocol for property discovery service dependency."""

    async def discover_properties(
        self,
        integration_account_id: uuid.UUID,
        provider: str,
    ) -> list[dict[str, Any]]:
        """Discover properties for the given integration account."""
        ...


@dataclass
class PropertySyncJob(Job):
    """
    Job for synchronizing integration properties.

    Discovers and updates properties from external providers for
    an integration account. Used to refresh available sites/properties
    after OAuth connection or periodically.

    Attributes:
        integration_account_id: UUID of the integration account.
        provider: Provider type (google_search_console, google_analytics, etc.).
    """

    integration_account_id: uuid.UUID = field(default_factory=uuid.uuid4)
    provider: str = ""

    @classmethod
    def create(
        cls,
        integration_account_id: uuid.UUID,
        provider: str,
        max_retries: int = 3,
    ) -> PropertySyncJob:
        """
        Factory method to create a PropertySyncJob.

        Args:
            integration_account_id: UUID of the integration account.
            provider: Provider type (e.g., 'google_search_console').
            max_retries: Maximum retry attempts.

        Returns:
            Configured PropertySyncJob instance.
        """
        job_id = cls.generate_id()

        return cls(
            job_id=job_id,
            job_type=JobType.PROPERTY_SYNC,
            payload={
                "integration_account_id": str(integration_account_id),
                "provider": provider,
            },
            max_retries=max_retries,
            integration_account_id=integration_account_id,
            provider=provider,
        )

    async def execute(
        self,
        db_session: "AsyncSession",
        discovery_service: PropertyDiscoveryServiceProtocol | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute the property sync job.

        Args:
            db_session: Database session for persistence.
            discovery_service: Service for discovering properties.

        Returns:
            Result dictionary with success status and properties discovered.
        """
        self.record_attempt()

        try:
            if discovery_service is None:
                raise ValueError("discovery_service is required")

            # Discover properties from provider
            properties = await discovery_service.discover_properties(
                integration_account_id=self.integration_account_id,
                provider=self.provider,
            )

            properties_count = len(properties)

            # Update integration account last synced timestamp
            await self._update_account_last_synced(db_session)

            # Store or update discovered properties
            await self._upsert_properties(db_session, properties)

            await db_session.commit()
            self.mark_completed()

            if self.on_success:
                await self.on_success({
                    "success": True,
                    "properties_discovered": properties_count,
                })

            return {
                "success": True,
                "properties_discovered": properties_count,
            }

        except Exception as e:
            error_message = str(e)
            self.record_error(error_message)

            await db_session.rollback()

            if self.on_failure:
                await self.on_failure(e)

            return {
                "success": False,
                "error": error_message,
            }

    async def _update_account_last_synced(
        self,
        db_session: "AsyncSession",
    ) -> None:
        """
        Update the integration account's last synced timestamp.

        Args:
            db_session: Database session.
        """
        from semrush_core.models.integration_account import IntegrationAccount

        await db_session.execute(
            update(IntegrationAccount)
            .where(IntegrationAccount.id == self.integration_account_id)
            .values(last_sync_at=datetime.now(timezone.utc))
        )

    async def _upsert_properties(
        self,
        db_session: "AsyncSession",
        properties: list[dict[str, Any]],
    ) -> None:
        """
        Upsert discovered properties.

        Creates new properties or updates existing ones based on
        the property_id from the provider.

        Args:
            db_session: Database session.
            properties: List of property dictionaries from discovery.
        """
        from semrush_core.models.integration_property import IntegrationProperty

        for prop_data in properties:
            property_id = prop_data.get("property_id")
            if not property_id:
                continue

            # Check if property exists
            result = await db_session.execute(
                select(IntegrationProperty).where(
                    IntegrationProperty.integration_account_id == self.integration_account_id,
                    IntegrationProperty.provider == self.provider,
                    IntegrationProperty.property_id == property_id,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing property
                existing.display_name = prop_data.get("display_name")
                existing.property_type = prop_data.get("property_type")
                existing.metadata_ = prop_data.get("metadata", {})
            else:
                # Create new property
                new_prop = IntegrationProperty(
                    integration_account_id=self.integration_account_id,
                    provider=self.provider,
                    property_id=property_id,
                    display_name=prop_data.get("display_name"),
                    property_type=prop_data.get("property_type"),
                    metadata_=prop_data.get("metadata", {}),
                )
                db_session.add(new_prop)

    def to_dict(self) -> dict[str, Any]:
        """Serialize job to dictionary with property-sync-specific fields."""
        data = super().to_dict()
        data.update({
            "integration_account_id": str(self.integration_account_id),
            "provider": self.provider,
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PropertySyncJob:
        """Deserialize PropertySyncJob from dictionary."""
        base = Job.from_dict(data)

        return cls(
            job_id=base.job_id,
            job_type=base.job_type,
            payload=base.payload,
            attempts=base.attempts,
            max_retries=base.max_retries,
            created_at=base.created_at,
            last_error=base.last_error,
            scheduled_at=base.scheduled_at,
            started_at=base.started_at,
            completed_at=base.completed_at,
            integration_account_id=uuid.UUID(data["integration_account_id"]),
            provider=data["provider"],
        )
