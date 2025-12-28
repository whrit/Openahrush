# Openahrush Infrastructure Setup Guide

This document describes the complete infrastructure setup for the Openahrush MVP, including Docker Compose configurations, scripts, and environment setup.

## Quick Start

### Prerequisites
- Docker & Docker Compose (v2.0+)
- Python 3.12
- uv package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### First-Time Setup

```bash
# 1. Copy environment file and review defaults
cp .env.example .env

# 2. Start all services (Postgres, Redis, MinIO, API)
./scripts/dev.sh up

# 3. Wait for services to be healthy
./scripts/dev.sh status

# 4. Run database migrations
./scripts/dev.sh migrate

# 5. View API documentation
# Open http://localhost:8000/docs
```

### Stop Services
```bash
./scripts/dev.sh down
```

## Architecture Overview

The Openahrush MVP uses a multi-container Docker Compose setup with:

- **API Container**: FastAPI application (Python 3.12, uv-managed)
- **PostgreSQL**: System of record database
- **Redis**: Work queue and caching layer
- **MinIO**: S3-compatible object storage for artifacts
- **ClickHouse** (optional): Time-series database for Common Crawl data

## Infrastructure Files

### Docker Compose Files

#### `/infra/compose/docker-compose.yml`
Main production-ready Docker Compose configuration with:

**Services:**
- **api**: FastAPI application
  - Port: 8000 (HTTP)
  - Health check: HTTP GET `/health`
  - Dependencies: postgres, redis, minio (all healthy)
  - Environment: Full configuration from `.env`
  - Network: `openahrush` bridge

- **postgres**: PostgreSQL 16 database
  - Port: 5432 (TCP)
  - User: `semrush` / Password: `semrush`
  - Database: `semrush`
  - Health check: `pg_isready` check every 10s
  - Volume: `postgres_data:/var/lib/postgresql/data`
  - Network: `openahrush` bridge

- **redis**: Redis 7 (Alpine)
  - Port: 6379 (TCP)
  - Command: `redis-server --appendonly yes` (AOF persistence)
  - Health check: `redis-cli ping` every 10s
  - Volume: `redis_data:/data`
  - Network: `openahrush` bridge

- **minio**: MinIO (S3-compatible object storage)
  - API Port: 9000
  - Console Port: 9001
  - Credentials: `minioadmin` / `minioadmin` (dev only)
  - Health check: HTTP GET `/minio/health/live` every 10s
  - Volume: `minio_data:/data`
  - Network: `openahrush` bridge

**Volumes:**
- `postgres_data`: PostgreSQL data directory
- `redis_data`: Redis AOF backup
- `minio_data`: MinIO object storage

**Networks:**
- `openahrush`: Bridge network connecting all services

#### `/infra/compose/docker-compose.clickhouse.yml`
Optional overlay configuration for Common Crawl ingestion:

```bash
# Start services with ClickHouse
./scripts/dev.sh up-clickhouse

# Or manually:
docker compose -f docker-compose.yml -f docker-compose.clickhouse.yml up -d
```

**Additional Service:**
- **clickhouse**: ClickHouse Server
  - HTTP Port: 8123
  - Native Port: 9000
  - HTTPS Port: 9440
  - Database: `openahrush` (auto-created)
  - User: `default` / Password: `default`
  - Health check: `curl http://localhost:8123/ping`
  - Volume: `clickhouse_data:/var/lib/clickhouse`

### Dockerfile

**Path**: `/Dockerfile`

Multi-stage build for production-grade container image:

1. **Builder Stage**: Installs build dependencies and Python packages via uv
   - Base: `python:3.12-slim`
   - Installs: build-essential, git, curl, uv
   - Runs: `uv sync --frozen --no-cache`

2. **Runtime Stage**: Minimal production image
   - Base: `python:3.12-slim`
   - User: Non-root `appuser` (UID 1000)
   - Entrypoint: `uvicorn semrush_api.main:app --host 0.0.0.0 --port 8000`
   - Health check: `curl http://localhost:8000/health` every 30s
   - Exposed: Port 8000

