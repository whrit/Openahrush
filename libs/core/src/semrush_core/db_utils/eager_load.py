"""
Eager loading utilities for preventing N+1 queries.

Provides helper functions to add eager loading options to SQLAlchemy queries,
making it easy to load related objects in a single query instead of making
separate queries for each relationship.

Usage:
    from semrush_core.db_utils.eager_load import with_eager_loads, with_selectin_loads

    # Using joinedload (single query with JOIN)
    query = with_eager_loads(select(Project), "sites", "settings")

    # Using selectinload (separate IN query, better for one-to-many)
    query = with_selectin_loads(select(Project), "sites", "crawl_runs")
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import (
    InstrumentedAttribute,
    joinedload,
    selectinload,
)
from sqlalchemy.orm.strategy_options import _AbstractLoad


def with_eager_loads[T](query: Select[tuple[T]], *relationships: str) -> Select[tuple[T]]:
    """
    Add joinedload options for specified relationships.

    joinedload performs a LEFT OUTER JOIN to load related objects in the
    same query. This is efficient for one-to-one and many-to-one relationships.

    For one-to-many relationships, consider using with_selectin_loads() instead
    to avoid Cartesian product issues.

    Args:
        query: SQLAlchemy Select query.
        *relationships: Names of relationships to eagerly load.

    Returns:
        Query with joinedload options applied.

    Example:
        query = with_eager_loads(
            select(Project),
            "owner",      # Many-to-one: load owner in same query
            "settings",   # One-to-one: load settings in same query
        )
    """
    if not relationships:
        return query

    # Get the entity from the query
    entity = _get_query_entity(query)
    if entity is None:
        return query

    options = build_eager_load_options(entity, list(relationships))
    if options:
        return query.options(*options)
    return query


def with_selectin_loads[T](query: Select[tuple[T]], *relationships: str) -> Select[tuple[T]]:
    """
    Add selectinload options for specified relationships.

    selectinload performs a separate SELECT ... WHERE id IN (...) query
    to load related objects. This is more efficient for one-to-many
    relationships as it avoids the Cartesian product problem.

    Args:
        query: SQLAlchemy Select query.
        *relationships: Names of relationships to eagerly load.

    Returns:
        Query with selectinload options applied.

    Example:
        query = with_selectin_loads(
            select(Project),
            "sites",       # One-to-many: separate query for sites
            "crawl_runs",  # One-to-many: separate query for crawl_runs
        )
    """
    if not relationships:
        return query

    entity = _get_query_entity(query)
    if entity is None:
        return query

    options = build_selectin_load_options(entity, list(relationships))
    if options:
        return query.options(*options)
    return query


def build_eager_load_options(
    model: type[Any],
    relationships: list[str],
) -> list[_AbstractLoad]:
    """
    Build joinedload options for a model's relationships.

    Args:
        model: SQLAlchemy model class.
        relationships: List of relationship names to eagerly load.

    Returns:
        List of joinedload options.
    """
    options: list[_AbstractLoad] = []
    for rel_name in relationships:
        if hasattr(model, rel_name):
            attr = getattr(model, rel_name)
            if isinstance(attr, InstrumentedAttribute):
                options.append(joinedload(attr))
    return options


def build_selectin_load_options(
    model: type[Any],
    relationships: list[str],
) -> list[_AbstractLoad]:
    """
    Build selectinload options for a model's relationships.

    Args:
        model: SQLAlchemy model class.
        relationships: List of relationship names to load via SELECT IN.

    Returns:
        List of selectinload options.
    """
    options: list[_AbstractLoad] = []
    for rel_name in relationships:
        if hasattr(model, rel_name):
            attr = getattr(model, rel_name)
            if isinstance(attr, InstrumentedAttribute):
                options.append(selectinload(attr))
    return options


def _get_query_entity(query: Select[Any]) -> type[Any] | None:
    """
    Extract the primary entity from a Select query.

    Args:
        query: SQLAlchemy Select query.

    Returns:
        Model class, or None if not found.
    """
    # Try to get from froms
    froms = query.froms
    if froms:
        first_from = froms[0]
        if hasattr(first_from, "entity_namespace"):
            entity_ns = first_from.entity_namespace
            if isinstance(entity_ns, type):
                return entity_ns

    # Try to get from selected columns
    try:
        selected = query.selected_columns
        if selected:
            for col in selected:
                if hasattr(col, "entity_namespace"):
                    entity_ns = col.entity_namespace
                    if isinstance(entity_ns, type):
                        return entity_ns
    except Exception:
        pass

    return None


# Utility for nested eager loading
def with_nested_eager_load[T](
    query: Select[tuple[T]],
    path: str,
    use_selectin: bool = False,
) -> Select[tuple[T]]:
    """
    Add eager loading for a nested relationship path.

    Args:
        query: SQLAlchemy Select query.
        path: Dot-separated relationship path (e.g., "project.sites.crawl_runs").
        use_selectin: If True, use selectinload; otherwise use joinedload.

    Returns:
        Query with nested eager loading applied.

    Example:
        query = with_nested_eager_load(
            select(CrawlRun),
            "project.sites",
            use_selectin=True,
        )
    """
    entity = _get_query_entity(query)
    if entity is None:
        return query

    parts = path.split(".")
    if not parts:
        return query

    load_func = selectinload if use_selectin else joinedload

    # Build the nested loader
    current_entity = entity
    current_loader: Any = None

    for _i, rel_name in enumerate(parts):
        if not hasattr(current_entity, rel_name):
            break

        attr = getattr(current_entity, rel_name)
        if not isinstance(attr, InstrumentedAttribute):
            break

        if current_loader is None:
            current_loader = load_func(attr)
        else:
            # Chain the loaders for nested relationships
            current_loader = current_loader.options(load_func(attr))

        # Get the related entity for the next iteration
        if hasattr(attr.property, "mapper"):
            current_entity = attr.property.mapper.class_

    if current_loader is not None:
        return query.options(current_loader)

    return query
