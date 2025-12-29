"""
ClickHouse storage adapter stub for Common Crawl edges.

Placeholder implementation for future scale deployment.
All methods raise NotImplementedError.
"""

from __future__ import annotations

from semrush_commoncrawl.storage.base import (
    AnchorCount,
    Backlink,
    Edge,
    RefDomain,
)


class ClickHouseStorage:
    """
    ClickHouse implementation of EdgeStorage (stub).

    This is a placeholder for future scale implementation.
    ClickHouse will provide better performance for large-scale
    Common Crawl data with columnar storage and efficient aggregations.

    All methods raise NotImplementedError until implementation is complete.
    """

    def __init__(self) -> None:
        """Initialize ClickHouseStorage."""
        pass

    async def insert_edges(self, edges: list[Edge]) -> int:
        """
        Insert edges into ClickHouse (not implemented).

        Args:
            edges: List of Edge objects to insert.

        Raises:
            NotImplementedError: ClickHouse storage not yet implemented.
        """
        raise NotImplementedError("ClickHouse storage not implemented")

    async def query_refdomains(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
    ) -> list[RefDomain]:
        """
        Query referring domains from ClickHouse (not implemented).

        Args:
            domain: Target domain to query backlinks for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of referring domains to return.

        Raises:
            NotImplementedError: ClickHouse storage not yet implemented.
        """
        raise NotImplementedError("ClickHouse storage not implemented")

    async def query_backlinks(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Backlink]:
        """
        Query backlinks from ClickHouse (not implemented).

        Args:
            domain: Target domain to query backlinks for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of backlinks to return.
            offset: Number of backlinks to skip (for pagination).

        Raises:
            NotImplementedError: ClickHouse storage not yet implemented.
        """
        raise NotImplementedError("ClickHouse storage not implemented")

    async def query_anchors(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
    ) -> list[AnchorCount]:
        """
        Query anchor text aggregates from ClickHouse (not implemented).

        Args:
            domain: Target domain to query anchor texts for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of anchor texts to return.

        Raises:
            NotImplementedError: ClickHouse storage not yet implemented.
        """
        raise NotImplementedError("ClickHouse storage not implemented")
