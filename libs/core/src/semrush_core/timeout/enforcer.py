"""
Timeout enforcement service.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from semrush_core.models import CrawlRun, CrawlStatus, Export, ExportStatus
from semrush_core.timeout.config import TimeoutConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TimeoutEnforcer:
    """
    Service for enforcing job timeouts.

    Provides methods for:
    - Checking if jobs have timed out
    - Marking jobs as failed due to timeout
    - Finding timed out jobs for batch processing
    """

    def __init__(self, config: TimeoutConfig | None = None) -> None:
        """
        Initialize the timeout enforcer.

        Args:
            config: Timeout configuration.
        """
        self._config = config or TimeoutConfig()

    def is_crawl_timed_out(self, started_at: datetime) -> bool:
        """
        Check if a crawl has timed out.

        Args:
            started_at: When the crawl started.

        Returns:
            True if timed out, False otherwise.
        """
        elapsed = datetime.now(UTC) - started_at
        return elapsed.total_seconds() >= self._config.crawl_timeout_seconds

    def is_export_timed_out(self, started_at: datetime) -> bool:
        """
        Check if an export has timed out.

        Args:
            started_at: When the export started.

        Returns:
            True if timed out, False otherwise.
        """
        elapsed = datetime.now(UTC) - started_at
        return elapsed.total_seconds() >= self._config.export_timeout_seconds

    def get_remaining_crawl_time(self, started_at: datetime) -> timedelta:
        """
        Get remaining time before crawl timeout.

        Args:
            started_at: When the crawl started.

        Returns:
            Remaining time as timedelta (may be negative if exceeded).
        """
        elapsed = datetime.now(UTC) - started_at
        remaining = self._config.crawl_timeout - elapsed
        return remaining

    def get_remaining_export_time(self, started_at: datetime) -> timedelta:
        """
        Get remaining time before export timeout.

        Args:
            started_at: When the export started.

        Returns:
            Remaining time as timedelta (may be negative if exceeded).
        """
        elapsed = datetime.now(UTC) - started_at
        remaining = self._config.export_timeout - elapsed
        return remaining

    async def mark_crawl_timed_out(
        self,
        session: AsyncSession,
        crawl_id: uuid.UUID,
    ) -> None:
        """
        Mark a crawl as failed due to timeout.

        Args:
            session: Database session.
            crawl_id: The crawl run ID.
        """
        stmt = select(CrawlRun).where(CrawlRun.id == crawl_id)
        result = await session.execute(stmt)
        crawl = result.scalar_one_or_none()

        if crawl is None:
            logger.warning("Crawl not found for timeout: %s", crawl_id)
            return

        crawl.status = CrawlStatus.FAILED
        crawl.error_message = (
            f"Job timed out after {self._config.crawl_timeout_seconds} seconds"
        )
        crawl.finished_at = datetime.now(UTC)
        await session.flush()

        logger.info("Marked crawl %s as timed out", crawl_id)

    async def mark_export_timed_out(
        self,
        session: AsyncSession,
        export_id: uuid.UUID,
    ) -> None:
        """
        Mark an export as failed due to timeout.

        Args:
            session: Database session.
            export_id: The export ID.
        """
        stmt = select(Export).where(Export.id == export_id)
        result = await session.execute(stmt)
        export = result.scalar_one_or_none()

        if export is None:
            logger.warning("Export not found for timeout: %s", export_id)
            return

        export.status = ExportStatus.FAILED
        export.error_message = (
            f"Job timed out after {self._config.export_timeout_seconds} seconds"
        )
        await session.flush()

        logger.info("Marked export %s as timed out", export_id)

    async def find_timed_out_crawls(
        self,
        session: AsyncSession,
    ) -> list[CrawlRun]:
        """
        Find all crawls that have timed out.

        Args:
            session: Database session.

        Returns:
            List of timed out CrawlRun instances.
        """
        timeout_threshold = datetime.now(UTC) - self._config.crawl_timeout

        stmt = select(CrawlRun).where(
            CrawlRun.status == CrawlStatus.RUNNING,
            CrawlRun.started_at < timeout_threshold,
        )
        result = await session.execute(stmt)
        crawls = result.scalars().all()

        return list(crawls)

    async def find_timed_out_exports(
        self,
        session: AsyncSession,
    ) -> list[Export]:
        """
        Find all exports that have timed out.

        Args:
            session: Database session.

        Returns:
            List of timed out Export instances.
        """
        timeout_threshold = datetime.now(UTC) - self._config.export_timeout

        stmt = select(Export).where(
            Export.status == ExportStatus.RUNNING,
            Export.created_at < timeout_threshold,
        )
        result = await session.execute(stmt)
        exports = result.scalars().all()

        return list(exports)

    async def process_timed_out_crawls(
        self,
        session: AsyncSession,
        crawls: list[CrawlRun],
    ) -> int:
        """
        Process and mark multiple crawls as timed out.

        Args:
            session: Database session.
            crawls: List of CrawlRun instances to mark.

        Returns:
            Number of crawls marked.
        """
        count = 0
        for crawl in crawls:
            crawl.status = CrawlStatus.FAILED
            crawl.error_message = (
                f"Job timed out after {self._config.crawl_timeout_seconds} seconds"
            )
            crawl.finished_at = datetime.now(UTC)
            count += 1

        if count > 0:
            await session.flush()
            logger.info("Marked %d crawls as timed out", count)

        return count

    async def process_timed_out_exports(
        self,
        session: AsyncSession,
        exports: list[Export],
    ) -> int:
        """
        Process and mark multiple exports as timed out.

        Args:
            session: Database session.
            exports: List of Export instances to mark.

        Returns:
            Number of exports marked.
        """
        count = 0
        for export in exports:
            export.status = ExportStatus.FAILED
            export.error_message = (
                f"Job timed out after {self._config.export_timeout_seconds} seconds"
            )
            count += 1

        if count > 0:
            await session.flush()
            logger.info("Marked %d exports as timed out", count)

        return count
