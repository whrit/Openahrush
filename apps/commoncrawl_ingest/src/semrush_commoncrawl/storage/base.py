"""
Storage adapter base classes and protocols.

Defines the EdgeStorage protocol for Common Crawl edge storage,
allowing switching between Postgres (MVP) and ClickHouse (scale).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class Edge:
    """
    Represents a link edge from Common Crawl data.

    An edge is a directed link from a source URL to a target URL,
    discovered in a specific Common Crawl snapshot.

    Attributes:
        snapshot_id: Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10').
        source_url: Full URL of the linking page.
        source_domain: Domain of the linking page.
        target_url: Full URL of the linked page.
        target_domain: Domain of the linked page.
        anchor: Anchor text of the link (may be None for image links).
        rel_flags: List of rel attribute values (nofollow, ugc, sponsored, etc.).
    """

    snapshot_id: str
    source_url: str
    source_domain: str
    target_url: str
    target_domain: str
    anchor: str | None = None
    rel_flags: list[str] | None = None


@dataclass
class RefDomain:
    """
    Represents a referring domain aggregate.

    Aggregates backlink counts from a single source domain
    to a target domain.

    Attributes:
        source_domain: Domain that links to the target.
        backlink_count: Total number of backlinks from this domain.
        first_seen: Earliest date this referring domain was discovered.
        last_seen: Most recent date this referring domain was seen.
    """

    source_domain: str
    backlink_count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None


@dataclass
class Backlink:
    """
    Represents a single backlink.

    Contains detailed information about an individual link
    from a source page to a target page.

    Attributes:
        source_url: Full URL of the linking page.
        source_domain: Domain of the linking page.
        target_url: Full URL of the linked page.
        target_domain: Domain of the linked page.
        anchor: Anchor text of the link.
        rel_flags: List of rel attribute values.
    """

    source_url: str
    source_domain: str
    target_url: str
    target_domain: str
    anchor: str | None = None
    rel_flags: list[str] | None = None


@dataclass
class AnchorCount:
    """
    Represents an anchor text with its occurrence count.

    Aggregates how many times a specific anchor text
    is used in links to a target domain.

    Attributes:
        anchor: The anchor text (may be empty for image links).
        count: Number of occurrences of this anchor text.
    """

    anchor: str
    count: int


@runtime_checkable
class EdgeStorage(Protocol):
    """
    Protocol for Common Crawl edge storage.

    Defines the interface for storing and querying link edges
    discovered from Common Crawl data. Implementations can use
    different storage backends (Postgres, ClickHouse) while
    maintaining a consistent API.

    Methods:
        insert_edges: Batch insert edges from Common Crawl processing.
        query_refdomains: Query referring domains for a target domain.
        query_backlinks: Query individual backlinks with pagination.
        query_anchors: Query anchor text aggregates for a domain.
    """

    async def insert_edges(self, edges: list[Edge]) -> int:
        """
        Insert a batch of edges into storage.

        Args:
            edges: List of Edge objects to insert.

        Returns:
            Number of edges successfully inserted.
        """
        ...

    async def query_refdomains(
        self,
        domain: str,
        snapshot_id: str | None = None,
        limit: int = 100,
    ) -> list[RefDomain]:
        """
        Query referring domains for a target domain.

        Args:
            domain: Target domain to query backlinks for.
            snapshot_id: Optional filter for specific Common Crawl snapshot.
            limit: Maximum number of referring domains to return.

        Returns:
            List of RefDomain objects sorted by backlink_count descending.
        """
        ...

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
        ...

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
        ...
