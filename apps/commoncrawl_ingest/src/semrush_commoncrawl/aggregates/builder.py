"""
Aggregate builder for Common Crawl data.

Orchestrates the building of all aggregate tables (refdomains, anchors)
after edge ingestion completes. Updates snapshot status upon completion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_commoncrawl.aggregates.anchors import AnchorsAggregator
from semrush_commoncrawl.aggregates.refdomains import RefDomainsAggregator


@dataclass
class AggregateResult:
    """
    Result of an aggregate build operation.

    Contains statistics about the aggregation process including
    counts of records created and execution duration.

    Attributes:
        snapshot_id: The snapshot that was processed.
        refdomains_count: Number of referring domain records created.
        anchors_count: Number of anchor text records created.
        duration_seconds: Total execution time in seconds.
    """

    snapshot_id: str
    refdomains_count: int
    anchors_count: int
    duration_seconds: float


class AggregateBuilder:
    """
    Orchestrator for building aggregate tables.

    Coordinates the execution of RefDomainsAggregator and AnchorsAggregator,
    and updates the snapshot status upon completion.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        """
        Initialize the builder with a database session.

        Args:
            db_session: Async SQLAlchemy session for database operations.
        """
        self.db = db_session
        self.refdomains = RefDomainsAggregator(db_session)
        self.anchors = AnchorsAggregator(db_session)

    async def build_all(self, snapshot_id: str) -> AggregateResult:
        """
        Build all aggregates for a snapshot.

        Executes both refdomains and anchors aggregation, then updates
        the snapshot record with completion status and counts.

        This method is typically called automatically after edge ingestion
        completes for a snapshot.

        Args:
            snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10').

        Returns:
            AggregateResult containing statistics about the build operation.

        Raises:
            Exception: If aggregation fails, the exception is propagated.
        """
        start_time = time.monotonic()

        # Update snapshot status to aggregating
        await self._update_snapshot_status(snapshot_id, "aggregating")

        try:
            # Build refdomains aggregate
            refdomains_count = await self.refdomains.build_for_snapshot(snapshot_id)

            # Build anchors aggregate
            anchors_count = await self.anchors.build_for_snapshot(snapshot_id)

            duration = time.monotonic() - start_time

            # Update snapshot with completion status and counts
            await self._update_snapshot_completion(
                snapshot_id=snapshot_id,
                refdomains_count=refdomains_count,
                anchors_count=anchors_count,
            )

            return AggregateResult(
                snapshot_id=snapshot_id,
                refdomains_count=refdomains_count,
                anchors_count=anchors_count,
                duration_seconds=duration,
            )

        except Exception:
            # Update snapshot status to failed on error
            await self._update_snapshot_status(snapshot_id, "failed")
            raise

    async def trigger_build(self, snapshot_id: str) -> None:
        """
        Trigger aggregate build as a background job.

        Records the job request and initiates background processing.
        The actual aggregation will be performed asynchronously.

        Args:
            snapshot_id: Common Crawl snapshot identifier.
        """
        # Update snapshot status to indicate aggregation is queued
        await self._update_snapshot_status(snapshot_id, "aggregating")
        await self.db.commit()

    async def _update_snapshot_status(self, snapshot_id: str, status: str) -> None:
        """
        Update the status of a snapshot record.

        Args:
            snapshot_id: Common Crawl snapshot identifier.
            status: New status value.
        """
        sql = text("""
            UPDATE commoncrawl_snapshots
            SET status = :status, updated_at = NOW()
            WHERE snapshot_id = :snapshot_id
        """)
        await self.db.execute(sql, {"snapshot_id": snapshot_id, "status": status})
        await self.db.commit()

    async def _update_snapshot_completion(
        self,
        snapshot_id: str,
        refdomains_count: int,
        anchors_count: int,
    ) -> None:
        """
        Update snapshot record with aggregation completion details.

        Args:
            snapshot_id: Common Crawl snapshot identifier.
            refdomains_count: Number of refdomains records created.
            anchors_count: Number of anchor records created.
        """
        sql = text("""
            UPDATE commoncrawl_snapshots
            SET
                status = 'completed',
                refdomains_count = :refdomains_count,
                anchors_count = :anchors_count,
                aggregates_built_at = NOW(),
                updated_at = NOW()
            WHERE snapshot_id = :snapshot_id
        """)
        await self.db.execute(
            sql,
            {
                "snapshot_id": snapshot_id,
                "refdomains_count": refdomains_count,
                "anchors_count": anchors_count,
            },
        )
        await self.db.commit()