**Features:**
- Non-root user execution (security hardening)
- Proper virtual environment setup
- Health check for orchestration
- Small image size via slim base
- Production-ready with zero debugging tools

### Configuration Files

#### `/infra/clickhouse/init.sql`
ClickHouse initialization SQL executed on startup:

- Creates `openahrush` database
- Creates `commoncrawl_ingest_metadata` table for tracking ingestion progress
- Creates `commoncrawl_domain_stats` table for domain-level statistics
- Placeholder for full schema (populated during Common Crawl implementation)

#### `/.env.example`
Comprehensive environment template with 60+ configuration options:

**Required for basic setup:**
- `DATABASE_URL`: PostgreSQL connection
- `REDIS_URL`: Redis connection
- `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY/S3_BUCKET`: Object storage
- `JWT_SECRET`: Token signing key
- `ENCRYPTION_KEY`: At-rest encryption

**Optional integrations:**
- Google OAuth credentials
- ClickHouse connection
- Email/SMTP settings
- Feature flags
- Monitoring (Sentry, OpenTelemetry)

**Copy and customize:**
```bash
cp .env.example .env
# Edit .env with your values
```

## Development Scripts

All scripts provide comprehensive help with `--help`:

```bash
./scripts/dev.sh help     # All dev commands
./scripts/lint.sh --help  # Linting options
./scripts/test.sh --help  # Testing options
```

### `scripts/dev.sh` - Docker Environment Management

**Usage:** `./scripts/dev.sh <command> [options]`

**Core Commands:**
- `up` - Start all services (postgres, redis, minio, api)
- `down` - Stop all services
- `restart` - Stop and restart all services
- `logs [service]` - Stream logs (all or specific service)
- `ps` - Show container status
- `status` - Show detailed health status

**Container Access:**
- `shell` - Open bash in API container
- `db-shell` - Open psql in Postgres container
- `redis-cli` - Open Redis CLI

**Database Operations:**
- `migrate` - Run pending Alembic migrations
- `migrate-downgrade` - Rollback to previous migration

**ClickHouse Support:**
- `up-clickhouse` - Start with ClickHouse overlay
- `down-clickhouse` - Stop services with ClickHouse

**Maintenance:**
- `clean` - Remove stopped containers and networks
- `clean-hard` - Remove all containers, volumes, and data (DESTRUCTIVE)
- `rebuild` - Rebuild API image without cache
- `env-setup` - Initialize .env from .env.example

**Examples:**
```bash
# Start development environment
./scripts/dev.sh up

# Watch API logs
./scripts/dev.sh logs api

# Open database shell
./scripts/dev.sh db-shell

# Run pending migrations
./scripts/dev.sh migrate

# Start with Common Crawl (ClickHouse)
./scripts/dev.sh up-clickhouse

# Completely reset environment
./scripts/dev.sh clean-hard
./scripts/dev.sh up
```

### `scripts/lint.sh` - Code Quality Checks

**Usage:** `./scripts/lint.sh [options]`

Runs three quality gates:
1. **Ruff linting** - Python style, security, performance rules
2. **Ruff format check** - Code formatting validation
3. **MyPy type checking** - Static type analysis

**All checks must pass in CI/CD pipeline.**

**Example:**
```bash
./scripts/lint.sh

# Output shows:
# - Ruff Linting: Checks for style and correctness
# - Ruff Format Check: Validates PEP 8 formatting
# - MyPy Type Checking: Validates Python type hints
# - Summary: Pass/fail with error counts
```

**To auto-fix formatting:**
```bash
uv run ruff format .
```

### `scripts/test.sh` - Test Execution

**Usage:** `./scripts/test.sh [options]`

