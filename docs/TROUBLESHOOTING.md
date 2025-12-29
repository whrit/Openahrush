# Troubleshooting Guide

Common issues and their solutions when running Openahrush.

## Table of Contents

- [Startup Issues](#startup-issues)
- [Database Problems](#database-problems)
- [Integration Failures](#integration-failures)
- [Crawl Issues](#crawl-issues)
- [Performance Problems](#performance-problems)
- [Common Error Messages](#common-error-messages)

---

## Startup Issues

### API Won't Start

**Symptom:** Container exits immediately or health check fails

**Check logs:**
```bash
docker compose -f infra/compose/docker-compose.prod.yml logs api
```

**Common causes:**

#### 1. Missing environment variables

```
Error: DATABASE_URL is required
```

**Solution:**
```bash
# Verify .env file exists and is loaded
cat .env.prod | grep DATABASE_URL

# Ensure docker compose uses env file
docker compose -f infra/compose/docker-compose.prod.yml --env-file .env.prod config
```

#### 2. Database connection failed

```
could not connect to server: Connection refused
```

**Solution:**
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Test connection manually
docker compose exec postgres psql -U semrush -d semrush -c "SELECT 1;"

# Verify DATABASE_URL format
# Correct: postgresql+psycopg://user:pass@host:5432/db
# Wrong: postgresql://user:pass@host:5432/db (missing +psycopg)
```

#### 3. Invalid JWT secret

```
JWT_SECRET must be at least 32 characters
```

**Solution:**
```bash
# Generate new secret
openssl rand -base64 32

# Update .env.prod
JWT_SECRET=<generated-secret>

# Restart API
docker compose restart api
```

---

## Database Problems

### Migration Failures

**Symptom:** `Target database is not up to date`

**Solution:**
```bash
# Check current version
docker compose exec api alembic -c migrations/alembic.ini current

# Check for pending migrations
docker compose exec api alembic -c migrations/alembic.ini heads

# Apply all migrations
docker compose exec api alembic -c migrations/alembic.ini upgrade head
```

### Migration Stuck

**Symptom:** Migration hangs indefinitely

**Possible cause:** Another migration in progress or stale lock

**Solution:**
```bash
# Check for active sessions
docker compose exec postgres psql -U semrush -d semrush -c "
SELECT pid, state, query
FROM pg_stat_activity
WHERE datname = 'semrush';
"

# If migration is truly stuck, terminate the session
docker compose exec postgres psql -U semrush -d semrush -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'semrush'
  AND state = 'active'
  AND query LIKE '%alembic%';
"

# Re-run migration
docker compose exec api alembic -c migrations/alembic.ini upgrade head
```

### Connection Pool Exhausted

**Symptom:** `QueuePool limit of size X overflow Y reached`

**Solution:**
```bash
# Increase pool size (temporarily)
export DB_POOL_SIZE=50
export DB_MAX_OVERFLOW=100

# Restart API
docker compose restart api

# Investigate connection leaks
docker compose exec postgres psql -U semrush -d semrush -c "
SELECT count(*)
FROM pg_stat_activity
WHERE datname = 'semrush';
"

# Check for long-running queries
docker compose exec postgres psql -U semrush -d semrush -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - pg_stat_activity.query_start > interval '1 minute';
"
```

### Database Disk Full

**Symptom:** `ERROR: could not extend file: No space left on device`

**Solution:**
```bash
# Check disk usage
df -h

# Clean up old WAL files (if autovacuum not running)
docker compose exec postgres psql -U semrush -d semrush -c "CHECKPOINT;"

# Vacuum tables
docker compose exec postgres psql -U semrush -d semrush -c "VACUUM FULL;"

# Remove old crawl runs (if retention policy not working)
docker compose exec api python -c "
from semrush_workers.cleanup import cleanup_old_crawls
import asyncio
asyncio.run(cleanup_old_crawls(keep_last=5))
"
```

---

## Integration Failures

### OAuth Connection Failed

**Symptom:** Redirect to OAuth provider fails or returns error

#### Issue: redirect_uri_mismatch

**Solution:**
```bash
# Verify GOOGLE_REDIRECT_URI matches exactly in Google Console
# - Must include https:// (or http:// for dev)
# - Must match port if specified
# - No trailing slash

# Example:
GOOGLE_REDIRECT_URI=https://yourdomain.com/integrations/google/callback

# Update in Google Cloud Console:
# APIs & Services > Credentials > OAuth 2.0 Client ID > Authorized redirect URIs
```

#### Issue: invalid_client

**Solution:**
```bash
# Verify client ID and secret are correct
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET

# Check for extra whitespace or newlines
export GOOGLE_CLIENT_ID=$(echo $GOOGLE_CLIENT_ID | tr -d '[:space:]')
export GOOGLE_CLIENT_SECRET=$(echo $GOOGLE_CLIENT_SECRET | tr -d '[:space:]')

# Restart API
docker compose restart api
```

### Sync Failures

**Symptom:** `integration.sync_failed` event or stale data

**Check sync status:**
```bash
curl -X GET http://localhost:8000/integrations/accounts \
  -H "Authorization: Bearer YOUR_TOKEN"

# Look for last_sync_at and error fields
```

**Common causes:**

#### 1. Token expired

**Solution:**
```bash
# Re-authorize integration
# Navigate to UI or trigger OAuth flow again
curl -X POST http://localhost:8000/integrations/google/connect \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 2. API quota exceeded

```
Error: Rate limit exceeded (quota: queries per day)
```

**Solution:**
- Wait for quota reset (daily)
- Request quota increase in Google Cloud Console
- Reduce sync frequency: `integration_sync_frequency: weekly`

#### 3. Property access revoked

```
Error: User does not have sufficient permissions
```

**Solution:**
- Verify user still has access to property
- Re-authorize integration
- Check property ID is correct

---

## Crawl Issues

### Crawl Stuck in "Running" State

**Symptom:** Crawl status remains `running` for hours

**Solution:**
```bash
# Check worker logs
docker compose logs workers

# Check Redis queue
docker compose exec redis redis-cli
> LLEN crawl:queue
> LRANGE crawl:queue 0 -1

# Force complete stuck crawl (DANGEROUS)
docker compose exec api python -c "
from semrush_core.models import CrawlRun
from semrush_core.database import get_session
from uuid import UUID
import asyncio

async def fix_stuck_crawl():
    async with get_session() as db:
        crawl = await db.get(CrawlRun, UUID('YOUR-CRAWL-ID'))
        if crawl:
            crawl.status = 'failed'
            crawl.error_message = 'Manually marked as failed due to timeout'
            await db.commit()

asyncio.run(fix_stuck_crawl())
"
```

### Crawl Finds No Pages

**Symptom:** `pages_crawled: 0` after completion

**Possible causes:**

#### 1. Robots.txt blocks crawler

**Solution:**
```bash
# Test robots.txt
curl https://example.com/robots.txt

# Check if User-agent: * or Openahrush is blocked
# If blocked, set respect_robots: false in project settings (not recommended)
```

#### 2. Seed URL inaccessible

**Solution:**
```bash
# Test seed URL manually
curl -I https://example.com

# Check for redirects or errors
# Verify seed_url in project settings is correct
```

#### 3. Scope too restrictive

**Solution:**
```bash
# Check project settings
curl -X GET http://localhost:8000/projects/PROJECT_ID/settings \
  -H "Authorization: Bearer YOUR_TOKEN"

# Verify:
# - allowed_hosts includes domain
# - exclude_regexes doesn't exclude everything
# - include_regexes isn't too narrow
```

### High 4xx/5xx Error Rate

**Symptom:** Many pages with 404 or 500 status codes

**Solution:**
```bash
# Review crawl pages
curl -X GET "http://localhost:8000/crawls/CRAWL_ID/pages?status_code=404" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Common causes:
# - Broken internal links (fix in CMS)
# - Temporary server issues (re-crawl)
# - Authentication required (configure auth in crawler settings - future feature)
```

---

## Performance Problems

### Slow API Responses

**Symptom:** API requests take > 5 seconds

**Diagnosis:**
```bash
# Enable slow query logging
export ENABLE_SLOW_QUERY_LOGGING=true
export SLOW_QUERY_THRESHOLD=1000  # 1 second

# Restart API
docker compose restart api

# Check logs for slow queries
docker compose logs api | grep "Slow query"
```

**Solutions:**

#### 1. Missing database indexes

```sql
-- Check missing indexes
SELECT schemaname, tablename, attname
FROM pg_stats
WHERE schemaname = 'public'
  AND n_distinct > 100
ORDER BY n_distinct DESC;

-- Add indexes for common queries
CREATE INDEX idx_issues_severity ON issue_instances(severity);
CREATE INDEX idx_crawl_pages_url ON crawl_pages(url);
```

#### 2. Large result sets without pagination

**Solution:**
```bash
# Always use pagination
curl -X GET "http://localhost:8000/projects/PROJECT_ID/issues?page=1&page_size=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3. N+1 query problem

**Check code for:**
```python
# Bad: N+1 queries
for project in projects:
    sites = await get_sites(project.id)  # Query per project

# Good: Eager loading
projects = await db.execute(
    select(Project).options(selectinload(Project.sites))
)
```

### High Memory Usage

**Symptom:** Container killed (OOMKilled) or system swap usage high

**Check:**
```bash
# Monitor memory usage
docker stats

# Check container limits
docker inspect openahrush-api | grep -A 10 Memory
```

**Solutions:**

#### 1. Increase container memory

```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 4G  # Increase from 2G
```

#### 2. Reduce worker concurrency

```bash
# Reduce concurrent crawls
export MAX_CONCURRENT_CRAWLS=2

# Reduce crawler concurrency
# In project settings:
{
  "concurrency_html": 8,  # Reduce from 16
  "concurrency_js": 2     # Reduce from 4
}
```

#### 3. Memory leak investigation

```python
# Add memory profiling
import tracemalloc
tracemalloc.start()

# ... run code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

---

## Common Error Messages

### "Could not connect to server"

**Full error:** `could not connect to server: Connection refused`

**Cause:** Database not running or wrong host/port

**Solution:**
```bash
docker compose ps postgres  # Verify running
echo $DATABASE_URL          # Verify correct
```

### "Bucket does not exist"

**Full error:** `NoSuchBucket: The specified bucket does not exist`

**Solution:**
```bash
# Create bucket manually
docker compose exec api python -c "
from semrush_core.storage import ensure_bucket
import asyncio
asyncio.run(ensure_bucket())
"

# Or create in MinIO console
# http://localhost:9001 (minioadmin/minioadmin)
```

### "CSRF verification failed"

**Full error:** `Invalid state parameter`

**Cause:** OAuth state mismatch (cookie expired or browser cleared)

**Solution:**
- Restart OAuth flow from beginning
- Check SECURE_COOKIES setting matches HTTPS usage
- Verify browser allows cookies

### "Token has expired"

**Full error:** `401 Unauthorized: Token has expired`

**Solution:**
```bash
# Re-authenticate
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Get new access token
```

### "Resource already exists"

**Full error:** `409 Conflict: Email already registered`

**Solution:**
- Use different email
- Or login with existing account
- Or reset password (if feature implemented)

---

## Debug Mode

**Enable verbose logging:**

```bash
# .env.prod
DEBUG=true
LOG_LEVEL=debug

# Restart
docker compose restart api workers
```

**View all logs:**
```bash
docker compose logs -f --tail=100
```

**Filter by service:**
```bash
docker compose logs -f api
docker compose logs -f workers
docker compose logs -f postgres
```

---

## Health Checks

**Verify all services:**

```bash
# API
curl http://localhost:8000/health

# PostgreSQL
docker compose exec postgres pg_isready -U semrush

# Redis
docker compose exec redis redis-cli ping

# MinIO
curl http://localhost:9000/minio/health/live
```

**Expected:**
- API: `{"status":"healthy"}`
- PostgreSQL: `accepting connections`
- Redis: `PONG`
- MinIO: `200 OK`

---

## Getting More Help

1. **Check logs first:** `docker compose logs -f`
2. **Review configuration:** See [CONFIGURATION.md](/Users/beckett/Projects/Openahrush/docs/CONFIGURATION.md)
3. **Search issues:** https://github.com/yourusername/openahrush/issues
4. **Ask community:** Discord/Slack channel
5. **Create issue:** Include logs, config (redact secrets), steps to reproduce

**When reporting issues, include:**

```bash
# System info
docker --version
docker compose version
uname -a

# Service status
docker compose ps

# Recent logs
docker compose logs --tail=100 api

# Environment (REDACT SECRETS)
env | grep -E '^(ENVIRONMENT|DATABASE_URL|REDIS_URL)' | sed 's/:[^@]*@/:***@/'
```
