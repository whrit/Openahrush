# Developer Guide

This guide covers the Openahrush codebase architecture, development setup, and contribution guidelines for developers working on or extending the platform.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Adding New Features](#adding-new-features)
- [Testing](#testing)
- [Code Style](#code-style)
- [Contributing](#contributing)

---

## Architecture Overview

### Two-Plane Design

**Control Plane (Python):**
- FastAPI REST API
- OAuth integrations (Google, Microsoft)
- Background workers (Celery/RQ)
- PDF/CSV export generation
- Common Crawl ingestion pipeline

**Data Plane (Rust - Future):**
- High-throughput crawler
- Frontier scheduling
- HTML parsing and extraction
- *Note: MVP uses Python crawler; Rust implementation planned*

### Service Architecture

```
apps/
├── api/          # FastAPI application (public API)
├── workers/      # Background job processors
├── integrations/ # OAuth + data sync adapters
├── reports/      # Export generation
└── commoncrawl_ingest/  # Common Crawl pipeline

libs/
├── core/         # Shared models, database, security
├── seo/          # URL normalization, robots.txt, HTML extraction
└── backlinks/    # Backlink processing utilities
```

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| API Framework | FastAPI | Latest |
| Database | PostgreSQL | 16+ |
| ORM | SQLAlchemy 2.0 | Async |
| Cache/Queue | Redis | 7+ |
| Object Storage | MinIO/S3 | - |
| Analytics DB | ClickHouse | 23+ (optional) |
| Language | Python | 3.12+ |
| Package Manager | uv | Latest |

---

## Development Setup

### Prerequisites

```bash
# Python 3.12+
python --version

# uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Docker and Docker Compose
docker --version
docker compose version

# PostgreSQL client (for migrations)
sudo apt-get install postgresql-client
```

### Clone and Install

```bash
# Clone repository
git clone https://github.com/yourusername/openahrush.git
cd openahrush

# Install dependencies (creates virtual environment)
uv sync

# Verify installation
uv run python --version
```

### Start Development Services

```bash
# Start Postgres, Redis, MinIO
scripts/dev.sh up

# Or start all including ClickHouse
scripts/dev.sh up-clickhouse

# Verify services are healthy
docker compose -f infra/compose/docker-compose.yml ps
```

### Database Setup

```bash
# Set database URL
export DATABASE_URL="postgresql+psycopg://semrush:semrush@localhost:5432/semrush"

# Run migrations
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head

# Verify
uv run --package semrush-core alembic -c migrations/alembic.ini current
```

### Run API Server

```bash
# Development mode with auto-reload
uv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env

# Minimal required for development:
DATABASE_URL=postgresql+psycopg://semrush:semrush@localhost:5432/semrush
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=dev-secret-key-change-in-production
ENCRYPTION_KEY=dev-encryption-key-change-in-production
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
S3_BUCKET=openahrush
DEBUG=true
```

---

## Project Structure

### Monorepo Layout

```
openahrush/
├── apps/                     # Application packages
│   ├── api/                 # FastAPI REST API
│   │   ├── src/semrush_api/
│   │   │   ├── routers/    # API route handlers
│   │   │   ├── schemas/    # Pydantic request/response models
│   │   │   ├── deps.py     # FastAPI dependencies
│   │   │   └── main.py     # Application entry point
│   │   └── tests/          # API tests
│   ├── workers/            # Background job processors
│   ├── integrations/       # OAuth + data sync
│   ├── reports/            # Export generation
│   └── commoncrawl_ingest/ # Common Crawl pipeline
│
├── libs/                    # Shared libraries
│   ├── core/               # semrush-core
│   │   ├── src/semrush_core/
│   │   │   ├── models/    # SQLAlchemy models
│   │   │   ├── security/  # JWT, encryption, passwords
│   │   │   ├── database.py # DB connection
│   │   │   └── config.py  # Settings
│   │   └── tests/
│   ├── seo/                # semrush-seo
│   │   ├── src/semrush_seo/
│   │   │   ├── url_utils.py      # URL normalization
│   │   │   ├── robots.py         # robots.txt parsing
│   │   │   ├── sitemap.py        # Sitemap parsing
│   │   │   └── html_extract.py   # HTML extraction
│   │   └── tests/
│   └── backlinks/          # semrush-backlinks
│
├── migrations/             # Alembic database migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
├── infra/                  # Infrastructure configs
│   ├── compose/           # Docker Compose files
│   └── clickhouse/        # ClickHouse schemas
│
├── scripts/               # Development scripts
│   ├── dev.sh            # Start dev services
│   ├── test.sh           # Run tests
│   └── lint.sh           # Lint and format
│
├── docs/                  # Documentation
├── pyproject.toml         # Python project config
└── uv.lock               # Dependency lock file
```

### Key Conventions

**Package naming:**
- `apps/*` → `semrush-{name}` package
- `libs/*` → `semrush-{name}` package
- Import as: `from semrush_api import ...`

**File naming:**
- Python files: `snake_case.py`
- Test files: `test_*.py`
- Models: `{entity}.py` (e.g., `project.py`, `user.py`)

---

## Development Workflow

### Running Tests

```bash
# Run all tests with coverage
scripts/test.sh

# Run specific test file
uv run pytest apps/api/tests/test_auth.py -v

# Run tests matching pattern
uv run pytest -k "test_login" -v

# Run tests and stop on first failure
uv run pytest -x

# Run with coverage report
uv run pytest --cov=apps --cov=libs --cov-report=html
```

### Linting and Formatting

```bash
# Run all checks (format + lint + types)
scripts/lint.sh

# Auto-fix formatting issues
uv run ruff format .

# Auto-fix linting issues
uv run ruff check --fix .

# Type checking only
uv run mypy apps/ libs/
```

### Code Style

**Ruff configuration:**
- Line length: 100
- Quote style: Double quotes
- Rules: E, F, I, B, UP, SIM, RUF
- Import sorting: Enabled

**MyPy configuration:**
- `no_implicit_optional = true`
- `check_untyped_defs = true`
- `strict_optional = true`

**Example:**

```python
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from semrush_api.deps import CurrentUser, DbSession
from semrush_core.models import Project


async def get_project(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Project:
    """
    Retrieve a project by ID.

    Args:
        project_id: Project UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Project instance

    Raises:
        HTTPException: 404 if project not found or not owned by user
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.user_id,
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project
```

### Database Migrations

**Creating migrations:**

```bash
# Generate migration from model changes
uv run --package semrush-core alembic -c migrations/alembic.ini revision --autogenerate -m "add user preferences table"

# Review generated migration in migrations/versions/
# Edit if necessary

# Apply migration
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head
```

**Migration best practices:**
- Always review autogenerated migrations
- Test migrations up AND down
- Use batch operations for large tables
- Document data migrations in comments

**Example migration:**

```python
"""add user preferences table

Revision ID: abc123def456
Revises: xyz789uvw012
Create Date: 2025-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'abc123def456'
down_revision = 'xyz789uvw012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('theme', sa.String(20), server_default='light'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_user_preferences_user', 'user_preferences', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_user_preferences_user')
    op.drop_table('user_preferences')
```

---

## Adding New Features

### Adding a New API Endpoint

**1. Define Pydantic schemas (`apps/api/src/semrush_api/schemas/`):**

```python
# apps/api/src/semrush_api/schemas/keyword.py
from pydantic import BaseModel, Field
from uuid import UUID


class KeywordCreate(BaseModel):
    project_id: UUID
    keyword: str = Field(min_length=1, max_length=200)
    search_volume: int | None = None


class KeywordResponse(BaseModel):
    id: UUID
    project_id: UUID
    keyword: str
    search_volume: int | None
    created_at: str

    class Config:
        from_attributes = True
```

**2. Add router (`apps/api/src/semrush_api/routers/`):**

```python
# apps/api/src/semrush_api/routers/keywords.py
from fastapi import APIRouter, status
from semrush_core.models import Keyword
from semrush_api.deps import CurrentUser, DbSession
from semrush_api.schemas.keyword import KeywordCreate, KeywordResponse

router = APIRouter(prefix="/projects/{project_id}/keywords", tags=["Keywords"])


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    project_id: UUID,
    data: KeywordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> KeywordResponse:
    """Create a new keyword for tracking."""
    keyword = Keyword(
        project_id=project_id,
        keyword=data.keyword,
        search_volume=data.search_volume,
    )
    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)
    return KeywordResponse.model_validate(keyword)
```

**3. Register router (`apps/api/src/semrush_api/main.py`):**

```python
from semrush_api.routers import keywords

def register_routers(app: FastAPI) -> None:
    # ... existing routers ...
    app.include_router(keywords.router, tags=["Keywords"])
```

**4. Add tests (`apps/api/tests/`):**

```python
# apps/api/tests/test_keywords.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_keyword(client: AsyncClient, auth_headers: dict, project_id: str):
    response = await client.post(
        f"/projects/{project_id}/keywords",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "keyword": "seo tools",
            "search_volume": 5000,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["keyword"] == "seo tools"
    assert data["search_volume"] == 5000
```

### Adding a New Database Model

**1. Create model (`libs/core/src/semrush_core/models/`):**

```python
# libs/core/src/semrush_core/models/keyword.py
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from .base import Base, UUIDMixin, TimestampMixin


class Keyword(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "keywords"

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    search_volume: Mapped[int | None]

    # Relationship
    project: Mapped["Project"] = relationship(back_populates="keywords")
```

**2. Add to `__init__.py`:**

```python
# libs/core/src/semrush_core/models/__init__.py
from .keyword import Keyword

__all__ = [
    # ... existing exports ...
    "Keyword",
]
```

**3. Generate migration:**

```bash
uv run --package semrush-core alembic -c migrations/alembic.ini revision --autogenerate -m "add keywords table"
```

**4. Review and apply migration:**

```bash
# Review generated file in migrations/versions/
# Apply migration
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head
```

### Adding a New Rule to the Audit Engine

**1. Define rule (`apps/workers/src/semrush_workers/rules/`):**

```python
# apps/workers/src/semrush_workers/rules/missing_h1.py
from semrush_core.models import IssueType
from semrush_workers.rules.base import Rule, RuleResult


class MissingH1Rule(Rule):
    """Check for missing H1 tags."""

    @property
    def issue_type(self) -> IssueType:
        return IssueType(
            code="missing_h1",
            name="Missing H1 Tag",
            severity="medium",
            description="Page has no H1 tag or empty H1",
        )

    async def evaluate(self, page_data: dict) -> RuleResult | None:
        """
        Evaluate page for missing H1.

        Args:
            page_data: Extracted page data with h1_count, first_h1

        Returns:
            RuleResult if issue found, None otherwise
        """
        h1_count = page_data.get("h1_count", 0)
        first_h1 = page_data.get("first_h1", "")

        if h1_count == 0 or not first_h1.strip():
            return RuleResult(
                issue_type_code=self.issue_type.code,
                severity="medium",
                confidence=1.0,
                evidence={
                    "h1_count": h1_count,
                    "expected": "At least one non-empty H1 tag",
                    "found": first_h1 or None,
                },
            )

        return None
```

**2. Register rule (`apps/workers/src/semrush_workers/rules/__init__.py`):**

```python
from .missing_h1 import MissingH1Rule

ALL_RULES = [
    # ... existing rules ...
    MissingH1Rule(),
]
```

**3. Add tests:**

```python
# apps/workers/tests/test_rules/test_missing_h1.py
import pytest
from semrush_workers.rules.missing_h1 import MissingH1Rule


@pytest.mark.asyncio
async def test_missing_h1_detected():
    rule = MissingH1Rule()
    page_data = {
        "url": "https://example.com/page",
        "h1_count": 0,
        "first_h1": "",
    }
    result = await rule.evaluate(page_data)
    assert result is not None
    assert result.issue_type_code == "missing_h1"
    assert result.severity == "medium"


@pytest.mark.asyncio
async def test_h1_present_no_issue():
    rule = MissingH1Rule()
    page_data = {
        "url": "https://example.com/page",
        "h1_count": 1,
        "first_h1": "Page Title",
    }
    result = await rule.evaluate(page_data)
    assert result is None
```

### Adding a New Integration Provider

**1. Create adapter (`apps/integrations/src/semrush_integrations/providers/`):**

```python
# apps/integrations/src/semrush_integrations/providers/yandex.py
from semrush_integrations.oauth.base import OAuthProvider


class YandexWebmasterAdapter(OAuthProvider):
    """Yandex Webmaster Tools integration."""

    provider_name = "yandex"

    def get_authorization_url(self) -> tuple[str, str]:
        """Generate OAuth authorization URL."""
        # Implementation
        pass

    async def exchange_code_for_token(self, code: str, state: str) -> dict:
        """Exchange authorization code for access token."""
        # Implementation
        pass

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh expired access token."""
        # Implementation
        pass

    async def list_properties(self, access_token: str) -> list[dict]:
        """List user's verified sites."""
        # Implementation
        pass

    async def fetch_search_performance(
        self,
        access_token: str,
        property_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Fetch search performance data."""
        # Implementation
        pass
```

**2. Register provider:**

```python
# apps/integrations/src/semrush_integrations/providers/__init__.py
from .yandex import YandexWebmasterAdapter

PROVIDERS = {
    "google": GoogleAdapter(),
    "microsoft": MicrosoftAdapter(),
    "yandex": YandexWebmasterAdapter(),  # New provider
}
```

---

## Testing

### Test Structure

```
apps/api/tests/
├── conftest.py         # Shared fixtures
├── test_auth.py
├── test_projects.py
└── test_integrations.py

libs/core/tests/
├── conftest.py
├── test_models.py
├── test_security.py
└── test_encryption.py
```

### Writing Tests

**Fixture example (`conftest.py`):**

```python
import pytest
from httpx import AsyncClient
from semrush_api.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers(access_token: str) -> dict:
    """Authorization headers with access token."""
    return {"Authorization": f"Bearer {access_token}"}
```

**Test example:**

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, auth_headers: dict):
    """Test project creation."""
    response = await client.post(
        "/projects",
        headers=auth_headers,
        json={"name": "Test Project"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_project_unauthorized(client: AsyncClient):
    """Test project creation without authentication."""
    response = await client.post(
        "/projects",
        json={"name": "Test Project"},
    )
    assert response.status_code == 401
```

### Coverage Goals

- **libs/:** >80% coverage (shared code, heavily reused)
- **apps/:** >70% coverage (application logic)
- **Critical paths:** 100% coverage (auth, security, payments)

---

## Code Style

### Python Style Guide

Follow PEP 8 with these specific rules:

**Imports:**
```python
# Standard library
import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

# Third-party
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

# Local
from semrush_api.deps import CurrentUser, DbSession
from semrush_core.models import Project
```

**Docstrings:**
```python
def calculate_impact_score(
    severity: int,
    confidence: float,
    traffic_weight: float,
) -> float:
    """
    Calculate issue impact score.

    Args:
        severity: Issue severity (2-10)
        confidence: Confidence level (0.0-1.0)
        traffic_weight: Traffic weight factor (0.0-2.0)

    Returns:
        Calculated impact score

    Raises:
        ValueError: If inputs are out of valid range
    """
    if not 2 <= severity <= 10:
        raise ValueError(f"Invalid severity: {severity}")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"Invalid confidence: {confidence}")

    return severity * confidence * traffic_weight
```

**Type hints:**
```python
# Always use type hints
def process_page(url: str, depth: int = 0) -> dict[str, Any]:
    ...

# Use modern syntax (Python 3.10+)
def get_project(project_id: UUID) -> Project | None:  # Not Optional[Project]
    ...

# Async functions
async def fetch_data(url: str) -> list[dict[str, Any]]:
    ...
```

---

## Contributing

### Contribution Workflow

1. **Fork repository**
2. **Create feature branch:** `git checkout -b feature/my-feature`
3. **Make changes** with tests
4. **Run linter:** `scripts/lint.sh`
5. **Run tests:** `scripts/test.sh`
6. **Commit** with clear message
7. **Push** to your fork
8. **Create Pull Request**

### Commit Messages

Follow conventional commits:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Add/update tests
- `chore:` Build/tooling changes

**Examples:**
```
feat(api): add keyword tracking endpoints

Implement CRUD endpoints for keyword management including
search volume tracking and position monitoring.

Closes #123
```

```
fix(auth): handle expired tokens gracefully

Previously, expired tokens caused 500 errors. Now returns
401 with clear error message prompting re-authentication.
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How this was tested

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Linting passes
- [ ] No breaking changes (or documented)
```

---

## Additional Resources

- **API Reference:** [API_REFERENCE.md](/Users/beckett/Projects/Openahrush/docs/API_REFERENCE.md)
- **Deployment Guide:** [DEPLOYMENT.md](/Users/beckett/Projects/Openahrush/docs/DEPLOYMENT.md)
- **Architecture:** [ARCHITECTURE.md](/Users/beckett/Projects/Openahrush/ARCHITECTURE.md)
- **Product Spec:** [BLUEPRINT-PRD-MVP.md](/Users/beckett/Projects/Openahrush/BLUEPRINT-PRD-MVP.md)
- **GitHub:** https://github.com/yourusername/openahrush