**Options:**
- `--coverage` - Generate coverage report (default)
- `--html` - Generate HTML report (`test_results.html`)
- `--verbose` - Detailed output
- `--quiet` - Minimal output
- `--watch` - Watch mode (requires pytest-watch)
- `--unit` - Run only unit tests
- `--integration` - Run only integration tests
- `-x` - Stop on first failure
- `-k PATTERN` - Run tests matching pattern

**Examples:**
```bash
# Run all tests with coverage
./scripts/test.sh

# Run specific test
./scripts/test.sh -k test_login

# Watch mode
./scripts/test.sh --watch

# Unit tests only
./scripts/test.sh --unit
```

## Service Endpoints

### API Server
- **URL**: http://localhost:8000
- **Health**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

### MinIO Console
- **URL**: http://localhost:9001
- **Username**: minioadmin
- **Password**: minioadmin
- **Use for**: Browse and manage S3 objects

### PostgreSQL
- **Host**: localhost:5432
- **User**: semrush
- **Password**: semrush
- **Database**: semrush
- **Connect**: `psql -h localhost -U semrush -d semrush`

### Redis
- **Host**: localhost:6379
- **Connect**: `redis-cli -h localhost`
- **Monitor**: `redis-cli MONITOR`

### ClickHouse (with `up-clickhouse`)
- **HTTP UI**: http://localhost:8123
- **Native**: localhost:9000
- **User**: default
- **Password**: default

## Database Migrations

Migrations use Alembic and are executed via uv:

```bash
# Run pending migrations
./scripts/dev.sh migrate

# Or manually:
export DATABASE_URL="postgresql+psycopg://semrush:semrush@localhost:5432/semrush"
uv run --package semrush-core alembic -c migrations/alembic.ini upgrade head

# Create new migration
uv run --package semrush-core alembic -c migrations/alembic.ini revision --autogenerate -m "description"

# Rollback
uv run --package semrush-core alembic -c migrations/alembic.ini downgrade -1
```

## Environment Configuration

### Development Defaults
Configured in `docker-compose.yml` for local development:

```yaml
Database:     semrush:semrush@postgres:5432/semrush
Redis:        redis://redis:6379/0
MinIO:        minio:9000 (minioadmin/minioadmin)
JWT Secret:   dev-secret-key-change-in-production
Encryption:   dev-encryption-key-change-in-production
```

### Production Deployment
Update `compose/.env` with real credentials:

```bash
# Generate strong secrets
openssl rand -base64 32  # JWT_SECRET
openssl rand -base64 32  # ENCRYPTION_KEY

# Configure with real values
DATABASE_URL=postgresql+psycopg://user:pass@prod-db.example.com:5432/db
REDIS_URL=redis://prod-redis.example.com:6379/0
JWT_SECRET=<generated-secret>
ENCRYPTION_KEY=<generated-key>
```

## Common Tasks

### Start Development Environment
```bash
./scripts/dev.sh up
./scripts/dev.sh logs api  # Watch API startup
```

### Connect to Database
```bash
./scripts/dev.sh db-shell
```

### Inspect Objects in MinIO
```bash
# 1. Open MinIO console: http://localhost:9001
# 2. Login: minioadmin / minioadmin
# 3. Browse buckets and files

# Or use CLI:
aws s3api --endpoint-url http://localhost:9000 list-objects --bucket openahrush
```

### Monitor Redis
```bash
./scripts/dev.sh redis-cli
> MONITOR     # Watch all commands
> KEYS *      # List all keys
> INFO        # Server statistics
```

### View Application Logs
```bash
# API logs
./scripts/dev.sh logs api

# Postgres logs
./scripts/dev.sh logs postgres

# All services
./scripts/dev.sh logs
```

### Reset Everything
```bash
# Remove containers and volumes (DELETE DATA!)
./scripts/dev.sh clean-hard

# Start fresh
./scripts/dev.sh up
./scripts/dev.sh migrate
```

### Run Code Quality Checks
```bash
# All checks
./scripts/lint.sh

# Fix formatting
uv run ruff format .

# Run tests
./scripts/test.sh --coverage
```

