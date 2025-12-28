# Sprint 5: Hardening & Polish

**Duration:** 1-2 weeks
**Dependencies:** Sprints 0-4 (All previous)
**Status:** Not Started

This sprint focuses on production readiness: rate limiting, security hardening, performance optimization, testing, and documentation.

---

## Objectives

1. Implement rate limiting and resource caps
2. Conduct security audit and fixes
3. Optimize performance bottlenecks
4. Build comprehensive test suite
5. Complete documentation
6. Prepare deployment configurations

---

## Epic 5.1: Rate Limiting & Resource Caps

### Task 5.1.1: Implement API rate limiting

**Description:** Add rate limiting to prevent abuse.

**Acceptance Criteria:**
- [ ] Rate limiting middleware for FastAPI
- [ ] Configurable limits per endpoint category
- [ ] Token bucket or sliding window algorithm
- [ ] Redis-backed for distributed limiting
- [ ] Returns 429 Too Many Requests when exceeded
- [ ] X-RateLimit-* headers in responses

**Rate Limits (MVP defaults):**
| Category | Limit |
|----------|-------|
| Auth | 5/min |
| Crawl triggers | 10/hour |
| Export triggers | 20/hour |
| API reads | 100/min |
| Webhook config | 10/min |

**Implementation:**
```python
from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.post("/projects/{id}/crawls")
@limiter.limit("10/hour")
async def trigger_crawl(project_id: UUID, request: Request):
    ...
```

---

### Task 5.1.2: Implement concurrent job caps

**Description:** Limit concurrent jobs per project.

**Acceptance Criteria:**
- [ ] Max 1 concurrent crawl per project
- [ ] Max 3 concurrent exports per project
- [ ] Max 1 concurrent CC ingestion globally (admin)
- [ ] Returns 409 Conflict if cap exceeded
- [ ] Redis-based lock management

---

### Task 5.1.3: Implement resource budget enforcement

**Description:** Enforce project-level resource budgets.

**Acceptance Criteria:**
- [ ] Track monthly crawl page budget
- [ ] Track monthly export count
- [ ] Warn at 80% usage
- [ ] Block at 100% usage
- [ ] Admin can override limits

**Budget Tracking:**
```sql
CREATE TABLE resource_usage (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    month DATE NOT NULL,  -- First day of month
    crawl_pages_used INTEGER DEFAULT 0,
    exports_used INTEGER DEFAULT 0,
    UNIQUE(project_id, month)
);
```

---

### Task 5.1.4: Implement timeout enforcement

**Description:** Kill long-running jobs.

**Acceptance Criteria:**
- [ ] Crawl timeout: 4 hours max
- [ ] Export timeout: 30 minutes max
- [ ] Render timeout: per-page from settings
- [ ] Job marked as failed with timeout error
- [ ] Worker process cleanup

---

## Epic 5.2: Security Hardening

### Task 5.2.1: Security audit and fixes

**Description:** Audit codebase for security vulnerabilities.

**Audit Areas:**
- [ ] SQL injection (parameterized queries everywhere)
- [ ] XSS in PDF reports (HTML escaping)
- [ ] SSRF in webhook URLs (allowlist/blocklist)
- [ ] Path traversal in exports
- [ ] Secrets in logs (redaction)
- [ ] Token storage encryption verification

**Fixes Required:**
- [ ] Validate webhook URLs (no internal IPs)
- [ ] Sanitize user input in templates
- [ ] Rotate encryption keys support
- [ ] Audit log for sensitive operations

---

### Task 5.2.2: Implement webhook URL validation

**Description:** Prevent SSRF via webhook URLs.

**Acceptance Criteria:**
- [ ] Block private IP ranges (10.x, 172.16-31.x, 192.168.x)
- [ ] Block localhost and loopback
- [ ] Block internal DNS names
- [ ] Optional: require HTTPS only
- [ ] DNS resolution check before saving

**Implementation:**
```python
import ipaddress

BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

def validate_webhook_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    # Resolve hostname
    try:
        ip = socket.gethostbyname(parsed.hostname)
    except socket.gaierror:
        return False

    # Check against blocked networks
    ip_obj = ipaddress.ip_address(ip)
    for network in BLOCKED_NETWORKS:
        if ip_obj in network:
            return False

    return True
```

---

### Task 5.2.3: Implement audit logging

**Description:** Log security-sensitive operations.

**Acceptance Criteria:**
- [ ] Log: login attempts (success/failure)
- [ ] Log: integration connect/disconnect
- [ ] Log: project create/delete
- [ ] Log: export downloads
- [ ] Log: webhook changes
- [ ] Store in database or external log system
- [ ] Include user_id, action, timestamp, details

