# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Openahrush is an open-source, self-hostable SEO platform with a Python control plane and Rust data plane. It provides Semrush/Ahrefs-like "Projects" workflows including site audits, search console integrations, and backlink analysis via Common Crawl ingestion.

## Development Commands

```bash
# Install dependencies
uv sync

# Run API server
uv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000

# Run all tests with coverage
scripts/test.sh

# Run specific test file
uv run pytest apps/api/tests/test_auth.py -v

# Run tests matching pattern
uv run pytest -k "test_login" -v

# Run tests and stop on first failure
uv run pytest -x

# Format + lint + types
scripts/lint.sh

# Fix formatting issues
uv run ruff format .

# Docker dev stack
scripts/dev.sh up          # Start (API, Postgres, Redis, MinIO)
scripts/dev.sh down         # Stop
scripts/dev.sh up-clickhouse  # Start with ClickHouse

# Database migrations
export DATABASE_URL="postgresql+psycopg://semrush:semrush@localhost:5432/semrush"
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head
uv run --package semrush-core alembic -c migrations/alembic.ini revision --autogenerate -m "description"
```

## Architecture

### Two-Plane Design
- **Control plane (Python):** FastAPI API, OAuth integrations, background workers, PDF reports, Common Crawl ingest
- **Data plane (Rust):** High-throughput crawler with frontier scheduling (crates/crawler - not yet implemented)

### Workspace Packages (uv monorepo)
```
libs/
  core/         # semrush-core: Config, database, models, security (JWT, encryption)
  seo/          # semrush-seo: URL normalization, robots.txt parsing, sitemap parsing, HTML extraction
  backlinks/    # semrush-backlinks: Backlink processing

apps/
  api/          # semrush-api: FastAPI routers, auth, projects, integrations, issues, alerts
  workers/      # semrush-workers: Crawl orchestration, rules engine, alert processing
  integrations/ # semrush-integrations: OAuth (Google/Microsoft), GSC/GA4/BWT adapters, data sync
  reports/      # PDF/CSV export rendering
  commoncrawl_ingest/  # Common Crawl pipeline
```

### Key Patterns

**Database Models** (libs/core/src/semrush_core/models/):
- All models use SQLAlchemy 2.0 async with `Mapped[]` type hints
- Common mixins: `id` (UUID), `created_at`, `updated_at`
- Fact tables for analytics: `SearchFact`, `AnalyticsFact`, `LinkFact`

**OAuth Flow** (apps/integrations/):
- Base class in `oauth/base.py` with provider-specific implementations
- State management via `libs/core/src/semrush_core/oauth/state.py`
- Token encryption using Fernet (libs/core/src/semrush_core/security/encryption.py)

**API Structure** (apps/api/src/semrush_api/routers/):
- Each router is a separate module (auth.py, projects.py, integrations.py, etc.)
- Uses FastAPI dependency injection for db sessions and auth
- JWT auth via `semrush_core.security.jwt`

**Testing**:
- Tests co-located with packages: `apps/*/tests/`, `libs/*/tests/`
- Async fixtures in `conftest.py` files
- Mock db sessions for API tests, no real database required
- pytest-asyncio with `asyncio_mode = "auto"`

### Storage Systems
- **Postgres:** System of record (users, projects, crawls, issues, integrations)
- **Redis:** Work queue + distributed locks
- **MinIO/S3:** HTML artifacts, exports
- **ClickHouse (optional):** Common Crawl edge storage at scale

## Code Style

- **Python:** 3.12 required
- **Ruff:** Line length 100, double quotes, rules E/F/I/B/UP/SIM/RUF
- **MyPy:** `no_implicit_optional`, `check_untyped_defs`

## Environment Variables

```bash
DATABASE_URL          # Postgres DSN (postgresql+asyncpg://...)
REDIS_URL             # Redis DSN
JWT_SECRET            # JWT signing key (min 32 chars)
MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/S3_BUCKET  # Object storage
CLICKHOUSE_URL/DATABASE  # Optional Common Crawl storage
GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI  # OAuth
```

## Key Documentation

- `ARCHITECTURE.md` - Services, data flows, event schemas
- `BLUEPRINT-PRD-MVP.md` - Product requirements and feature specs
- `COMMONCRAWL_INGESTION.md` - Common Crawl pipeline design
- `openapi.yaml` - API specification
