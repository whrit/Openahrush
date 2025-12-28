````markdown
# Openahrush (MVP)

An open-source, self-hostable SEO platform inspired by Semrush and Ahrefs “Projects” workflows.

**Core MVP capabilities**
- **Projects**: sites, competitors, schedules, budgets/retention settings
- **Integrations (truth-first)**: Google Search Console (GSC), Google Analytics (GA4), Bing Webmaster Tools (BWT)
- **Hybrid Site Audit**: HTML-first crawler with **Playwright fallback** for JS-heavy pages (budgeted)
- **Impact-aware prioritization**: issues ranked using real impressions/sessions/conversions (where available)
- **Backlinks (free data moat)**:
  - **Common Crawl ingestion (core MVP)** for backlink/ref-domain explorer + new/lost + overlap/intersect
  - plus CSV imports + provider links (where available)
- **Exports + Webhooks**: CSV/JSON/PDF exports + event webhooks

> Status: MVP scaffolding. Interfaces and schemas are evolving; expect breaking changes until v1.0.

---

## Table of contents
- [Architecture](#architecture)
- [Quickstart](#quickstart)
  - [Local dev (uv)](#local-dev-uv)
  - [Run with Docker Compose](#run-with-docker-compose)
  - [Optional ClickHouse](#optional-clickhouse)
- [Database migrations (Alembic)](#database-migrations-alembic)
- [Configuration](#configuration)
- [Common Crawl ingestion](#common-crawl-ingestion)
- [API](#api)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Architecture

This repo is a monorepo with:
- **Python control plane** (API, integrations, workers, reports, Common Crawl ingest)
- **Rust data plane** (crawler/frontier for high-throughput crawling)

Docs:
- `docs/ARCHITECTURE.md` — services, data flows, and event schemas
- `docs/COMMONCRAWL_INGESTION.md` — Common Crawl ingest design and storage strategy
- `openapi.yaml` — API scaffold/spec

---

## Quickstart

### Prerequisites
- **Python 3.12**
- **uv** (package manager): https://astral.sh/uv/
- **Docker** (optional, but recommended for local stack)

---

### Local dev (uv)

1) Install dependencies (workspace):
```bash
uv sync
````

2. Run the API locally (dev server):

```bash
uv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000
```

3. Verify:

* [http://localhost:8000/healthz](http://localhost:8000/healthz)
* [http://localhost:8000/readyz](http://localhost:8000/readyz)

---

### Run with Docker Compose

From repo root:

```bash
scripts/dev.sh up
```

Services (default):

* API: [http://localhost:8000](http://localhost:8000)
* Postgres: localhost:5432
* Redis: localhost:6379
* MinIO: [http://localhost:9000](http://localhost:9000) (console: [http://localhost:9001](http://localhost:9001))

Stop:

```bash
scripts/dev.sh down
```

---

### Optional ClickHouse

ClickHouse is recommended when enabling meaningful Common Crawl ingestion beyond tiny subsets.

Start with ClickHouse overlay:

```bash
scripts/dev.sh up-clickhouse
```

ClickHouse ports:

* HTTP: [http://localhost:8123](http://localhost:8123)
* Native: localhost:9000

---

## Database migrations (Alembic)

Migrations are managed via Alembic in `migrations/`.

### Apply migrations (local Postgres)

If your Postgres is running locally with the default credentials:

```bash
export DATABASE_URL="postgresql+psycopg://semrush:semrush@localhost:5432/semrush"
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head
```

### Apply migrations (Docker Postgres)

If using Docker Compose and exposing Postgres on localhost:5432:

```bash
export DATABASE_URL="postgresql+psycopg://semrush:semrush@localhost:5432/semrush"
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head
```

### Create a new migration

```bash
uv run --package semrush-core alembic -c migrations/alembic.ini revision --autogenerate -m "add integrations tables"
```

---

## Configuration

Services read configuration from environment variables. In Docker, these are defined in `infra/compose/docker-compose.yml`.

Common variables:

* `DATABASE_URL` — Postgres DSN
* `REDIS_URL` — Redis DSN
* `JWT_SECRET` — JWT signing secret (dev-only default is unsafe in production)
* `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `S3_BUCKET` — artifacts/export storage
* `CLICKHOUSE_URL`, `CLICKHOUSE_DATABASE` — Common Crawl edge storage (optional)

OAuth (placeholders in Compose):

* `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`

Project settings (scope, include/exclude, query params, budgets, schedules, retention) are stored per-project and enforced by crawls and jobs.

See:

* `PRD.md` (settings spec)
* `openapi.yaml` (`ProjectSettings` schema)

---

## Common Crawl ingestion

Common Crawl ingestion powers the backlink explorer and competitive link intel using open data.

Key concepts:

* **Snapshots** (e.g., `CC-MAIN-YYYY-XX`)
* **Ingestion jobs** that parse WAT (metadata) to extract link edges (WAT-first strategy)
* **Aggregates/materializations** for interactive queries:

  * referring domains
  * anchors distribution
  * new/lost between snapshots
  * overlap/intersect vs competitors

Endpoints:

* `GET /commoncrawl/snapshots`
* `POST /commoncrawl/ingest` (operator/admin)
* `GET /links/domain/{domain}/refdomains`
* `GET /links/domain/{domain}/backlinks`
* `GET /links/domain/{domain}/anchors`
* `GET /links/domain/{domain}/new-lost`
* `GET /links/domain/{domain}/overlap`
* `GET /links/domain/{domain}/intersect`

Implementation notes and subset strategies:

* `docs/COMMONCRAWL_INGESTION.md`

---

## API

The API is described in:

* `openapi.yaml`

Health endpoints:

* `GET /healthz`
* `GET /readyz`

---

## Development

Common commands:

```bash
# format + lint + types
scripts/lint.sh

# python + rust tests
scripts/test.sh

# docker dev
scripts/dev.sh up
scripts/dev.sh down
```

Repo layout:

* `apps/` deployable services (api/workers/integrations/reports/commoncrawl_ingest)
* `libs/` shared libraries (core/seo/backlinks)
* `crates/` Rust workspace (crawler)
* `migrations/` Alembic migrations
* `infra/` compose + ClickHouse init SQL
* `docs/` specs and architecture

---

## Troubleshooting

### Postgres extension error: `citext`

The initial migration creates the `citext` extension. Ensure your Postgres instance allows extensions (default local Postgres does).

### Port conflicts

If Docker services fail to start due to port conflicts (5432, 6379, 8000), stop the conflicting services or change ports in Compose.

### WeasyPrint dependencies

The reports container installs additional system libraries for WeasyPrint. If you replace PDF rendering later (e.g., Playwright PDF), you can remove those dependencies.

---

## License

See `LICENSE`.