**Schema:**
```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action, created_at DESC);
```

---

### Task 5.2.4: Implement secret redaction in logs

**Description:** Prevent secrets from appearing in logs.

**Acceptance Criteria:**
- [ ] Redact tokens in log messages
- [ ] Redact passwords and secrets
- [ ] Redact webhook secrets
- [ ] Custom logging formatter
- [ ] Test coverage for redaction

---

## Epic 5.3: Performance Optimization

### Task 5.3.1: Database query optimization

**Description:** Identify and fix slow queries.

**Acceptance Criteria:**
- [ ] Enable query logging in development
- [ ] Identify N+1 queries
- [ ] Add missing indexes based on EXPLAIN
- [ ] Use connection pooling (asyncpg)
- [ ] Batch reads for list endpoints

**Common Optimizations:**
- Add composite indexes for common filters
- Use LIMIT/OFFSET or keyset pagination
- Eager load relationships where needed
- Cache frequently-read configs

---

### Task 5.3.2: Implement response caching

**Description:** Cache expensive API responses.

**Acceptance Criteria:**
- [ ] Redis cache for read-heavy endpoints
- [ ] Cache key includes: endpoint, project_id, params hash
- [ ] TTL based on data freshness requirements
- [ ] Cache invalidation on data changes
- [ ] Cache headers for client-side caching

**Cache Candidates:**
| Endpoint | TTL |
|----------|-----|
| GET /projects/{id}/issues | 5 min |
| GET /links/domain/{}/refdomains | 1 hour |
| GET /commoncrawl/snapshots | 1 hour |

---

### Task 5.3.3: Optimize crawl performance

**Description:** Improve crawl throughput.

**Acceptance Criteria:**
- [ ] Profile crawl bottlenecks
- [ ] Optimize HTML parsing (selectolax vs lxml)
- [ ] Batch database inserts (100+ rows)
- [ ] Use uvloop for async performance
- [ ] Connection pooling for fetcher

---

### Task 5.3.4: Optimize Common Crawl ingestion

**Description:** Improve CC ingestion speed.

