"""
Database optimization utilities for Openahrush.

This module provides utilities for efficient database operations:

- **Pagination**: Keyset (cursor-based) pagination for efficient large dataset handling
- **Eager Loading**: Helpers for preventing N+1 queries
- **Batch Operations**: Utilities for batching large read operations
- **Query Logging**: Development-mode query logging and slow query detection

Usage Examples:

    # Keyset pagination
    from semrush_core.db_utils import KeysetPaginator, paginate_query

    paginator = KeysetPaginator()
    result = await paginator.paginate(
        session=db,
        query=select(Project),
        order_by_columns=["created_at", "id"],
        cursor=request.cursor,
        limit=20,
    )

    # Eager loading
    from semrush_core.db_utils import with_eager_loads, with_selectin_loads

    query = with_eager_loads(select(Project), "owner", "settings")
    query = with_selectin_loads(query, "sites")

    # Batch fetching
    from semrush_core.db_utils import batch_fetch

    projects = await batch_fetch(
        session=db,
        model=Project,
        ids=project_ids,
        batch_size=100,
    )

    # Query logging
    from semrush_core.db_utils import QueryLogger, create_query_logger

    logger = create_query_logger()
    async with logger.timed_query("SELECT * FROM users"):
        result = await session.execute(query)
"""

from semrush_core.db_utils.batch import (
    batch_delete,
    batch_exists,
    batch_fetch,
    batch_fetch_ordered,
    batch_fetch_with_eager_load,
)
from semrush_core.db_utils.eager_load import (
    build_eager_load_options,
    build_selectin_load_options,
    with_eager_loads,
    with_nested_eager_load,
    with_selectin_loads,
)
from semrush_core.db_utils.pagination import (
    KeysetPaginator,
    PaginatedResult,
    paginate_query,
)
from semrush_core.db_utils.query_log import (
    N1QueryDetector,
    QueryLogger,
    QueryStats,
    SlowQueryDetector,
    create_query_logger,
    normalize_query_pattern,
    setup_query_logging,
)

__all__ = [
    # Pagination
    "KeysetPaginator",
    "PaginatedResult",
    "paginate_query",
    # Eager loading
    "with_eager_loads",
    "with_selectin_loads",
    "build_eager_load_options",
    "build_selectin_load_options",
    "with_nested_eager_load",
    # Batch operations
    "batch_fetch",
    "batch_fetch_with_eager_load",
    "batch_fetch_ordered",
    "batch_exists",
    "batch_delete",
    # Query logging
    "QueryLogger",
    "SlowQueryDetector",
    "N1QueryDetector",
    "QueryStats",
    "create_query_logger",
    "normalize_query_pattern",
    "setup_query_logging",
]
