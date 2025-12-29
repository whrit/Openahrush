"""
Batch read utilities for efficient database operations.

Provides functions to fetch records in batches to avoid:
- Large IN clauses that can overwhelm query planners
- Memory issues with loading too many records at once
- Connection timeouts for long-running queries

Usage:
    from semrush_core.db_utils.batch import batch_fetch

    # Fetch 1000 records in batches of 100
    records = await batch_fetch(
        session=db_session,
        model=Project,
        ids=project_ids,
        batch_size=100,
    )
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


async def batch_fetch[T](
    session: AsyncSession,
    model: type[T],
    ids: list[uuid.UUID],
    batch_size: int = 100,
    id_column: str = "id",
) -> list[T]:
    """
    Fetch records by IDs in batches to avoid large IN clauses.

    Large IN clauses can cause:
    - Query planner performance issues
    - Parameter limit errors (PostgreSQL has a limit of ~32K parameters)
    - Memory pressure on the database server

    This function splits the IDs into batches and executes multiple queries,
    then combines the results.

    Args:
        session: Async database session.
        model: SQLAlchemy model class.
        ids: List of UUIDs to fetch.
        batch_size: Maximum IDs per query (default: 100).
        id_column: Name of the ID column (default: "id").

    Returns:
        List of fetched records (order may not match input IDs).

    Example:
        projects = await batch_fetch(
            session=db,
            model=Project,
            ids=project_ids,
            batch_size=50,
        )
    """
    if not ids:
        return []

    results: list[T] = []
    id_col = getattr(model, id_column)

    # Process in batches
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        query = select(model).where(id_col.in_(batch_ids))
        result = await session.execute(query)
        results.extend(result.scalars().all())

    return results


async def batch_fetch_with_eager_load[T](
    session: AsyncSession,
    model: type[T],
    ids: list[uuid.UUID],
    relationships: list[str],
    batch_size: int = 100,
    id_column: str = "id",
) -> list[T]:
    """
    Fetch records by IDs in batches with eager loading of relationships.

    Combines batch fetching with eager loading to efficiently load
    records and their relationships without N+1 queries.

    Args:
        session: Async database session.
        model: SQLAlchemy model class.
        ids: List of UUIDs to fetch.
        relationships: List of relationship names to eager load.
        batch_size: Maximum IDs per query (default: 100).
        id_column: Name of the ID column (default: "id").

    Returns:
        List of fetched records with relationships loaded.

    Example:
        projects = await batch_fetch_with_eager_load(
            session=db,
            model=Project,
            ids=project_ids,
            relationships=["owner", "sites"],
        )
    """
    if not ids:
        return []

    results: list[T] = []
    id_col = getattr(model, id_column)

    # Build eager load options
    load_options = []
    for rel_name in relationships:
        if hasattr(model, rel_name):
            load_options.append(joinedload(getattr(model, rel_name)))

    # Process in batches
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        query = select(model).where(id_col.in_(batch_ids))

        if load_options:
            query = query.options(*load_options)

        result = await session.execute(query)
        results.extend(result.scalars().unique().all())

    return results


async def batch_fetch_ordered[T](
    session: AsyncSession,
    model: type[T],
    ids: list[uuid.UUID],
    batch_size: int = 100,
    id_column: str = "id",
) -> list[T]:
    """
    Fetch records by IDs in batches, preserving the order of input IDs.

    This is useful when the order of input IDs is meaningful (e.g., sorted
    by relevance) and needs to be preserved in the output.

    Args:
        session: Async database session.
        model: SQLAlchemy model class.
        ids: List of UUIDs to fetch (order will be preserved).
        batch_size: Maximum IDs per query (default: 100).
        id_column: Name of the ID column (default: "id").

    Returns:
        List of fetched records in the same order as input IDs.
        Missing records are silently omitted.

    Example:
        # IDs ordered by search relevance
        projects = await batch_fetch_ordered(
            session=db,
            model=Project,
            ids=ranked_project_ids,
        )
    """
    if not ids:
        return []

    # Fetch all records (unordered)
    all_records = await batch_fetch(
        session=session,
        model=model,
        ids=ids,
        batch_size=batch_size,
        id_column=id_column,
    )

    # Build a lookup dictionary
    id_to_record: dict[uuid.UUID, T] = {}
    for record in all_records:
        record_id = getattr(record, id_column)
        id_to_record[record_id] = record

    # Return records in the original order
    ordered_results: list[T] = []
    for id_ in ids:
        if id_ in id_to_record:
            ordered_results.append(id_to_record[id_])

    return ordered_results


async def batch_exists(
    session: AsyncSession,
    model: type[Any],
    ids: list[uuid.UUID],
    batch_size: int = 100,
    id_column: str = "id",
) -> set[uuid.UUID]:
    """
    Check which IDs exist in the database.

    Useful for validating lists of IDs before performing operations
    that require all IDs to be valid.

    Args:
        session: Async database session.
        model: SQLAlchemy model class.
        ids: List of UUIDs to check.
        batch_size: Maximum IDs per query (default: 100).
        id_column: Name of the ID column (default: "id").

    Returns:
        Set of IDs that exist in the database.

    Example:
        existing_ids = await batch_exists(
            session=db,
            model=Project,
            ids=requested_ids,
        )
        missing_ids = set(requested_ids) - existing_ids
    """
    if not ids:
        return set()

    existing: set[uuid.UUID] = set()
    id_col = getattr(model, id_column)

    # Only select the ID column for efficiency
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        query = select(id_col).where(id_col.in_(batch_ids))
        result = await session.execute(query)
        existing.update(result.scalars().all())

    return existing


async def batch_delete(
    session: AsyncSession,
    model: type[Any],
    ids: list[uuid.UUID],
    batch_size: int = 100,
    id_column: str = "id",
) -> int:
    """
    Delete records by IDs in batches.

    Args:
        session: Async database session.
        model: SQLAlchemy model class.
        ids: List of UUIDs to delete.
        batch_size: Maximum IDs per query (default: 100).
        id_column: Name of the ID column (default: "id").

    Returns:
        Total number of records deleted.

    Example:
        deleted_count = await batch_delete(
            session=db,
            model=OldCrawlRun,
            ids=expired_crawl_ids,
        )
    """
    if not ids:
        return 0

    from sqlalchemy import delete

    total_deleted = 0
    id_col = getattr(model, id_column)

    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        stmt = delete(model).where(id_col.in_(batch_ids))
        result = await session.execute(stmt)
        # rowcount is available on CursorResult from delete operations
        total_deleted += result.rowcount  # type: ignore[attr-defined]

    return total_deleted
