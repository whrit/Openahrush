"""
Anchor text aggregator.

Builds aggregated anchor text statistics from raw Common Crawl edges.
Groups edges by (target_domain, normalized_anchor) and calculates
occurrence counts for each anchor text.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnchorsAggregator:
    """
    Aggregator for building anchor text distribution statistics.

    Takes raw edges from commoncrawl_edges and materializes
    aggregate statistics into commoncrawl_anchors table.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        """
        Initialize the aggregator with a database session.

        Args:
            db_session: Async SQLAlchemy session for database operations.
        """
        self.db = db_session

    async def build_for_snapshot(self, snapshot_id: str) -> int:
        """
        Build anchor text aggregate for a snapshot.

        Groups edges by (target_domain, anchor) and calculates:
        - count: Number of occurrences of each anchor text

        Anchor text normalization:
        - Trims leading/trailing whitespace using TRIM()
        - Skips NULL anchors
        - Skips empty string anchors

        Uses INSERT ... ON CONFLICT to handle upserts when rebuilding.

        Args:
            snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10').

        Returns:
            Count of anchor records created/updated.
        """
        sql = text("""
            INSERT INTO commoncrawl_anchors (
                id, snapshot_id, target_domain, anchor, count, created_at, updated_at
            )
            SELECT
                gen_random_uuid() as id,
                snapshot_id,
                target_domain,
                TRIM(anchor) as anchor,
                COUNT(*) as count,
                NOW() as created_at,
                NOW() as updated_at
            FROM commoncrawl_edges
            WHERE snapshot_id = :snapshot_id
              AND anchor IS NOT NULL
              AND anchor != ''
            GROUP BY snapshot_id, target_domain, TRIM(anchor)
            ON CONFLICT (snapshot_id, target_domain, anchor)
            DO UPDATE SET
                count = EXCLUDED.count,
                updated_at = NOW()
        """)

        result = await self.db.execute(sql, {"snapshot_id": snapshot_id})
        await self.db.commit()

        return result.rowcount
