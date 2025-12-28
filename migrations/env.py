"""
Alembic environment configuration for async migrations.

This file configures Alembic to use:
- Async SQLAlchemy engine with asyncpg
- Database URL from environment variable
- All models from semrush_core.models for autogenerate support
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base metadata and all models for autogenerate
from semrush_core.models import Base
from semrush_core.models import (  # noqa: F401 - imports needed for autogenerate
    # Core models
    AnalyticsFactDaily,
    Competitor,
    IntegrationAccount,
    IntegrationMapping,
    IntegrationProperty,
    IntegrationToken,
    LinkFact,
    Project,
    ProjectSettings,
    SearchFactDaily,
    Site,
    SyncRun,
    User,
)

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Get database URL from environment.

    Falls back to a development default if not set.
    Converts postgresql:// to postgresql+asyncpg:// for async support.
    """
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://semrush:semrush@localhost:5432/semrush",
    )

    # Ensure we're using asyncpg driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in async mode.

    Creates an async engine and runs migrations within a connection.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an async engine and associated connection for running migrations.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
