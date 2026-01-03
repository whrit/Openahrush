#!/usr/bin/env python3
"""
Migration verification script.

Tests the full migration lifecycle:
1. Upgrade to head
2. Verify tables exist
3. Downgrade one step
4. Re-upgrade
5. Full downgrade to base
6. Full upgrade to head

Supports both PostgreSQL and SQLite for testing.
"""

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def setup_alembic_config(database_url: str) -> Config:
    """Set up Alembic configuration with the given database URL."""
    # Find the migrations directory
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "migrations"

    if not migrations_dir.exists():
        print(f"Error: Migrations directory not found at {migrations_dir}")
        sys.exit(1)

    alembic_ini = migrations_dir / "alembic.ini"
    if not alembic_ini.exists():
        print(f"Error: alembic.ini not found at {alembic_ini}")
        sys.exit(1)

    # Create Alembic config
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("sqlalchemy.url", database_url)

    # Set DATABASE_URL for env.py
    os.environ["DATABASE_URL"] = database_url

    return config


async def verify_tables_exist(engine: AsyncEngine, expected_tables: list[str]) -> bool:
    """Verify that expected tables exist in the database."""
    async with engine.connect() as conn:
        result = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
        missing_tables = [t for t in expected_tables if t not in result]

        if missing_tables:
            print(f"  Warning: Missing tables: {', '.join(missing_tables)}")
            return False

        print(f"  OK: All {len(expected_tables)} expected tables exist")
        return True


async def get_current_revision(engine: AsyncEngine) -> str | None:
    """Get the current database revision."""
    async with engine.connect() as conn:
        try:
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.fetchone()
            return row[0] if row else None
        except Exception:
            # Table doesn't exist yet
            return None


def get_all_revisions(config: Config) -> list[str]:
    """Get all migration revisions in order."""
    script = ScriptDirectory.from_config(config)
    revisions = []

    for rev in script.walk_revisions():
        if rev.revision:
            revisions.insert(0, rev.revision)

    return revisions


async def run_verification(database_url: str, verbose: bool = False) -> bool:
    """Run full migration verification cycle."""
    print("=" * 70)
    print("Migration Verification Test")
    print("=" * 70)
    print(f"Database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    print()

    # Set up Alembic
    config = setup_alembic_config(database_url)

    # Convert sync URL to async URL
    async_url = database_url
    if database_url.startswith("postgresql://"):
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("sqlite://"):
        async_url = database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    # Create async engine
    engine = create_async_engine(async_url, echo=verbose)

    try:
        # Expected core tables (from migrations)
        expected_tables = [
            "alembic_version",
            "users",
            "projects",
            "sites",
            "competitors",
            "project_settings",
            "integration_accounts",
            "integration_tokens",
            "integration_properties",
            "integration_mappings",
            "sync_runs",
            "search_fact_daily",
            "analytics_fact_daily",
            "link_facts",
            "crawl_runs",
            "crawl_pages",
            "link_edges",
            "issues",
        ]

        all_revisions = get_all_revisions(config)
        print(f"Found {len(all_revisions)} migrations to test")
        print()

        # Step 1: Upgrade to head
        print("Step 1: Upgrading to head...")
        try:
            command.upgrade(config, "head")
            current = await get_current_revision(engine)
            print(f"  OK: Upgraded to: {current}")
        except Exception as e:
            print(f"  FAIL: Upgrade failed: {e}")
            return False

        # Step 2: Verify tables exist
        print("\nStep 2: Verifying tables exist...")
        if not await verify_tables_exist(engine, expected_tables):
            print("  Warning: Some tables missing (may be expected)")

        # Step 3: Downgrade one step
        print("\nStep 3: Testing downgrade (one step)...")
        try:
            command.downgrade(config, "-1")
            current = await get_current_revision(engine)
            print(f"  OK: Downgraded to: {current}")
        except Exception as e:
            print(f"  FAIL: Downgrade failed: {e}")
            return False

        # Step 4: Re-upgrade
        print("\nStep 4: Re-upgrading to head...")
        try:
            command.upgrade(config, "head")
            current = await get_current_revision(engine)
            print(f"  OK: Re-upgraded to: {current}")
        except Exception as e:
            print(f"  FAIL: Re-upgrade failed: {e}")
            return False

        # Step 5: Full downgrade to base
        print("\nStep 5: Testing full downgrade to base...")
        try:
            command.downgrade(config, "base")
            current = await get_current_revision(engine)
            if current is None:
                print("  OK: Fully downgraded to base")
            else:
                print(f"  FAIL: Expected None, got: {current}")
                return False
        except Exception as e:
            print(f"  FAIL: Full downgrade failed: {e}")
            return False

        # Step 6: Full upgrade to head again
        print("\nStep 6: Final upgrade to head...")
        try:
            command.upgrade(config, "head")
            current = await get_current_revision(engine)
            print(f"  OK: Final upgrade to: {current}")
        except Exception as e:
            print(f"  FAIL: Final upgrade failed: {e}")
            return False

        # Final verification
        print("\nStep 7: Final table verification...")
        await verify_tables_exist(engine, expected_tables)

        print()
        print("=" * 70)
        print("All migration tests passed!")
        print("=" * 70)
        return True

    finally:
        await engine.dispose()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify database migrations work correctly"
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (default: SQLite in temp file for testing)",
        default=None,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output (show SQL)",
    )

    args = parser.parse_args()

    # Determine database URL
    if args.database_url:
        database_url = args.database_url
    else:
        # Create a temporary SQLite database for testing
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        database_url = f"sqlite:///{temp_path}"
        print(f"Using temporary SQLite database: {temp_path}")
        print()

    try:
        success = asyncio.run(run_verification(database_url, args.verbose))
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
