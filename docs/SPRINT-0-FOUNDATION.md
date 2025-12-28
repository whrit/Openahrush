# Sprint 0: Foundation & Platform

**Duration:** 2-3 weeks
**Dependencies:** None
**Status:** Complete (2025-12-28)

This sprint establishes the core platform skeleton: FastAPI application, database schema, development infrastructure, and basic project management.

---

## Objectives

1. Bootstrap the Python monorepo with working packages
2. Create FastAPI API with auth scaffolding
3. Set up Postgres with Alembic migrations
4. Configure Redis queue infrastructure
5. Create Docker Compose development environment
6. Implement health endpoints and Projects CRUD
7. Build Project Settings model and enforcement

---

## Epic 0.1: Workspace Bootstrap

### Task 0.1.1: Create libs/core package

**Description:** Initialize the shared core library with base models, utilities, and database configuration.

**Acceptance Criteria:**
- [x] `libs/core/pyproject.toml` created with dependencies
- [x] `libs/core/src/semrush_core/__init__.py` exists
- [x] `libs/core/src/semrush_core/config.py` with Settings class (pydantic-settings)
- [x] `libs/core/src/semrush_core/database.py` with async SQLAlchemy engine
- [x] `libs/core/src/semrush_core/models/base.py` with Base declarative model
- [x] `uv sync` succeeds

**Files to Create:**
```
libs/core/
├── pyproject.toml
├── src/
│   └── semrush_core/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       └── models/
│           ├── __init__.py
│           └── base.py
```

**Dependencies:**
- sqlalchemy[asyncio] >= 2.0
- asyncpg
- pydantic-settings
- alembic

---

### Task 0.1.2: Create libs/seo package

**Description:** Initialize the SEO utilities library for URL normalization and extraction.

**Acceptance Criteria:**
- [x] `libs/seo/pyproject.toml` created
- [x] `libs/seo/src/semrush_seo/__init__.py` exists
- [x] `libs/seo/src/semrush_seo/url.py` with URL normalization utilities
- [x] `libs/seo/src/semrush_seo/extraction.py` placeholder for HTML extraction

**Files to Create:**
```
libs/seo/
├── pyproject.toml
├── src/
│   └── semrush_seo/
│       ├── __init__.py
│       ├── url.py
│       └── extraction.py
```

**Dependencies:**
- urllib3
- tldextract

---

### Task 0.1.3: Create libs/backlinks package

**Description:** Initialize the backlinks processing library (placeholder for Sprint 3).

**Acceptance Criteria:**
- [x] `libs/backlinks/pyproject.toml` created
- [x] `libs/backlinks/src/semrush_backlinks/__init__.py` exists
- [x] Placeholder modules for future backlink processing

**Files to Create:**
```
libs/backlinks/
├── pyproject.toml
├── src/
│   └── semrush_backlinks/
│       ├── __init__.py
│       └── models.py
```

---

### Task 0.1.4: Create apps/api package

**Description:** Initialize the FastAPI application with basic structure.

**Acceptance Criteria:**
- [x] `apps/api/pyproject.toml` created with FastAPI dependencies
- [x] `apps/api/src/semrush_api/__init__.py` exists
- [x] `apps/api/src/semrush_api/main.py` with FastAPI app instance
- [x] `apps/api/src/semrush_api/routers/` directory structure
- [x] Application starts with `uvicorn semrush_api.main:app`

**Files to Create:**
```
apps/api/
├── pyproject.toml
├── src/
│   └── semrush_api/
│       ├── __init__.py
│       ├── main.py
│       ├── deps.py
│       └── routers/
│           ├── __init__.py
│           └── health.py
```

**Dependencies:**
- fastapi >= 0.109
- uvicorn[standard]
- python-jose[cryptography]
- passlib[bcrypt]
- semrush-core (workspace)

---

### Task 0.1.5: Create apps/workers package (skeleton)

**Description:** Initialize the worker orchestration package.

