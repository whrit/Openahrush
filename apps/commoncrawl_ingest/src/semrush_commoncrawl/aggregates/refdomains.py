"""
Referring domains aggregator.

Builds aggregated referring domain statistics from raw Common Crawl edges.
Groups edges by (target_domain, source_domain) and calculates:
- Backlink count per referring domain
- First seen timestamp
- Last seen timestamp
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RefDomainsAggregator:
    """
    Aggregator for building referring domain statistics.

    Takes raw edges from commoncrawl_edges and materializes
    aggregate statistics into commoncrawl_refdomains table.
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
        Build refdomains aggregate for a snapshot.

        Groups edges by (target_domain, source_domain) and calculates:
        - backlink_count: COUNT(*) of edges for this domain pair
        - first_seen: MIN(discovered_at) across all edges
        - last_seen: MAX(discovered_at) across all edges

        Uses INSERT ... ON CONFLICT to handle upserts when rebuilding.

        Args:
            snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10').

        Returns:
            Count of referring domain records created/updated.
        """
        sql = text("""
            INSERT INTO commoncrawl_refdomains (
                id, snapshot_id, target_domain, source_domain,
                backlink_count, first_seen, last_seen, created_at, updated_at
            )
            SELECT
                gen_random_uuid() as id,
                snapshot_id,
                target_domain,
                source_domain,
                COUNT(*) as backlink_count,
                MIN(discovered_at) as first_seen,
                MAX(discovered_at) as last_seen,
                NOW() as created_at,
                NOW() as updated_at
            FROM commoncrawl_edges
            WHERE snapshot_id = :snapshot_id
            GROUP BY snapshot_id, target_domain, source_domain
            ON CONFLICT (snapshot_id, target_domain, source_domain)
            DO UPDATE SET
                backlink_count = EXCLUDED.backlink_count,
                first_seen = EXCLUDED.first_seen,
                last_seen = EXCLUDED.last_seen,
                updated_at = NOW()
        """)

        result = await self.db.execute(sql, {"snapshot_id": snapshot_id})
        await self.db.commit()

        return result.rowcount

    async def rebuild_for_domain(self, target_domain: str, snapshot_id: str) -> int:
        """
        Rebuild aggregates for a specific target domain.

        Useful for targeted rebuilds without reprocessing the entire snapshot.
        Deletes existing records for the domain and rebuilds from edges.

        Args:
            target_domain: The domain to rebuild aggregates for.
            snapshot_id: Common Crawl snapshot identifier.

        Returns:
            Count of referring domain records created.
        """
        # First, delete existing records for this domain in the snapshot
        delete_sql = text("""
            DELETE FROM commoncrawl_refdomains
            WHERE snapshot_id = :snapshot_id AND target_domain = :target_domain
        """)
        await self.db.execute(
            delete_sql,
            {"snapshot_id": snapshot_id, "target_domain": target_domain},
        )

        # Then insert fresh aggregates
        insert_sql = text("""
            INSERT INTO commoncrawl_refdomains (
                id, snapshot_id, target_domain, source_domain,
                backlink_count, first_seen, last_seen, created_at, updated_at
            )
            SELECT
                gen_random_uuid() as id,
                snapshot_id,
                target_domain,
                source_domain,
                COUNT(*) as backlink_count,
                MIN(discovered_at) as first_seen,
                MAX(discovered_at) as last_seen,
                NOW() as created_at,
                NOW() as updated_at
            FROM commoncrawl_edges
            WHERE snapshot_id = :snapshot_id AND target_domain = :target_domain
            GROUP BY snapshot_id, target_domain, source_domain
            ON CONFLICT (snapshot_id, target_domain, source_domain)
            DO UPDATE SET
                backlink_count = EXCLUDED.backlink_count,
                first_seen = EXCLUDED.first_seen,
                last_seen = EXCLUDED.last_seen,
                updated_at = NOW()
        """)

        result = await self.db.execute(
            insert_sql,
            {"snapshot_id": snapshot_id, "target_domain": target_domain},
        )
        await self.db.commit()

        return result.rowcount
