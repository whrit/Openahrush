"""
PostgreSQL storage adapter for Common Crawl edges.

Implements the EdgeStorage protocol using SQLAlchemy async
for storing and querying backlink data in PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_commoncrawl.storage.base import (
    AnchorCount,
    Backlink,
    Edge,
    RefDomain,
)


class PostgresStorage:
    """
    PostgreSQL implementation of EdgeStorage.

    Uses SQLAlchemy async sessions for database operations.
    Stores edges in commoncrawl_edges table and provides
    query methods for refdomains, backlinks, and anchors.

    Attributes:
        session: SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize PostgresStorage with a database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def insert_edges(self, edges: list[Edge]) -> int:
        """
        Batch insert edges into the commoncrawl_edges table.

        Uses executemany for efficient batch insertion.

        Args:
            edges: List of Edge objects to insert.

        Returns:
            Number of edges inserted.
        """
        if not edges:
            return 0

        # Build INSERT statement with VALUES
        insert_sql = text("""
            INSERT INTO commoncrawl_edges (
                snapshot_id,
                source_url,
                source_domain,
                target_url,
                target_domain,
                anchor,
                rel_flags
            ) VALUES (
                :snapshot_id,
                :source_url,
                :source_domain,
                :target_url,
                :target_domain,
                :anchor,
                :rel_flags
            )
        """)

        # Prepare parameters for batch insert
        params = [
            {
                "snapshot_id": edge.snapshot_id,
                "source_url": edge.source_url,
                "source_domain": edge.source_domain,
                "target_url": edge.target_url,
                "target_domain": edge.target_domain,
                "anchor": edge.anchor,
                "rel_flags": edge.rel_flags,
            }
            for edge in edges
        ]

        await self.session.execute(insert_sql, params)
        await self.session.flush()

        return len(edges)

    async def query_refdomains(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
    ) -> list[RefDomain]:
        """
        Query referring domains for a target domain.

        Queries the commoncrawl_refdomains aggregate table
        (or builds aggregates from edges if table doesn't exist).

        Args:
            domain: Target domain to query backlinks for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of referring domains to return.

        Returns:
            List of RefDomain objects sorted by backlink_count descending.
        """
        # Query from aggregate table or build on-the-fly
        if snapshot_id:
            query = text("""
                SELECT
                    source_domain,
                    COUNT(*) as backlink_count,
                    MIN(created_at) as first_seen,
                    MAX(created_at) as last_seen
                FROM commoncrawl_edges
                WHERE target_domain = :domain
                  AND snapshot_id = :snapshot_id
                GROUP BY source_domain
                ORDER BY backlink_count DESC
                LIMIT :limit
            """)
            params = {"domain": domain, "snapshot_id": snapshot_id, "limit": limit}
        else:
            query = text("""
                SELECT
                    source_domain,
                    COUNT(*) as backlink_count,
                    MIN(created_at) as first_seen,
                    MAX(created_at) as last_seen
                FROM commoncrawl_edges
                WHERE target_domain = :domain
                GROUP BY source_domain
                ORDER BY backlink_count DESC
                LIMIT :limit
            """)
            params = {"domain": domain, "limit": limit}

        result = await self.session.execute(query, params)
        rows = result.fetchall()

        return [
            RefDomain(
                source_domain=row.source_domain,
                backlink_count=row.backlink_count,
                first_seen=row.first_seen,
                last_seen=row.last_seen,
            )
            for row in rows
        ]

    async def query_backlinks(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Backlink]:
        """
        Query individual backlinks for a target domain.

        Args:
            domain: Target domain to query backlinks for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of backlinks to return.
            offset: Number of backlinks to skip (for pagination).

        Returns:
            List of Backlink objects.
        """
        if snapshot_id:
            query = text("""
                SELECT
                    source_url,
                    source_domain,
                    target_url,
                    target_domain,
                    anchor,
                    rel_flags
                FROM commoncrawl_edges
                WHERE target_domain = :domain
                  AND snapshot_id = :snapshot_id
                ORDER BY source_domain, source_url
                LIMIT :limit
                OFFSET :offset
            """)
            params = {
                "domain": domain,
                "snapshot_id": snapshot_id,
                "limit": limit,
                "offset": offset,
            }
        else:
            query = text("""
                SELECT
                    source_url,
                    source_domain,
                    target_url,
                    target_domain,
                    anchor,
                    rel_flags
                FROM commoncrawl_edges
                WHERE target_domain = :domain
                ORDER BY source_domain, source_url
                LIMIT :limit
                OFFSET :offset
            """)
            params = {"domain": domain, "limit": limit, "offset": offset}

        result = await self.session.execute(query, params)
        rows = result.fetchall()

        return [
            Backlink(
                source_url=row.source_url,
                source_domain=row.source_domain,
                target_url=row.target_url,
                target_domain=row.target_domain,
                anchor=row.anchor,
                rel_flags=row.rel_flags,
            )
            for row in rows
        ]

    async def query_anchors(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
    ) -> list[AnchorCount]:
        """
        Query anchor text aggregates for a target domain.

        Args:
            domain: Target domain to query anchor texts for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of anchor texts to return.

        Returns:
            List of AnchorCount objects sorted by count descending.
        """
        if snapshot_id:
            query = text("""
                SELECT
                    COALESCE(anchor, '') as anchor,
                    COUNT(*) as count
                FROM commoncrawl_edges
                WHERE target_domain = :domain
                  AND snapshot_id = :snapshot_id
                GROUP BY anchor
                ORDER BY count DESC
                LIMIT :limit
            """)
            params = {"domain": domain, "snapshot_id": snapshot_id, "limit": limit}
        else:
            query = text("""
                SELECT
                    COALESCE(anchor, '') as anchor,
                    COUNT(*) as count
                FROM commoncrawl_edges
                WHERE target_domain = :domain
                GROUP BY anchor
                ORDER BY count DESC
                LIMIT :limit
            """)
            params = {"domain": domain, "limit": limit}

        result = await self.session.execute(query, params)
        rows = result.fetchall()

        return [
            AnchorCount(
                anchor=row.anchor,
                count=row.count,
            )
            for row in rows
        ]