**Acceptance Criteria:**
- [x] `apps/workers/pyproject.toml` created
- [x] `apps/workers/src/semrush_workers/__init__.py` exists
- [x] `apps/workers/src/semrush_workers/runner.py` with worker loop placeholder

**Files to Create:**
```
apps/workers/
├── pyproject.toml
├── src/
│   └── semrush_workers/
│       ├── __init__.py
│       ├── runner.py
│       └── tasks/
│           └── __init__.py
```

**Dependencies:**
- redis
- semrush-core (workspace)

---

### Task 0.1.6: Create remaining app packages (skeleton)

**Description:** Initialize skeleton packages for integrations, reports, and commoncrawl_ingest.

**Acceptance Criteria:**
- [x] `apps/integrations/` package created with pyproject.toml
- [x] `apps/reports/` package created with pyproject.toml
- [x] `apps/commoncrawl_ingest/` package created with pyproject.toml

**Files to Create:**
```
apps/integrations/
├── pyproject.toml
├── src/
│   └── semrush_integrations/
│       └── __init__.py

apps/reports/
├── pyproject.toml
├── src/
│   └── semrush_reports/
│       └── __init__.py

apps/commoncrawl_ingest/
├── pyproject.toml
├── src/
│   └── semrush_commoncrawl/
│       └── __init__.py
```

---

## Epic 0.2: Database & Migrations

### Task 0.2.1: Set up Alembic migrations

**Description:** Configure Alembic for database migrations with async support.

**Acceptance Criteria:**
- [x] `migrations/alembic.ini` created
- [x] `migrations/env.py` configured for async SQLAlchemy
- [x] `migrations/script.py.mako` template exists
- [x] `migrations/versions/` directory exists
- [x] Migration commands work via `uv run`

**Files to Create:**
```
migrations/
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    └── .gitkeep
```

---

### Task 0.2.2: Create initial schema migration

**Description:** Create the initial database schema with core tables.

**Acceptance Criteria:**
- [x] Migration creates `users` table
- [x] Migration creates `projects` table
- [x] Migration creates `sites` table
- [x] Migration creates `competitors` table
- [x] Migration creates `project_settings` table
- [x] Migration enables `citext` and `uuid-ossp` extensions
- [x] `alembic upgrade head` succeeds

**Schema (users):**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Schema (projects):**
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

**Schema (sites):**
```sql
CREATE TABLE sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    base_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Schema (competitors):**
```sql
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Schema (project_settings):**
```sql
CREATE TABLE project_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

---

### Task 0.2.3: Create SQLAlchemy models

**Description:** Define SQLAlchemy ORM models for the core schema.

**Acceptance Criteria:**
- [x] `User` model in `libs/core/src/semrush_core/models/user.py`
- [x] `Project` model in `libs/core/src/semrush_core/models/project.py`
- [x] `Site` model in `libs/core/src/semrush_core/models/site.py`
- [x] `Competitor` model in `libs/core/src/semrush_core/models/competitor.py`
- [x] `ProjectSettings` model in `libs/core/src/semrush_core/models/settings.py`
- [x] Models imported in `models/__init__.py`

**Files to Create:**
```
libs/core/src/semrush_core/models/
├── __init__.py
├── base.py
├── user.py
├── project.py
├── site.py
├── competitor.py
└── settings.py
```

---

## Epic 0.3: Infrastructure

### Task 0.3.1: Create Docker Compose configuration

**Description:** Set up Docker Compose for local development with all required services.

**Acceptance Criteria:**
- [x] `infra/compose/docker-compose.yml` created
- [x] API service configured (builds from workspace)
- [x] Postgres service with health check
- [x] Redis service with health check
- [x] MinIO service with console
- [x] Network configuration correct
- [x] Volume mounts for persistence

**Services Configuration:**
```yaml
services:
  api:
    build: ../..
    ports: ["8000:8000"]
    depends_on: [postgres, redis, minio]

  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: semrush
      POSTGRES_PASSWORD: semrush
      POSTGRES_DB: semrush
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck: pg_isready -U semrush

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck: redis-cli ping

  minio:
    image: minio/minio
    ports: ["9000:9000", "9001:9001"]
    command: server /data --console-address ":9001"
