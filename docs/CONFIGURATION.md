# Configuration Reference

Complete reference for all Openahrush configuration options via environment variables and project settings.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Project Settings](#project-settings)
- [Integration Configuration](#integration-configuration)
- [Security Configuration](#security-configuration)
- [Performance Tuning](#performance-tuning)

---

## Environment Variables

### Core Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | Environment: `development`, `staging`, `production` |
| `DEBUG` | No | `false` | Enable debug mode (verbose logging, API docs) |
| `LOG_LEVEL` | No | `info` | Logging level: `debug`, `info`, `warning`, `error` |
| `API_HOST` | No | `0.0.0.0` | API server bind address |
| `API_PORT` | No | `8000` | API server port |
| `APP_NAME` | No | `Openahrush` | Application name |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed CORS origins |

**Example:**
```bash
ENVIRONMENT=production
LOG_LEVEL=info
CORS_ORIGINS=https://app.example.com,https://www.example.com
```

### Database (PostgreSQL)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | **Yes** | - | PostgreSQL connection string |
| `DB_POOL_SIZE` | No | `20` | Connection pool size |
| `DB_MAX_OVERFLOW` | No | `40` | Max overflow connections |
| `DB_ECHO` | No | `false` | Log SQL queries (debug only) |

**Format:**
```bash
DATABASE_URL=postgresql+psycopg://user:password@host:port/database

# Examples:
# Local: postgresql+psycopg://semrush:semrush@localhost:5432/semrush
# Docker: postgresql+psycopg://semrush:semrush@postgres:5432/semrush
```

**SSL Support:**
```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db?sslmode=require
```

### Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | **Yes** | - | Redis connection string |
| `REDIS_MAX_CONNECTIONS` | No | `50` | Connection pool size |

**Format:**
```bash
REDIS_URL=redis://[:password]@host:port/db

# Examples:
# Local: redis://localhost:6379/0
# Docker: redis://redis:6379/0
# With password: redis://:mypassword@redis:6379/0
```

### Object Storage (MinIO/S3)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MINIO_ENDPOINT` | **Yes** | - | MinIO/S3 endpoint URL |
| `MINIO_ACCESS_KEY` | **Yes** | - | Access key (username) |
| `MINIO_SECRET_KEY` | **Yes** | - | Secret key (password) |
| `S3_BUCKET` | **Yes** | `openahrush` | Bucket name |
| `AWS_REGION` | No | `us-east-1` | AWS region (for S3 compatibility) |
| `MINIO_SECURE` | No | `false` | Use HTTPS for MinIO |

**MinIO (self-hosted):**
```bash
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=strong-secret-key
S3_BUCKET=openahrush
```

**AWS S3:**
```bash
MINIO_ENDPOINT=https://s3.amazonaws.com
MINIO_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
MINIO_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_BUCKET=my-openahrush-bucket
AWS_REGION=us-west-2
MINIO_SECURE=true
```

### Security

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | **Yes** | - | Secret for JWT signing (min 32 chars) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Access token expiration (minutes) |
| `ENCRYPTION_KEY` | **Yes** | - | Fernet encryption key for sensitive data |
| `SECURE_COOKIES` | No | `false` | Use secure cookies (HTTPS only) |

**Generate secrets:**
```bash
# JWT secret
openssl rand -base64 32

# Encryption key (Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Example:**
```bash
JWT_SECRET=Kw8xF3nH2vL9pR4qT7yU1mN6bV0cX5zS8jG3dA2wE4fI6hK9lO
ENCRYPTION_KEY=3q7nF2kP9mT5xW8bC4vN0zR6jL1yH3dS7aG9fE2wQ5uI8oK=
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Google OAuth

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLIENT_ID` | For GSC/GA4 | - | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For GSC/GA4 | - | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | For GSC/GA4 | - | OAuth callback URL |

**Obtain from:** [Google Cloud Console](https://console.cloud.google.com/)

**Example:**
```bash
GOOGLE_CLIENT_ID=123456789-abcdefgh.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-aBcDeFgHiJkLmNoPqRsTuVwXyZ
GOOGLE_REDIRECT_URI=https://yourdomain.com/integrations/google/callback
```

### Microsoft OAuth

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MICROSOFT_CLIENT_ID` | For BWT | - | Microsoft OAuth client ID |
| `MICROSOFT_CLIENT_SECRET` | For BWT | - | Microsoft OAuth client secret |
| `MICROSOFT_REDIRECT_URI` | For BWT | - | OAuth callback URL |
| `MICROSOFT_TENANT_ID` | No | `common` | Azure AD tenant ID |

### ClickHouse (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLICKHOUSE_URL` | For CC | - | ClickHouse HTTP endpoint |
| `CLICKHOUSE_DATABASE` | For CC | `openahrush` | Database name |
| `CLICKHOUSE_USER` | No | `default` | Username |
| `CLICKHOUSE_PASSWORD` | No | - | Password |

**Example:**
```bash
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_DATABASE=openahrush
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=strong-password
```

### Email (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | For email | - | SMTP server hostname |
| `SMTP_PORT` | For email | `587` | SMTP server port |
| `SMTP_USER` | For email | - | SMTP username |
| `SMTP_PASSWORD` | For email | - | SMTP password |
| `SMTP_TLS` | No | `true` | Use TLS |
| `MAIL_FROM` | For email | - | Sender email address |
| `ENABLE_EMAIL_NOTIFICATIONS` | No | `false` | Enable email notifications |

### Crawler Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEFAULT_CRAWL_DEPTH` | No | `3` | Default max crawl depth |
| `MAX_CONCURRENT_CRAWLS` | No | `5` | Max concurrent crawls per project |
| `CRAWL_REQUEST_TIMEOUT` | No | `30` | HTTP request timeout (seconds) |
| `USE_PLAYWRIGHT_FALLBACK` | No | `false` | Enable Playwright for JS rendering |
| `USER_AGENT` | No | `Openahrush/0.1.0` | Default crawler user agent |

### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FEATURE_COMMONCRAWL_INGEST` | No | `true` | Enable Common Crawl ingestion |
| `FEATURE_GSC_INTEGRATION` | No | `true` | Enable Google Search Console |
| `FEATURE_GA4_INTEGRATION` | No | `true` | Enable Google Analytics 4 |
| `FEATURE_BWT_INTEGRATION` | No | `true` | Enable Bing Webmaster Tools |
| `FEATURE_BACKLINK_ANALYSIS` | No | `true` | Enable backlink features |
| `ENABLE_API_DOCS` | No | `true` (dev) | Enable /docs and /redoc |
| `ENABLE_ADMIN_ENDPOINTS` | No | `false` | Enable admin-only endpoints |

### Monitoring (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTRY_DSN` | No | - | Sentry error tracking DSN |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | - | OpenTelemetry collector endpoint |
| `ENABLE_REQUEST_LOGGING` | No | `true` | Log HTTP requests |
| `ENABLE_SLOW_QUERY_LOGGING` | No | `true` | Log slow database queries |
| `SLOW_QUERY_THRESHOLD` | No | `1000` | Slow query threshold (ms) |

---

## Project Settings

Configured via `PUT /projects/{id}/settings` endpoint.

### Crawl Scope

```json
{
  "seed_url": "https://example.com",
  "include_subdomains": true,
  "allowed_hosts": ["example.com", "www.example.com", "blog.example.com"],
  "allowed_schemes": ["https", "http"],
  "include_regexes": ["/blog/.*", "/products/.*"],
  "exclude_regexes": ["/admin/.*", "/wp-admin/.*", ".*\\.pdf$"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `seed_url` | string | Required | Starting URL for crawls |
| `include_subdomains` | boolean | `true` | Crawl subdomains |
| `allowed_hosts` | array | Derived | Explicit host allowlist |
| `allowed_schemes` | array | `["https","http"]` | URL schemes to crawl |
| `include_regexes` | array | `[]` | Include URL patterns |
| `exclude_regexes` | array | `[]` | Exclude URL patterns |

### URL Normalization

```json
{
  "query_param_policy": "strip_tracking",
  "query_param_allowlist": ["id", "page"],
  "query_param_denylist": ["utm_source", "fbclid"],
  "strip_tracking_params": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query_param_policy` | enum | `strip_tracking` | `allow_all`, `strip_all`, `allowlist`, `denylist` |
| `query_param_allowlist` | array | `[]` | Params to keep (if policy=`allowlist`) |
| `query_param_denylist` | array | `[]` | Params to remove (if policy=`denylist`) |
| `strip_tracking_params` | boolean | `true` | Auto-remove common tracking params |

**Tracking params auto-removed:**
- `utm_*` (Google Analytics)
- `gclid`, `fbclid` (ad platforms)
- `ref`, `source` (generic referrers)

### Crawl Budgets

```json
{
  "max_pages": 10000,
  "max_depth": 5,
  "concurrency_html": 16,
  "politeness_delay_ms": 1000,
  "respect_robots": true,
  "use_sitemaps": true,
  "user_agent": "Openahrush/0.1.0 (+https://openahrush.org)"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_pages` | integer | `10000` | Max pages to crawl per run |
| `max_depth` | integer | `5` | Max link depth from seed |
| `concurrency_html` | integer | `16` | Concurrent HTML fetches |
| `politeness_delay_ms` | integer | `1000` | Delay between requests to same host |
| `respect_robots` | boolean | `true` | Respect robots.txt |
| `use_sitemaps` | boolean | `true` | Discover URLs from sitemaps |
| `user_agent` | string | Auto | Custom user agent |

### Hybrid JS Rendering

```json
{
  "js_render_mode": "hybrid",
  "max_rendered_pages": 200,
  "max_render_time_ms": 15000,
  "concurrency_js": 4,
  "js_required_selectors": ["#app", "main"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `js_render_mode` | enum | `hybrid` | `off`, `hybrid`, `js_only` |
| `max_rendered_pages` | integer | `200` | Max pages to render per run |
| `max_render_time_ms` | integer | `15000` | Timeout per page render |
| `concurrency_js` | integer | `4` | Concurrent Playwright instances |
| `js_required_selectors` | array | `[]` | Selectors that trigger JS render |

**Hybrid heuristics:**
- Thin DOM (< 200 chars text)
- SPA shell detected
- Required selectors missing
- Meta/canonical missing

### Schedules and Retention

```json
{
  "audit_frequency": "weekly",
  "integration_sync_frequency": "daily",
  "visibility_refresh_frequency": "daily",
  "links_refresh_frequency": "monthly",
  "retain_audit_runs": 10,
  "retain_serp_snapshots_days": 90,
  "retain_raw_html_days": 30
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audit_frequency` | enum | `weekly` | `off`, `daily`, `weekly` |
| `integration_sync_frequency` | enum | `daily` | `daily`, `weekly` |
| `visibility_refresh_frequency` | enum | `daily` | `daily`, `weekly` |
| `links_refresh_frequency` | enum | `monthly` | `weekly`, `monthly` |
| `retain_audit_runs` | integer | `10` | Keep last N crawl runs |
| `retain_serp_snapshots_days` | integer | `90` | Days to keep SERP data |
| `retain_raw_html_days` | integer | `30` | Days to keep HTML artifacts |

---

## Integration Configuration

### Google Search Console

**Scopes required:**
- `https://www.googleapis.com/auth/webmasters.readonly`

**Data synced:**
- Query performance (daily)
- Page performance (daily)
- Sitemaps
- Manual actions

**Rate limits:**
- 600 requests per minute per project
- Use batch requests for efficiency

### Google Analytics 4

**Scopes required:**
- `https://www.googleapis.com/auth/analytics.readonly`

**Dimensions:**
- Date, page path, source/medium, device category

**Metrics:**
- Sessions, users, engagement time, conversions

**Sampling:**
- Data may be sampled for large date ranges
- Check `data_quality_flags` in synced facts

### Bing Webmaster Tools

**API key required:** Generate in BWT settings

**Data synced:**
- Query performance
- Crawl stats
- Backlinks (limited)

---

## Security Configuration

### JWT Configuration

```bash
JWT_SECRET=<min-32-chars>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_ALGORITHM=HS256  # Hardcoded, not configurable
```

**Token structure:**
```json
{
  "sub": "user-uuid",
  "scopes": ["user"],
  "exp": 1640000000
}
```

### Encryption

Uses Fernet (AES-128-CBC):

```bash
ENCRYPTION_KEY=<32-byte-base64-encoded>
```

**Encrypted fields:**
- Integration access tokens
- Integration refresh tokens
- Webhook secrets

### Password Hashing

- Algorithm: bcrypt
- Cost factor: 12 (hardcoded)
- Min password length: 8 characters

### CORS

```bash
CORS_ORIGINS=https://app.example.com,https://www.example.com
```

**Wildcard (development only):**
```bash
CORS_ORIGINS=*
```

---

## Performance Tuning

### Database

**Connection pool:**
```bash
DB_POOL_SIZE=20          # Connections kept alive
DB_MAX_OVERFLOW=40       # Extra connections when pool exhausted
```

**Recommendations:**
- Small (< 10 users): `POOL_SIZE=10`, `MAX_OVERFLOW=20`
- Medium (10-100 users): `POOL_SIZE=20`, `MAX_OVERFLOW=40`
- Large (100+ users): `POOL_SIZE=50`, `MAX_OVERFLOW=100`

**Query optimization:**
- Enable `ENABLE_SLOW_QUERY_LOGGING=true`
- Set `SLOW_QUERY_THRESHOLD=500` (ms) for stricter logging
- Use `DB_ECHO=true` in development to see queries

### Redis

```bash
REDIS_MAX_CONNECTIONS=50
```

**Tune based on job volume:**
- Light workload: 20 connections
- Medium: 50 connections
- Heavy: 100+ connections

### Crawler

```bash
CRAWL_REQUEST_TIMEOUT=30           # HTTP timeout
DEFAULT_CRAWL_DEPTH=3             # Max depth
MAX_CONCURRENT_CRAWLS=5           # Concurrent crawls per project
```

**Project settings:**
```json
{
  "concurrency_html": 16,         // Concurrent fetches
  "politeness_delay_ms": 1000,    // Delay between requests
  "max_pages": 10000              // Total page limit
}
```

**Throughput calculation:**
```
pages_per_minute = concurrency_html * (60000 / politeness_delay_ms)
Example: 16 * (60000 / 1000) = 960 pages/minute
```

### ClickHouse

**For large Common Crawl datasets:**

```sql
-- Tune merge settings
SET max_insert_block_size = 1000000;
SET min_insert_block_size_rows = 100000;

-- Use async inserts
SET async_insert = 1;
SET wait_for_async_insert = 0;
```

---

## Configuration Validation

**Startup checks:**

```python
# semrush_core/config.py validates:
- DATABASE_URL format and connectivity
- REDIS_URL connectivity
- JWT_SECRET length (min 32 chars)
- ENCRYPTION_KEY format (Fernet)
- S3_BUCKET existence
```

**Manual validation:**

```bash
# Test database connection
docker compose exec api python -c "
from semrush_core.database import get_engine
import asyncio
asyncio.run(get_engine().connect())
"

# Test Redis connection
docker compose exec api python -c "
import redis
from semrush_core import get_settings
r = redis.from_url(get_settings().redis_url)
r.ping()
"

# Test MinIO/S3
docker compose exec api python -c "
from semrush_core.storage import ensure_bucket
import asyncio
asyncio.run(ensure_bucket())
"
```

---

## Configuration Examples

### Development

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=debug
DATABASE_URL=postgresql+psycopg://semrush:semrush@localhost:5432/semrush
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=dev-secret-key-change-in-production
ENCRYPTION_KEY=dev-encryption-key-change-in-production
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
S3_BUCKET=openahrush
CORS_ORIGINS=*
ENABLE_API_DOCS=true
```

### Production

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
DATABASE_URL=postgresql+psycopg://semrush:STRONG_PASSWORD@postgres:5432/semrush?sslmode=require
REDIS_URL=redis://:REDIS_PASSWORD@redis:6379/0
JWT_SECRET=<generated-32-char-secret>
ENCRYPTION_KEY=<generated-fernet-key>
MINIO_ENDPOINT=https://s3.amazonaws.com
MINIO_ACCESS_KEY=<aws-access-key>
MINIO_SECRET_KEY=<aws-secret-key>
S3_BUCKET=prod-openahrush
AWS_REGION=us-west-2
MINIO_SECURE=true
CORS_ORIGINS=https://app.example.com
SECURE_COOKIES=true
ENABLE_API_DOCS=false
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=https://app.example.com/integrations/google/callback
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_PASSWORD=<strong-password>
SENTRY_DSN=<your-sentry-dsn>
```

---

## Troubleshooting Configuration

**Issue:** `Could not connect to database`

**Solution:**
```bash
# Check DATABASE_URL format
echo $DATABASE_URL

# Test connection
psql "$DATABASE_URL"
```

**Issue:** `Invalid encryption key`

**Solution:**
```bash
# Generate valid Fernet key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Issue:** `JWT secret too short`

**Solution:**
```bash
# Generate 32+ character secret
openssl rand -base64 32
```

For more troubleshooting, see [TROUBLESHOOTING.md](/Users/beckett/Projects/Openahrush/docs/TROUBLESHOOTING.md).