**Acceptance Criteria:**
- [ ] Parallel WAT file processing
- [ ] Batch inserts to storage (10K+ rows)
- [ ] Stream processing (don't buffer full files)
- [ ] Use ClickHouse async inserts if applicable
- [ ] Progress checkpointing for resume

---

## Epic 5.4: Testing

### Task 5.4.1: Unit test coverage

**Description:** Add unit tests for core logic.

**Acceptance Criteria:**
- [ ] Test coverage > 80% for libs/
- [ ] Test coverage > 70% for apps/
- [ ] All rules have test cases
- [ ] URL normalization fully tested
- [ ] Encryption/decryption tested

**Test Structure:**
```
libs/core/tests/
├── test_models.py
├── test_encryption.py
└── test_config.py

apps/api/tests/
├── test_auth.py
├── test_projects.py
└── test_health.py
```

---

### Task 5.4.2: Integration tests

**Description:** Test component interactions.

**Acceptance Criteria:**
- [ ] OAuth flow integration tests
- [ ] Crawl pipeline end-to-end test
- [ ] Export generation tests
- [ ] Webhook delivery tests
- [ ] Uses test database (separate from dev)
- [ ] Runs in CI

---

### Task 5.4.3: End-to-end tests

**Description:** Full workflow tests.

**Acceptance Criteria:**
- [ ] Create project → add site → run crawl → view issues
- [ ] Connect integration → sync → view performance
- [ ] Trigger export → download file
- [ ] Configure webhook → receive delivery
- [ ] Uses Playwright or similar for API testing

---

### Task 5.4.4: Load testing

**Description:** Verify system under load.

**Acceptance Criteria:**
- [ ] API handles 100 concurrent requests
- [ ] Crawl engine handles target page rate
- [ ] Export generation doesn't block API
- [ ] Webhook delivery at target rate
- [ ] Document performance baselines

**Tools:** k6, locust, or wrk

---

## Epic 5.5: Documentation

### Task 5.5.1: API documentation

**Description:** Complete OpenAPI documentation.

**Acceptance Criteria:**
- [ ] All endpoints have descriptions
- [ ] Request/response examples
- [ ] Error responses documented
- [ ] Authentication documented
- [ ] Served at /docs (Swagger UI)

---

### Task 5.5.2: Deployment documentation

**Description:** Document deployment process.

**Acceptance Criteria:**
- [ ] Docker Compose production config
- [ ] Environment variable reference
- [ ] Database migration instructions
- [ ] Backup/restore procedures
- [ ] Monitoring setup guide

**Docs to Create:**
```
docs/
├── DEPLOYMENT.md
├── CONFIGURATION.md
├── OPERATIONS.md
└── TROUBLESHOOTING.md
```

---

### Task 5.5.3: User documentation

**Description:** Document user-facing features.

**Acceptance Criteria:**
- [ ] Getting started guide
- [ ] Integration setup guides (GSC, GA4, BWT)
- [ ] Crawl configuration guide
- [ ] Export and report guide
- [ ] Webhook integration guide

---

### Task 5.5.4: Developer documentation

**Description:** Document codebase for contributors.

**Acceptance Criteria:**
- [ ] Architecture overview
- [ ] Development setup guide
- [ ] Adding new rules guide
- [ ] Adding new integrations guide
- [ ] Code style guide
- [ ] Contributing guidelines

---

## Epic 5.6: Deployment Preparation

### Task 5.6.1: Production Docker Compose

**Description:** Create production-ready Docker configuration.

**Acceptance Criteria:**
- [ ] Separate docker-compose.prod.yml
- [ ] Resource limits on containers
- [ ] Health checks on all services
- [ ] Restart policies
- [ ] Log rotation
- [ ] No development defaults

---

### Task 5.6.2: Environment configuration

**Description:** Document and validate environment setup.

**Acceptance Criteria:**
- [ ] .env.example with all variables
- [ ] Validation on startup (fail fast)
- [ ] Secrets never logged
- [ ] Separate dev/prod defaults

**Environment Variables:**
```bash
# Required
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
JWT_SECRET=<generate-strong-secret>
ENCRYPTION_KEY=<fernet-key>

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
S3_BUCKET=openahrush

# Optional
CLICKHOUSE_URL=clickhouse://...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

---

### Task 5.6.3: Health and monitoring endpoints

**Description:** Complete health monitoring setup.

**Acceptance Criteria:**
- [ ] /healthz (liveness) - always fast
- [ ] /readyz (readiness) - checks dependencies
- [ ] /metrics (Prometheus format) - optional
- [ ] Log structured JSON in production
- [ ] Request tracing headers

**Metrics to Export (Optional):**
- Request count/latency by endpoint
- Job queue depth
- Active crawls
- Database connection pool stats

---

### Task 5.6.4: Database migrations for production

**Description:** Ensure migrations work in production.

**Acceptance Criteria:**
- [ ] Migrations are idempotent
- [ ] Rollback scripts for each migration
- [ ] Migration runs before app starts
- [ ] Handles concurrent migrations safely
- [ ] Tested on fresh database

---

## Verification Checklist

### Security
- [ ] No SQL injection vulnerabilities
- [ ] Tokens encrypted at rest
- [ ] Webhook URLs validated
- [ ] Secrets not in logs
- [ ] Audit logging works

### Performance
- [ ] API response time < 200ms (p95)
- [ ] Crawl throughput meets target
- [ ] No N+1 queries in hot paths
- [ ] Caching reduces database load

### Testing
- [ ] Unit test coverage > 70%
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Load tests meet targets

### Documentation
- [ ] API docs complete
- [ ] Deployment docs complete
- [ ] User guides complete
- [ ] Developer docs complete

### Deployment
- [ ] Production compose works
- [ ] Environment validated
- [ ] Health checks pass
- [ ] Migrations run cleanly

---

## Notes

### Production Checklist

Before deploying to production:

1. **Secrets:**
   - Generate strong JWT_SECRET (32+ bytes)
   - Generate Fernet ENCRYPTION_KEY
   - Set unique database passwords
   - Configure OAuth credentials

2. **Infrastructure:**
   - Postgres with backups enabled
   - Redis with persistence
   - MinIO with redundancy
   - Reverse proxy (nginx/caddy) with TLS

3. **Monitoring:**
   - Log aggregation (ELK, Loki)
   - Metrics collection (Prometheus)
   - Alerting (PagerDuty, Slack)
   - Uptime monitoring

4. **Backup:**
   - Database daily backups
   - Test restore procedure
   - Object storage backup

### Performance Baselines

Document these after load testing:

| Metric | Target | Actual |
|--------|--------|--------|
| API p50 latency | < 50ms | |
| API p95 latency | < 200ms | |
| API p99 latency | < 500ms | |
| Crawl pages/min | 500+ | |
| Export generation | < 60s | |
| Webhook delivery | < 5s | |

### Known Limitations (MVP)

Document current limitations for v1+ improvements:

1. No multi-tenancy (single org)
2. No SSO/SAML
3. No advanced RBAC
4. Postgres-only for CC edges (ClickHouse optional)
5. Single-region deployment
6. No real-time updates (polling-based)