```

**Files to Create:**
```
infra/
├── compose/
│   ├── docker-compose.yml
│   └── docker-compose.clickhouse.yml
└── clickhouse/
    └── init.sql
```

---

### Task 0.3.2: Create Dockerfile for API

**Description:** Create a multi-stage Dockerfile for the API service.

**Acceptance Criteria:**
- [x] `Dockerfile` at repo root
- [x] Uses Python 3.12 base image
- [x] Installs uv for dependency management
- [x] Copies workspace and builds packages
- [x] Runs uvicorn on port 8000
- [x] Non-root user for security

---

### Task 0.3.3: Create dev scripts

**Description:** Create shell scripts for common development tasks.

**Acceptance Criteria:**
- [x] `scripts/dev.sh` with up/down/logs/restart commands
- [x] `scripts/lint.sh` runs ruff + mypy
- [x] `scripts/test.sh` runs pytest
- [x] Scripts are executable (chmod +x)

**Files to Create:**
```
scripts/
├── dev.sh
├── lint.sh
└── test.sh
```

---

## Epic 0.4: Auth & Health Endpoints

### Task 0.4.1: Implement health endpoints

**Description:** Create /healthz and /readyz endpoints per OpenAPI spec.

**Acceptance Criteria:**
- [x] `GET /healthz` returns `{"ok": true, "version": "0.2.0"}`
- [x] `GET /readyz` checks database connectivity
- [x] Returns 503 if database unreachable
- [x] No authentication required

**Router:** `apps/api/src/semrush_api/routers/health.py`

---

### Task 0.4.2: Implement auth endpoints

**Description:** Create login/logout/me endpoints with JWT authentication.

**Acceptance Criteria:**
- [x] `POST /auth/login` validates credentials, returns JWT
- [x] `POST /auth/logout` acknowledges logout
- [x] `GET /me` returns current user (requires auth)
- [x] JWT tokens have configurable expiry
- [x] Password hashing with bcrypt

**Router:** `apps/api/src/semrush_api/routers/auth.py`

**Dependencies:** `apps/api/src/semrush_api/deps.py` with `get_current_user`

---

### Task 0.4.3: Implement user registration (optional)

**Description:** Add user registration endpoint for self-hosted deployments.

**Acceptance Criteria:**
- [x] `POST /auth/register` creates new user
- [x] Email uniqueness validated
- [x] Password strength requirements (configurable)
- [x] Returns created user (without password)

---

## Epic 0.5: Projects CRUD

### Task 0.5.1: Implement Projects list/create

**Description:** Create endpoints for listing and creating projects.

**Acceptance Criteria:**
- [x] `GET /projects` returns paginated project list for current user
- [x] `POST /projects` creates a new project
- [x] Validates required fields (name)
- [x] Sets owner_id from current user
- [x] Returns 201 on creation

**Router:** `apps/api/src/semrush_api/routers/projects.py`

---

### Task 0.5.2: Implement Projects get/update/delete

**Description:** Create endpoints for individual project operations.

**Acceptance Criteria:**
- [x] `GET /projects/{project_id}` returns project details
- [x] `PATCH /projects/{project_id}` updates project fields
- [x] `DELETE /projects/{project_id}` soft-deletes or hard-deletes project
- [x] 404 if project not found
- [x] 403 if user doesn't own project

---

### Task 0.5.3: Implement Sites management

**Description:** Create endpoints for managing sites within projects.

**Acceptance Criteria:**
- [x] `POST /projects/{project_id}/sites` adds a site
- [x] Validates domain and base_url format
- [x] Returns 201 on creation
- [x] Site belongs to project

**Router:** `apps/api/src/semrush_api/routers/sites.py` (or in projects.py)

---

### Task 0.5.4: Implement Competitors management

**Description:** Create endpoints for managing competitor domains.

**Acceptance Criteria:**
- [x] `POST /projects/{project_id}/competitors` adds a competitor
- [x] `GET /projects/{project_id}/competitors` lists competitors
- [x] Validates domain format
- [x] Returns 201 on creation

---

## Epic 0.6: Project Settings

### Task 0.6.1: Define ProjectSettings Pydantic model

**Description:** Create Pydantic model matching the OpenAPI ProjectSettings schema.

**Acceptance Criteria:**
- [x] All settings fields defined with correct types and defaults
- [x] Scope settings: seed_url, include_subdomains, allowed_hosts, regexes
- [x] Query param settings: policy, allowlist, denylist, strip_tracking
- [x] Crawl budgets: max_pages, max_depth, concurrency, politeness, robots, sitemaps
- [x] JS rendering: mode, max_rendered, timeout, concurrency, required_selectors
- [x] Schedules: audit/sync/visibility/links frequency
- [x] Retention: audit_runs, serp_days, html_days
- [x] Validation for regex patterns

**File:** `libs/core/src/semrush_core/schemas/settings.py`

---

### Task 0.6.2: Implement Settings endpoints

**Description:** Create GET/PUT endpoints for project settings.

**Acceptance Criteria:**
- [x] `GET /projects/{project_id}/settings` returns current settings (or defaults)
- [x] `PUT /projects/{project_id}/settings` updates settings
- [x] Settings stored as JSONB in project_settings table
- [x] Validates all settings against schema
- [x] Returns 404 if project not found

**Router:** `apps/api/src/semrush_api/routers/settings.py`

---

### Task 0.6.3: Create settings defaults logic

**Description:** Implement default settings and merge logic.

**Acceptance Criteria:**
- [x] Default settings defined in code
- [x] New projects get default settings automatically
- [x] Partial updates merge with existing settings
- [x] Settings can be reset to defaults

---

## Verification Checklist

### Endpoints Working
- [x] `GET /healthz` → 200
- [x] `GET /readyz` → 200 (with DB)
- [x] `POST /auth/login` → JWT token
- [x] `GET /me` → current user
- [x] `POST /projects` → 201
- [x] `GET /projects` → project list
- [x] `GET /projects/{id}` → project detail
- [x] `PATCH /projects/{id}` → updated project
- [x] `DELETE /projects/{id}` → 204
- [x] `POST /projects/{id}/sites` → 201
- [x] `POST /projects/{id}/competitors` → 201
- [x] `GET /projects/{id}/competitors` → list
- [x] `GET /projects/{id}/settings` → settings
- [x] `PUT /projects/{id}/settings` → 200

### Development Infrastructure
- [x] `uv sync` succeeds
- [x] `uv run --package semrush-api uvicorn semrush_api.main:app` starts
- [x] `scripts/dev.sh up` brings up Docker stack
- [x] `scripts/dev.sh down` tears down cleanly
- [x] `scripts/lint.sh` passes
- [x] `scripts/test.sh` passes
- [x] Alembic migrations apply successfully

### Code Quality
- [x] All files pass Ruff linting
- [x] All files pass MyPy type checking
- [x] Test coverage for core functionality
- [x] OpenAPI spec matches implementation

---

## Notes

### Security Considerations
- JWT secret must be strong in production
- Password hashing uses bcrypt with appropriate cost
- Database credentials not hardcoded
- API validates all input

### Performance Considerations
- Database connection pooling configured
- Async endpoints where appropriate
- Health check caches DB connectivity briefly

### Next Sprint Dependencies
This sprint provides:
- Working API with auth
- Database with core schema
- Project/Settings infrastructure
- Docker dev environment

Required by:
- Sprint 1: Needs project infrastructure for integration mapping
- Sprint 2: Needs settings for crawl configuration
- Sprint 3: Needs database for edge storage
- Sprint 4: Needs all for export generation
