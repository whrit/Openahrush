# Openahrush Quick Start Guide

Get up and running in 5 minutes.

## Installation (One Time)

```bash
# Install Python 3.12 and Docker
# Then clone the repo and cd into it

# Copy environment file
cp .env.example .env

# Start all services
./scripts/dev.sh up

# Wait for services to be ready
./scripts/dev.sh status

# Run migrations
./scripts/dev.sh migrate
```

That's it! You now have:
- API at http://localhost:8000
- Postgres at localhost:5432
- Redis at localhost:6379
- MinIO console at http://localhost:9001

## Daily Development

```bash
# Start your day
./scripts/dev.sh up

# View logs
./scripts/dev.sh logs api

# Open database
./scripts/dev.sh db-shell

# Open container shell
./scripts/dev.sh shell

# Check code quality
./scripts/lint.sh

# Run tests
./scripts/test.sh

# End your day
./scripts/dev.sh down
```

## Important Endpoints

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| MinIO | http://localhost:9001 | minioadmin/minioadmin |
| Postgres | localhost:5432 | semrush/semrush |
| Redis | localhost:6379 | - |

## Useful Commands

```bash
# View all available commands
./scripts/dev.sh help

# Watch logs in real-time
./scripts/dev.sh logs api

# Open bash in container
./scripts/dev.sh shell

# Run database migrations
./scripts/dev.sh migrate

# Rollback migration
./scripts/dev.sh migrate-downgrade

# Restart everything
./scripts/dev.sh restart

# Clean everything (delete data!)
./scripts/dev.sh clean-hard
```

## Common With ClickHouse

For Common Crawl features:

```bash
# Start with ClickHouse
./scripts/dev.sh up-clickhouse

# Stop with ClickHouse
./scripts/dev.sh down-clickhouse

# Access ClickHouse
# HTTP: http://localhost:8123
# User: default / default
```

## Troubleshooting

**API won't start?**
```bash
./scripts/dev.sh logs api
```

**Database error?**
```bash
./scripts/dev.sh db-shell
# Then run SQL queries
```

**Port already in use?**
```bash
# Find what's using it
lsof -i :8000

# Reset everything
./scripts/dev.sh clean-hard
./scripts/dev.sh up
```

**Need to reset data?**
```bash
./scripts/dev.sh clean-hard
./scripts/dev.sh up
./scripts/dev.sh migrate
```

## Next Steps

1. Read `INFRASTRUCTURE.md` for detailed setup
2. Read `ARCHITECTURE.md` for system design
3. Check `openapi.yaml` for API endpoints
4. Look at `apps/api/` to understand the codebase

## Resources

- Full docs: `INFRASTRUCTURE.md`
- Architecture: `ARCHITECTURE.md`
- API spec: `openapi.yaml`
- Common Crawl: `COMMONCRAWL_INGESTION.md`
- Feature list: `BLUEPRINT-PRD-MVP.md`
