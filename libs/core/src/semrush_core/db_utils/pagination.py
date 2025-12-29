"""
Keyset (cursor-based) pagination utilities for efficient large dataset handling.

Keyset pagination is more efficient than OFFSET/LIMIT for large datasets because:
- It doesn't require counting all previous rows
- Performance is consistent regardless of page number
- It handles concurrent inserts/deletes correctly

Usage:
    paginator = KeysetPaginator()
    result = await paginator.paginate(
        session=db_session,
        query=select(Project),
        order_by_columns=["created_at", "id"],
        cursor=request.cursor,
        limit=20,
    )
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, asc, desc, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute


@dataclass
class PaginatedResult[T]:
    """
    Result container for paginated queries.

    Attributes:
        items: List of items for the current page.
        next_cursor: Opaque cursor for fetching the next page, or None if no more pages.
        has_more: Whether there are more items after this page.
    """

    items: list[T]
    next_cursor: str | None
    has_more: bool

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for API responses.

        Note: Items are not serialized - caller should handle that.
        """
        return {
            "items": self.items,
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
        }


class KeysetPaginator:
    """
    Cursor-based pagination implementation using keyset pagination.

    Keyset pagination uses the values from the last row of the previous page
    to efficiently fetch the next page. This is more efficient than OFFSET
    for large datasets.

    The cursor is a base64-encoded JSON object containing the ordering column
    values from the last item of the previous page.
    """

    def encode_cursor(self, values: dict[str, Any]) -> str:
        """
        Encode cursor values as a URL-safe string.

        Args:
            values: Dictionary of column names to their values from the last row.

        Returns:
            Base64-encoded JSON string.
        """
        # Convert non-serializable types to strings
        serializable = {}
        for key, value in values.items():
            if isinstance(value, uuid.UUID):
                serializable[key] = str(value)
            elif isinstance(value, datetime):
                serializable[key] = value.isoformat()
            else:
                serializable[key] = value

        json_str = json.dumps(serializable, separators=(",", ":"))
        return base64.urlsafe_b64encode(json_str.encode()).decode()

    def decode_cursor(self, cursor: str | None) -> dict[str, Any] | None:
        """
        Decode a cursor string back to column values.

        Args:
            cursor: Base64-encoded cursor string, or None.

        Returns:
            Dictionary of column values, or None if cursor is empty.

        Raises:
            ValueError: If cursor is invalid.
        """
        if not cursor:
            return None

        try:
            json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid cursor: {e}") from e

    def build_cursor_filter(
        self,
        cursor_values: dict[str, Any],
        columns: dict[str, InstrumentedAttribute[Any]],
        descending: bool = False,
    ) -> Any:
        """
        Build a WHERE clause for cursor-based filtering.

        For multiple columns, this creates a compound comparison using tuple
        comparison semantics: (col1, col2) > (val1, val2).

        Args:
            cursor_values: Values from the decoded cursor.
            columns: Mapping of column names to SQLAlchemy column objects.
            descending: If True, filter for values less than cursor (for DESC order).

        Returns:
            SQLAlchemy filter clause.
        """
        if len(columns) == 1:
            # Simple single-column case
            col_name = next(iter(columns.keys()))
            col = columns[col_name]
            value = cursor_values.get(col_name)

            if descending:
                return col < value
            return col > value

        # Multi-column keyset comparison using tuple comparison
        # This handles (col1, col2) > (val1, val2) correctly
        col_list = [columns[name] for name in columns]
        val_list: list[Any] = [cursor_values.get(name) for name in columns]

        if descending:
            return tuple_(*col_list) < tuple_(*val_list)  # type: ignore[arg-type]
        return tuple_(*col_list) > tuple_(*val_list)  # type: ignore[arg-type]

    async def paginate[T](
        self,
        session: AsyncSession,
        query: Select[tuple[T]],
        order_by_columns: list[str],
        cursor: str | None = None,
        limit: int = 20,
        descending: bool = False,
        model: type[Any] | None = None,
    ) -> PaginatedResult[T]:
        """
        Execute a paginated query using keyset pagination.

        Args:
            session: Async database session.
            query: Base SQLAlchemy select query (without ORDER BY or LIMIT).
            order_by_columns: Column names to order by (e.g., ["created_at", "id"]).
            cursor: Cursor string from previous page, or None for first page.
            limit: Maximum items per page.
            descending: If True, order descending instead of ascending.
            model: Optional model class to extract columns from. If not provided,
                   columns are extracted from the query's selected entity.

        Returns:
            PaginatedResult with items, next_cursor, and has_more flag.
        """
        # Extract model from query if not provided
        if model is None:
            # Get the first entity from the query's column descriptions
            froms = query.froms
            if froms:
                entity_ns = froms[0].entity_namespace
                if isinstance(entity_ns, type):
                    model = entity_ns
            else:
                # Try to get from selected columns
                selected = query.selected_columns
                if selected:
                    first_col = next(iter(selected))
                    if hasattr(first_col, "entity_namespace"):
                        entity_ns = first_col.entity_namespace
                        if isinstance(entity_ns, type):
                            model = entity_ns

        # Build column mapping for cursor operations
        columns: dict[str, InstrumentedAttribute[Any]] = {}
        if model is not None:
            for col_name in order_by_columns:
                if hasattr(model, col_name):
                    columns[col_name] = getattr(model, col_name)

        # Apply cursor filter if provided
        if cursor:
            cursor_values = self.decode_cursor(cursor)
            if cursor_values and columns:
                filter_clause = self.build_cursor_filter(
                    cursor_values=cursor_values,
                    columns=columns,
                    descending=descending,
                )
                query = query.where(filter_clause)

        # Apply ordering
        order_func = desc if descending else asc
        for col_name in order_by_columns:
            if col_name in columns:
                query = query.order_by(order_func(columns[col_name]))

        # Fetch limit + 1 to determine if there are more items
        query = query.limit(limit + 1)

        # Execute query
        result = await session.execute(query)
        items = list(result.scalars().all())

        # Determine if there are more items
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]  # Remove the extra item

        # Generate next cursor from last item
        next_cursor: str | None = None
        if has_more and items:
            last_item = items[-1]
            cursor_values = {}
            for col_name in order_by_columns:
                if hasattr(last_item, col_name):
                    cursor_values[col_name] = getattr(last_item, col_name)
            next_cursor = self.encode_cursor(cursor_values)

        return PaginatedResult(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        )


# Convenience function for common use case
async def paginate_query[T](
    session: AsyncSession,
    query: Select[tuple[T]],
    cursor: str | None = None,
    limit: int = 20,
    order_by: list[str] | None = None,
    descending: bool = False,
) -> PaginatedResult[T]:
    """
    Convenience function for keyset pagination.

    Args:
        session: Async database session.
        query: Base SQLAlchemy select query.
        cursor: Cursor from previous page, or None.
        limit: Items per page.
        order_by: Column names for ordering. Defaults to ["created_at", "id"].
        descending: Order direction.

    Returns:
        PaginatedResult with paginated items.
    """
    paginator = KeysetPaginator()
    return await paginator.paginate(
        session=session,
        query=query,
        order_by_columns=order_by or ["created_at", "id"],
        cursor=cursor,
        limit=limit,
        descending=descending,
    )
