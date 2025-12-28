# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Openahrush is an open-source, self-hostable SEO platform with a Python control plane and Rust data plane. It provides Semrush/Ahrefs-like "Projects" workflows including site audits, search console integrations, and backlink analysis via Common Crawl ingestion.

**Status:** MVP scaffolding phase. The pyproject.toml declares the workspace structure, but implementation code in apps/, libs/, and crates/ has not yet been created.

## Development Commands

```bash
# Install dependencies (workspace)
uv sync

# Run API server (when implemented)
uv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000

# Format + lint + types
scripts/lint.sh

# Run tests (python + rust)
scripts/test.sh

# Docker dev stack
scripts/dev.sh up          # Start (API, Postgres, Redis, MinIO)
scripts/dev.sh down         # Stop
scripts/dev.sh up-clickhouse  # Start with ClickHouse for Common Crawl

# Database migrations
export DATABASE_URL="postgresql+psycopg://semrush:semrush@localhost:5432/semrush"
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head
uv run --package semrush-core alembic -c migrations/alembic.ini revision --autogenerate -m "description"
```

## Architecture

### Two-Plane Design
- **Control plane (Python):** API, integrations, workers, reports, Common Crawl ingest
- **Data plane (Rust):** High-throughput crawler with frontier scheduling

### Workspace Structure (uv monorepo)
```
libs/
  core/         # Shared core library
  seo/          # SEO-specific utilities
  backlinks/    # Backlink processing

apps/
  api/          # FastAPI public API + dashboard
  workers/      # Orchestration + rules + alerts
  integrations/ # OAuth + provider sync + normalization
  reports/      # Exports + PDF rendering
  commoncrawl_ingest/  # Common Crawl pipeline

crates/
  crawler/      # Rust high-throughput fetch/parse

migrations/     # Alembic migrations
infra/          # Docker Compose configs
```

### Storage Systems
- **Postgres:** System of record (users, projects, crawls, issues, integrations)
- **Redis:** Work queue + locks
- **MinIO/S3:** HTML artifacts, exports
- **ClickHouse (optional):** Common Crawl edge storage at scale

### Key Architectural Principles
- **Truth-first:** First-party integrations (GSC/GA4/BWT) are core drivers
- **Free data moat:** Common Crawl ingestion provides backlink data without paid APIs
- **Hybrid crawling:** HTML-first with Playwright fallback under configurable budgets
- **Stable event schemas:** Message payloads remain stable even if transport changes (Redis -> NATS/Kafka)

## Code Quality

### Tooling Configuration
- **Python:** 3.12 required
- **Ruff:** Line length 100, rules E/F/I/B/UP/SIM/RUF, double quotes
- **MyPy:** warn_return_any, check_untyped_defs, no_implicit_optional
- **pytest:** Test paths in apps/ and libs/

### Event Schema Pattern
All internal events use a common envelope:
- `event_id`, `event_type`, `occurred_at`, `project_id`, `trace_id`, `payload`

Core event types: `integration.sync_*`, `crawl.*`, `rules.completed`, `alert.fired`, `commoncrawl.ingest_*`

## Key Documentation

- `ARCHITECTURE.md` - Services, data flows, event schemas
- `BLUEPRINT-PRD-MVP.md` - Product requirements, feature specs, project settings
- `COMMONCRAWL_INGESTION.md` - Common Crawl pipeline design and ClickHouse schemas
- `openapi.yaml` - Complete API specification (40+ endpoints)

## Environment Variables

```bash
DATABASE_URL          # Postgres DSN
REDIS_URL             # Redis DSN
JWT_SECRET            # JWT signing (never use dev default in production)
MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/S3_BUCKET  # Object storage
CLICKHOUSE_URL/DATABASE  # Optional Common Crawl storage
GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI  # OAuth integrations
```
