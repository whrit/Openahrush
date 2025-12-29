"""
Storage adapters for Common Crawl edge data.

Provides abstraction layer for storing and querying backlink data,
allowing switching between Postgres (MVP) and ClickHouse (scale).

Usage:
    from semrush_commoncrawl.storage import get_storage, EdgeStorage

    # Create Postgres storage
    storage = get_storage("postgres", session=db_session)

    # Insert edges
    count = await storage.insert_edges(edges)

    # Query referring domains
    refdomains = await storage.query_refdomains("example.com")

    # Query backlinks with pagination
    backlinks = await storage.query_backlinks("example.com", limit=50, offset=0)

    # Query anchor text distribution
    anchors = await storage.query_anchors("example.com")
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from semrush_commoncrawl.storage.base import (
    AnchorCount,
    Backlink,
    Edge,
    EdgeStorage,
    RefDomain,
)
from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage
from semrush_commoncrawl.storage.postgres import PostgresStorage

__all__ = [
    "AnchorCount",
    "Backlink",
    "ClickHouseStorage",
    "Edge",
    "EdgeStorage",
    "get_storage",
    "PostgresStorage",
    "RefDomain",
]


def get_storage(
    storage_type: str,
    *,
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> PostgresStorage | ClickHouseStorage:
    """
    Factory function to create storage adapters.

    Creates the appropriate storage implementation based on type.

    Args:
        storage_type: Type of storage ('postgres' or 'clickhouse').
        session: SQLAlchemy async session (required for postgres).
        **kwargs: Additional arguments passed to storage constructor.

    Returns:
        Storage adapter instance.

    Raises:
        ValueError: If storage_type is not recognized.
        ValueError: If required arguments are missing.

    Examples:
        >>> storage = get_storage("postgres", session=db_session)
        >>> storage = get_storage("clickhouse")
    """
    if storage_type == "postgres":
        if session is None:
            raise ValueError("PostgresStorage requires a session argument")
        return PostgresStorage(session=session)
    elif storage_type == "clickhouse":
        return ClickHouseStorage()
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
