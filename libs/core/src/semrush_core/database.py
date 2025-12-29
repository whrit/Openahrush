"""
Async SQLAlchemy database configuration and session management.

Provides:
- Async engine creation with connection pooling
- Async session factory for dependency injection
- Context manager for session handling
- Table creation utilities for testing/development
- Connection pool health monitoring

Connection Pool Configuration:
    The connection pool is configured via environment variables:
    - DATABASE_POOL_SIZE: Number of connections to keep open (default: 5)
    - DATABASE_MAX_OVERFLOW: Extra connections allowed above pool_size (default: 10)
    - DATABASE_POOL_TIMEOUT: Seconds to wait for a connection (default: 30)

    For asyncpg, the pool is managed by SQLAlchemy's QueuePool:
    - pool_pre_ping: Validates connections before use (enabled)
    - pool_recycle: Recreates connections after 1 hour (enabled)

    Recommended settings by workload:
    - Light: pool_size=5, max_overflow=5
    - Medium: pool_size=10, max_overflow=20
    - Heavy: pool_size=20, max_overflow=30 (requires DB connection limit increase)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from semrush_core.config import get_settings

# Module-level engine and session factory (lazy initialization)
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(
    *,
    database_url: str | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: int | None = None,
    echo: bool = False,
    use_null_pool: bool = False,
) -> AsyncEngine:
    """
    Create or retrieve the async SQLAlchemy engine.

    Args:
        database_url: Override database URL (defaults to settings)
        pool_size: Override connection pool size
        max_overflow: Override max overflow connections
        pool_timeout: Override pool timeout in seconds
        echo: Enable SQL logging
        use_null_pool: Use NullPool (for testing/single connections)

    Returns:
        AsyncEngine instance configured for the application.
    """
    global _engine

    if _engine is not None:
        return _engine

    settings = get_settings()

    url = database_url or settings.database_url
    pool_sz = pool_size if pool_size is not None else settings.database_pool_size
    overflow = max_overflow if max_overflow is not None else settings.database_max_overflow
    timeout = pool_timeout if pool_timeout is not None else settings.database_pool_timeout

    engine_kwargs: dict[str, Any] = {
        "echo": echo,
        "future": True,
    }

    if use_null_pool:
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs.update(
            {
                "pool_size": pool_sz,
                "max_overflow": overflow,
                "pool_timeout": timeout,
                "pool_pre_ping": True,  # Verify connections before use
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            }
        )

    _engine = create_async_engine(url, **engine_kwargs)
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """
    Create or retrieve the async session factory.

    Args:
        engine: Optional engine override (uses default if not provided)

    Returns:
        Async session factory for creating database sessions.
    """
    global _async_session_factory

    if _async_session_factory is not None and engine is None:
        return _async_session_factory

    eng = engine or get_engine()

    factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    if engine is None:
        _async_session_factory = factory

    return factory


# Convenience alias for the default session factory
AsyncSessionLocal = get_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection provider for async database sessions.

    Yields an async session and ensures proper cleanup. Use this with
    FastAPI's Depends() for automatic session management.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession instance for database operations.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database sessions.

    Use this for non-FastAPI contexts like background workers or scripts.

    Usage:
        async with get_session_context() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

    Yields:
        AsyncSession instance for database operations.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """
    Create all database tables defined in SQLAlchemy models.

    This should only be used for development/testing. Use Alembic
    migrations for production database management.

    Requires models to be imported before calling this function
    to register them with the metadata.
    """
    from semrush_core.models.base import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """
    Drop all database tables.

    WARNING: This permanently deletes all data. Only use in testing.
    """
    from semrush_core.models.base import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def dispose_engine() -> None:
    """
    Dispose of the database engine and close all connections.

    Call this during application shutdown to clean up resources.
    """
    global _engine, _async_session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


def reset_engine() -> None:
    """
    Reset the module-level engine and session factory.

    Use this in testing to ensure fresh connections between tests.
    Note: Call dispose_engine() first if the engine is active.
    """
    global _engine, _async_session_factory
    _engine = None
    _async_session_factory = None


def get_pool_status() -> dict[str, int | str]:
    """
    Get the current connection pool status.

    Returns connection pool metrics for monitoring and debugging.
    Returns empty dict if engine is not initialized or using NullPool.

    Returns:
        Dictionary with pool metrics:
        - pool_size: Configured pool size
        - checked_in: Number of connections available in pool
        - checked_out: Number of connections currently in use
        - overflow: Number of overflow connections currently active
        - total: Total connections (checked_in + checked_out)

    Example:
        >>> status = get_pool_status()
        >>> print(f"Connections in use: {status.get('checked_out', 0)}")
    """
    if _engine is None:
        return {"status": "not_initialized"}

    pool = _engine.pool

    # NullPool doesn't have these attributes
    if isinstance(pool, NullPool):
        return {"status": "null_pool"}

    # Check if pool has the status methods (QueuePool and similar)
    if hasattr(pool, "size") and hasattr(pool, "checkedin"):
        checked_in: int = pool.checkedin()  # type: ignore[attr-defined]
        checked_out: int = pool.checkedout()  # type: ignore[attr-defined]
        return {
            "status": "active",
            "pool_size": pool.size(),  # type: ignore[attr-defined]
            "checked_in": checked_in,
            "checked_out": checked_out,
            "overflow": pool.overflow(),  # type: ignore[attr-defined]
            "total": checked_in + checked_out,
        }

    return {"status": "unknown_pool_type"}


async def check_database_connection() -> bool:
    """
    Verify the database connection is working.

    Executes a simple query to check connectivity.
    Useful for health checks and startup verification.

    Returns:
        True if connection is successful, False otherwise.

    Example:
        if not await check_database_connection():
            logger.error("Database connection failed!")
            sys.exit(1)
    """
    try:
        from sqlalchemy import text

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