## Troubleshooting

### Services Not Starting
```bash
# Check service status
./scripts/dev.sh status

# View detailed logs
./scripts/dev.sh logs api
./scripts/dev.sh logs postgres

# Rebuild container
./scripts/dev.sh rebuild
./scripts/dev.sh up
```

### Database Connection Errors
```bash
# Verify Postgres is healthy
docker compose ps postgres

# Check credentials in .env
cat .env | grep DATABASE_URL

# Connect directly
./scripts/dev.sh db-shell

# Reset database
./scripts/dev.sh clean
./scripts/dev.sh up
./scripts/dev.sh migrate
```

### Port Conflicts
Default ports: 8000 (API), 5432 (Postgres), 6379 (Redis), 9000/9001 (MinIO)

If ports are in use:
```bash
# Find what's using port 8000
lsof -i :8000

# Or modify docker-compose.yml to use different ports:
# ports:
#   - "8001:8000"  # Use 8001 instead
```

### Out of Disk Space
```bash
# Clean Docker system
docker system prune -a --volumes

# Or specifically clean Openahrush
./scripts/dev.sh clean-hard
```

### API Won't Start
```bash
# Check logs
./scripts/dev.sh logs api

# Rebuild without cache
./scripts/dev.sh rebuild

# Verify dependencies in container
docker exec openahrush-api uv pip list
```

## Docker Compose Commands Reference

Basic operations when not using `dev.sh`:

```bash
cd infra/compose

# Start services
docker compose -p openahrush up -d

# Stop services
docker compose -p openahrush down

# View logs
docker compose -p openahrush logs -f

# Run command in container
docker compose -p openahrush exec api bash

# Show container status
docker compose -p openahrush ps

# Remove volumes
docker compose -p openahrush down -v
```

## Security Considerations

### Development
- Default credentials are insecure and only for local development
- Never use dev secrets in production
- Enable SECURE_COOKIES in production
- Use TLS/HTTPS for all external connections

### Production Deployment
1. Generate strong cryptographic keys
2. Use managed database services (RDS, Cloud SQL)
3. Use managed Redis (ElastiCache, MemoryStore)
4. Use S3 or managed object storage
5. Implement network isolation (VPCs, security groups)
6. Use secrets management (AWS Secrets Manager, HashiCorp Vault)
7. Enable encryption at rest and in transit
8. Implement RBAC and authentication
9. Use non-root containers
10. Regular security audits and updates

## Next Steps

1. **Review Configuration**: Check `.env` and adjust for your environment
2. **Start Services**: `./scripts/dev.sh up`
3. **Run Migrations**: `./scripts/dev.sh migrate`
4. **Check Health**: `./scripts/dev.sh status`
5. **Browse API**: http://localhost:8000/docs
6. **Read Tests**: Review test structure in `apps/` and `libs/`
7. **Explore Codebase**: Start with `apps/api/main.py`

## File Locations

```
/Users/beckett/Projects/Openahrush/
├── Dockerfile                              # Multi-stage container image
├── .env.example                            # Environment template
├── infra/
│   ├── compose/
│   │   ├── docker-compose.yml              # Main services
│   │   └── docker-compose.clickhouse.yml   # Optional ClickHouse
│   └── clickhouse/
│       └── init.sql                        # ClickHouse initialization
├── scripts/
│   ├── dev.sh                              # Dev environment management
│   ├── lint.sh                             # Code quality checks
│   └── test.sh                             # Test execution
├── migrations/                             # Alembic migrations
├── apps/                                   # Application packages
├── libs/                                   # Shared libraries
└── INFRASTRUCTURE.md                       # This file
```

## Further Reading

- `ARCHITECTURE.md` - System design and data flows
- `BLUEPRINT-PRD-MVP.md` - Feature specifications
- `COMMONCRAWL_INGESTION.md` - Common Crawl integration
- `openapi.yaml` - Complete API specification
- `README.md` - Project overview
