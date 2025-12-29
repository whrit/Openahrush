# Deployment Guide

This guide covers deploying Openahrush to production environments using Docker Compose, including database setup, environment configuration, monitoring, and operational procedures.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Production Docker Compose](#production-docker-compose)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Health Checks](#health-checks)
- [Backup and Restore](#backup-and-restore)
- [Monitoring and Logging](#monitoring-and-logging)
- [Scaling](#scaling)
- [Security Hardening](#security-hardening)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum (small deployments):**
- 2 CPU cores
- 4 GB RAM
- 50 GB storage (SSD recommended)
- Ubuntu 22.04 LTS or similar Linux distribution

**Recommended (production):**
- 4+ CPU cores
- 8+ GB RAM
- 200+ GB storage (SSD required)
- Ubuntu 22.04 LTS or similar

### Software Requirements

```bash
# Docker Engine (20.10+)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose (v2.0+)
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### Network Requirements

**Inbound Ports:**
- `443` - HTTPS (public)
- `80` - HTTP (redirect to HTTPS)

**Outbound Access:**
- OAuth providers (accounts.google.com, login.microsoftonline.com)
- Common Crawl data (commoncrawl.org)
- Container registries (hub.docker.com, ghcr.io)

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/openahrush.git
cd openahrush
```

### 2. Generate Secrets

```bash
# Generate JWT secret (32+ bytes)
openssl rand -base64 32

# Generate encryption key (exactly 32 bytes for Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Or use OpenSSL for encryption key
openssl rand -base64 32
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env.prod

# Edit with your secrets and configuration
nano .env.prod
```

**Critical variables to set:**
- `JWT_SECRET` - Use generated secret
- `ENCRYPTION_KEY` - Use generated key
- `DATABASE_URL` - Update password
- `MINIO_SECRET_KEY` - Change from default
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - OAuth credentials

### 4. Deploy

```bash
# Start services
docker compose -f infra/compose/docker-compose.prod.yml --env-file .env.prod up -d

# Check status
docker compose -f infra/compose/docker-compose.prod.yml ps

# View logs
docker compose -f infra/compose/docker-compose.prod.yml logs -f api
```

### 5. Initialize Database

```bash
# Run migrations
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini upgrade head

# Verify
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  python -c "from semrush_core.database import get_engine; import asyncio; asyncio.run(get_engine().connect())"
```

### 6. Verify Health

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"0.1.0","timestamp":"..."}
```

---

## Production Docker Compose

The production Docker Compose configuration is located at `/Users/beckett/Projects/Openahrush/infra/compose/docker-compose.prod.yml`.

### Key Differences from Development

**Production configuration includes:**
- Resource limits (CPU, memory)
- Health checks on all services
- Restart policies (`unless-stopped`)
- Log rotation and retention
- No development mounts or debug features
- Separate networks for service isolation
- Read-only root filesystems where possible

### Service Architecture

```
┌─────────────────┐
│  Reverse Proxy  │ (nginx/Caddy)
│   (HTTPS/SSL)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│   API Service   │────▶│  PostgreSQL  │
│   (FastAPI)     │     │  (Primary)   │
└────────┬────────┘     └──────────────┘
         │
         ├──────────────▶┌──────────────┐
         │               │    Redis     │
         │               │  (Queue)     │
         │               └──────────────┘
         │
         ├──────────────▶┌──────────────┐
         │               │    MinIO     │
         │               │  (Storage)   │
         │               └──────────────┘
         │
         └──────────────▶┌──────────────┐
                         │ ClickHouse   │
                         │  (Optional)  │
                         └──────────────┘
```

### Resource Limits

Default resource allocation per service:

| Service | CPU Limit | Memory Limit | Memory Reservation |
|---------|-----------|--------------|-------------------|
| API | 2.0 | 2 GB | 512 MB |
| Workers | 2.0 | 2 GB | 512 MB |
| PostgreSQL | 2.0 | 2 GB | 1 GB |
| Redis | 0.5 | 512 MB | 256 MB |
| MinIO | 1.0 | 1 GB | 512 MB |
| ClickHouse | 4.0 | 4 GB | 2 GB |

Adjust based on your workload in `docker-compose.prod.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          memory: 512M
```

---

## Environment Configuration

### Required Variables

```bash
# Core
ENVIRONMENT=production
LOG_LEVEL=info
DATABASE_URL=postgresql+psycopg://user:STRONG_PASSWORD@postgres:5432/semrush
REDIS_URL=redis://redis:6379/0

# Security (MUST CHANGE)
JWT_SECRET=<your-generated-secret-min-32-chars>
ENCRYPTION_KEY=<your-generated-fernet-key>

# Object Storage
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=<change-from-default>
MINIO_SECRET_KEY=<strong-secret-key>
S3_BUCKET=openahrush

# Google OAuth (for integrations)
GOOGLE_CLIENT_ID=<from-google-console>
GOOGLE_CLIENT_SECRET=<from-google-console>
GOOGLE_REDIRECT_URI=https://yourdomain.com/integrations/google/callback
```

### Optional Variables

```bash
# ClickHouse (for Common Crawl)
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_DATABASE=openahrush
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=<strong-password>

# Email (for notifications)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=notifications@yourdomain.com
SMTP_PASSWORD=<smtp-password>
MAIL_FROM=noreply@yourdomain.com
ENABLE_EMAIL_NOTIFICATIONS=true

# Monitoring
SENTRY_DSN=<your-sentry-dsn>
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### Validation on Startup

The application validates critical environment variables on startup:

```python
# Checked variables:
- DATABASE_URL (must be valid PostgreSQL URL)
- REDIS_URL (must be valid Redis URL)
- JWT_SECRET (minimum 32 characters)
- ENCRYPTION_KEY (valid Fernet key format)
- S3_BUCKET (bucket name provided)
```

**If validation fails:** Application exits with error message. Check logs:

```bash
docker compose -f infra/compose/docker-compose.prod.yml logs api
```

---

## Database Setup

### PostgreSQL Configuration

#### Initial Setup

```bash
# PostgreSQL runs in container with persistent volume
# Data stored in: postgres_data volume

# Access PostgreSQL shell
docker compose -f infra/compose/docker-compose.prod.yml exec postgres psql -U semrush -d semrush
```

#### Running Migrations

**Apply all migrations:**

```bash
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini upgrade head
```

**Check current version:**

```bash
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini current
```

**View migration history:**

```bash
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini history
```

#### Creating New Migrations

```bash
# Generate migration from model changes
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini revision --autogenerate -m "description of change"

# Review generated migration in migrations/versions/
# Edit if necessary, then apply:
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini upgrade head
```

#### Rollback Migrations

```bash
# Rollback one migration
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini downgrade -1

# Rollback to specific version
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini downgrade <revision_id>
```

#### Production Migration Best Practices

1. **Test migrations on staging** before production
2. **Backup database** before applying migrations (see Backup section)
3. **Check migration SQL** in generated files for destructive operations
4. **Apply during low-traffic window** if schema changes are breaking
5. **Monitor application logs** during and after migration
6. **Have rollback plan ready** (tested rollback migration)

#### Handling Concurrent Migrations

Alembic uses a lock table to prevent concurrent migrations:

```sql
-- Check lock status
SELECT * FROM alembic_version;

-- If migration stuck, manually release (DANGEROUS - ensure no migration running):
-- DELETE FROM alembic_version WHERE version_num = 'stuck_version';
```

#### Zero-Downtime Migration Strategies

**For breaking schema changes:**

1. **Expand-Contract Pattern:**
   - Migration 1: Add new column (nullable)
   - Deploy code that writes to both old and new columns
   - Migration 2: Backfill data
   - Deploy code that reads from new column only
   - Migration 3: Drop old column

2. **Table Rename:**
   - Create new table with new schema
   - Set up triggers to duplicate writes
   - Backfill data in batches
   - Switch reads to new table
   - Remove triggers and old table

**Example:**

```python
# Migration: Add new column (safe)
def upgrade():
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=True))

# Later migration: Make non-nullable after backfill
def upgrade():
    # Backfill first
    op.execute("UPDATE users SET email_verified = false WHERE email_verified IS NULL")
    # Then alter
    op.alter_column('users', 'email_verified', nullable=False)
```

---

## SSL/TLS Configuration

### Using Nginx Reverse Proxy

**Install Nginx:**

```bash
sudo apt-get install nginx certbot python3-certbot-nginx
```

**Nginx configuration (`/etc/nginx/sites-available/openahrush`):**

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com;

    # SSL certificates (via Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy settings
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (bypass auth)
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }

    # Larger uploads for CSV imports
    client_max_body_size 50M;
}
```

**Enable site and obtain certificate:**

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/openahrush /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Obtain Let's Encrypt certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal (certbot sets up cron automatically)
sudo certbot renew --dry-run
```

### Using Caddy (Automatic HTTPS)

**Caddyfile:**

```
yourdomain.com {
    reverse_proxy localhost:8000

    # Automatic HTTPS via Let's Encrypt
    tls your-email@example.com

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        X-XSS-Protection "1; mode=block"
    }
}
```

**Run Caddy:**

```bash
sudo caddy run --config /etc/caddy/Caddyfile
```

---

## Health Checks

### Endpoint Overview

**Liveness probe (`/health`):**
- Checks if application is running
- Always responds quickly (< 100ms)
- Returns 200 if healthy, 503 if not

**Readiness probe (`/ready` - optional):**
- Checks if application can serve traffic
- Validates database, Redis, MinIO connectivity
- Returns 200 when ready, 503 when not ready

### Docker Health Checks

Configured in `docker-compose.prod.yml`:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Check container health:**

```bash
docker compose -f infra/compose/docker-compose.prod.yml ps
# Look for "healthy" status
```

### Monitoring Health

**Manual check:**

```bash
curl http://localhost:8000/health
```

**Automated monitoring:**

```bash
# Using watch
watch -n 10 curl -s http://localhost:8000/health

# Using systemd timer or cron
*/5 * * * * curl -f http://localhost:8000/health || echo "Health check failed" | mail -s "Openahrush Health Alert" admin@example.com
```

### Health Check Response

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-01-15T10:30:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "storage": "ok"
  }
}
```

**Degraded state:**

```json
{
  "status": "degraded",
  "version": "0.1.0",
  "timestamp": "2025-01-15T10:30:00Z",
  "checks": {
    "database": "ok",
    "redis": "error",
    "storage": "ok"
  }
}
```

---

## Backup and Restore

### PostgreSQL Backup

#### Automated Daily Backups

**Backup script (`/usr/local/bin/backup-openahrush.sh`):**

```bash
#!/bin/bash
set -e

BACKUP_DIR="/var/backups/openahrush"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Dump database
docker compose -f /opt/openahrush/infra/compose/docker-compose.prod.yml \
  exec -T postgres pg_dump -U semrush -d semrush | \
  gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Backup MinIO data (optional, if not using external S3)
docker compose -f /opt/openahrush/infra/compose/docker-compose.prod.yml \
  exec -T minio mc mirror /data $BACKUP_DIR/minio_$DATE

# Remove old backups
find $BACKUP_DIR -name "postgres_*.sql.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "minio_*" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} +

# Upload to remote storage (optional)
# aws s3 sync $BACKUP_DIR s3://your-backup-bucket/openahrush/

echo "Backup completed: $DATE"
```

**Make executable and add to cron:**

```bash
sudo chmod +x /usr/local/bin/backup-openahrush.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
0 2 * * * /usr/local/bin/backup-openahrush.sh >> /var/log/openahrush-backup.log 2>&1
```

#### Manual Backup

```bash
# One-time backup
docker compose -f infra/compose/docker-compose.prod.yml exec -T postgres \
  pg_dump -U semrush -d semrush | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore from Backup

```bash
# Stop API and workers (prevent writes)
docker compose -f infra/compose/docker-compose.prod.yml stop api workers

# Restore database
gunzip < backup_20250115.sql.gz | \
  docker compose -f infra/compose/docker-compose.prod.yml exec -T postgres \
  psql -U semrush -d semrush

# Restart services
docker compose -f infra/compose/docker-compose.prod.yml start api workers

# Verify
curl http://localhost:8000/health
```

### MinIO/S3 Backup

**If using MinIO container:**

```bash
# Install MinIO Client
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Configure alias
mc alias set local http://localhost:9000 minioadmin MINIO_SECRET_KEY

# Mirror bucket to local directory
mc mirror local/openahrush /backup/minio/openahrush

# Or sync to remote S3
mc mirror local/openahrush s3-backup/openahrush-backup
```

**If using AWS S3:**
- S3 buckets have built-in versioning and replication
- Enable versioning: `aws s3api put-bucket-versioning --bucket openahrush --versioning-configuration Status=Enabled`
- Configure cross-region replication for disaster recovery

### Disaster Recovery

**Full system restore procedure:**

1. **Provision new server** with same specs
2. **Install Docker and Docker Compose**
3. **Clone repository** and checkout same version
4. **Restore environment file** (`.env.prod`)
5. **Start database only:**
   ```bash
   docker compose -f infra/compose/docker-compose.prod.yml up -d postgres redis minio
   ```
6. **Restore database backup:**
   ```bash
   gunzip < postgres_backup.sql.gz | \
     docker compose -f infra/compose/docker-compose.prod.yml exec -T postgres \
     psql -U semrush -d semrush
   ```
7. **Restore MinIO data** (if applicable)
8. **Start remaining services:**
   ```bash
   docker compose -f infra/compose/docker-compose.prod.yml up -d
   ```
9. **Verify health and functionality**

**Recovery Time Objective (RTO):** 1-2 hours
**Recovery Point Objective (RPO):** 24 hours (with daily backups)

---

## Monitoring and Logging

### Application Logs

**View logs:**

```bash
# All services
docker compose -f infra/compose/docker-compose.prod.yml logs -f

# Specific service
docker compose -f infra/compose/docker-compose.prod.yml logs -f api

# Last 100 lines
docker compose -f infra/compose/docker-compose.prod.yml logs --tail=100 api
```

### Structured Logging

Production logs are JSON-formatted for easy parsing:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "semrush_api.main",
  "message": "Request completed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "GET",
  "path": "/projects",
  "status_code": 200,
  "duration_ms": 45.2
}
```

### Log Aggregation

**Using ELK Stack (Elasticsearch, Logstash, Kibana):**

1. **Install Filebeat** on host:
   ```bash
   curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.11.0-amd64.deb
   sudo dpkg -i filebeat-8.11.0-amd64.deb
   ```

2. **Configure Filebeat** (`/etc/filebeat/filebeat.yml`):
   ```yaml
   filebeat.inputs:
   - type: container
     paths:
       - '/var/lib/docker/containers/*/*.log'
     processors:
       - add_docker_metadata: ~

   output.elasticsearch:
     hosts: ["https://your-elasticsearch:9200"]
     username: "elastic"
     password: "changeme"
   ```

3. **Start Filebeat:**
   ```bash
   sudo systemctl enable filebeat
   sudo systemctl start filebeat
   ```

**Using Grafana Loki:**

Add Loki driver to Docker Compose:

```yaml
services:
  api:
    logging:
      driver: loki
      options:
        loki-url: "http://localhost:3100/loki/api/v1/push"
        loki-batch-size: "400"
```

### Metrics and Monitoring

**Prometheus metrics (optional):**

Add `/metrics` endpoint to export Prometheus metrics:

```yaml
# docker-compose.prod.yml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
```

**Key metrics to track:**
- Request rate and latency (p50, p95, p99)
- Error rate (4xx, 5xx)
- Database connection pool usage
- Queue depth (Redis)
- Crawl throughput (pages/minute)
- Export generation time

### Alerting

**Example Prometheus alert rules:**

```yaml
groups:
  - name: openahrush
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        annotations:
          summary: "PostgreSQL is down"

      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
        for: 5m
        annotations:
          summary: "Container memory usage > 90%"
```

---

## Scaling

### Vertical Scaling

**Increase resources for existing containers:**

1. **Edit `docker-compose.prod.yml`** resource limits:
   ```yaml
   services:
     api:
       deploy:
         resources:
           limits:
             cpus: '4.0'
             memory: 4G
   ```

2. **Recreate services:**
   ```bash
   docker compose -f infra/compose/docker-compose.prod.yml up -d --force-recreate api
   ```

### Horizontal Scaling

**Scale API workers:**

```bash
# Run multiple API instances behind load balancer
docker compose -f infra/compose/docker-compose.prod.yml up -d --scale api=3
```

**Configure load balancer (Nginx):**

```nginx
upstream openahrush_api {
    least_conn;
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    location / {
        proxy_pass http://openahrush_api;
        # ... other proxy settings ...
    }
}
```

### Database Scaling

**Read replicas:**

1. Configure PostgreSQL streaming replication
2. Direct read queries to replicas
3. Keep writes to primary

**Connection pooling:**

Already configured via SQLAlchemy's AsyncEngine:

```python
# Adjust pool size in semrush_core/database.py
engine = create_async_engine(
    settings.database_url,
    pool_size=20,  # Increase for more concurrent connections
    max_overflow=40,
    pool_pre_ping=True,
)
```

### ClickHouse Scaling

For large Common Crawl datasets:

1. **Increase ClickHouse resources**
2. **Use distributed tables** across multiple nodes
3. **Optimize partitioning** by domain prefix and snapshot
4. **Enable materialized views** for common queries

---

## Security Hardening

### Secrets Management

**Never commit secrets to git:**

```bash
# Add to .gitignore
.env
.env.prod
.env.local
*.key
*.pem
```

**Use secret management tools (production):**

- **HashiCorp Vault:** Centralized secret storage
- **AWS Secrets Manager:** If deploying on AWS
- **Docker Secrets:** For Docker Swarm deployments

**Example with Docker Secrets:**

```yaml
secrets:
  jwt_secret:
    external: true
  encryption_key:
    external: true

services:
  api:
    secrets:
      - jwt_secret
      - encryption_key
    environment:
      JWT_SECRET_FILE: /run/secrets/jwt_secret
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
```

### Firewall Configuration

**UFW (Uncomplicated Firewall):**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### Regular Security Updates

```bash
# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Update Docker images
docker compose -f infra/compose/docker-compose.prod.yml pull
docker compose -f infra/compose/docker-compose.prod.yml up -d

# Remove unused images
docker image prune -a
```

### Security Scanning

```bash
# Scan Docker images for vulnerabilities
docker scan openahrush-api:latest

# Use Trivy for comprehensive scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image openahrush-api:latest
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptom:** `could not connect to server: Connection refused`

**Solution:**
```bash
# Check PostgreSQL is running
docker compose -f infra/compose/docker-compose.prod.yml ps postgres

# Check logs
docker compose -f infra/compose/docker-compose.prod.yml logs postgres

# Verify DATABASE_URL format
echo $DATABASE_URL
# Should be: postgresql+psycopg://user:pass@postgres:5432/dbname

# Test connection
docker compose -f infra/compose/docker-compose.prod.yml exec postgres \
  psql -U semrush -d semrush -c "SELECT 1;"
```

#### 2. MinIO Access Denied

**Symptom:** `403 Forbidden` when accessing S3 bucket

**Solution:**
```bash
# Ensure bucket exists
docker compose -f infra/compose/docker-compose.prod.yml exec api python -c "
from semrush_core.storage import ensure_bucket
import asyncio
asyncio.run(ensure_bucket())
"

# Check MinIO credentials match .env
docker compose -f infra/compose/docker-compose.prod.yml logs minio | grep MINIO_ROOT
```

#### 3. Migration Failures

**Symptom:** `Target database is not up to date`

**Solution:**
```bash
# Check current version
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini current

# View pending migrations
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini show

# Force upgrade
docker compose -f infra/compose/docker-compose.prod.yml exec api \
  alembic -c migrations/alembic.ini upgrade head
```

#### 4. High Memory Usage

**Symptom:** Container OOM killed

**Solution:**
```bash
# Check memory usage
docker stats

# Increase memory limits in docker-compose.prod.yml
# Restart with new limits
docker compose -f infra/compose/docker-compose.prod.yml up -d --force-recreate
```

#### 5. OAuth Integration Failures

**Symptom:** `redirect_uri_mismatch`

**Solution:**
- Verify `GOOGLE_REDIRECT_URI` matches Google Cloud Console configuration
- Must use exact same protocol (https://) and port
- No trailing slashes

### Debug Mode

**Enable debug logging temporarily:**

```bash
# Edit .env.prod
LOG_LEVEL=debug

# Restart API
docker compose -f infra/compose/docker-compose.prod.yml restart api

# Watch logs
docker compose -f infra/compose/docker-compose.prod.yml logs -f api
```

**Disable after debugging:**

```bash
LOG_LEVEL=info
docker compose -f infra/compose/docker-compose.prod.yml restart api
```

### Getting Help

1. **Check documentation:** `/Users/beckett/Projects/Openahrush/docs/`
2. **Search issues:** https://github.com/yourusername/openahrush/issues
3. **Community forum:** Discord/Slack channel
4. **Create issue:** Include logs, environment, steps to reproduce

---

## Maintenance Windows

### Planned Maintenance

**Recommended schedule:**
- **Minor updates:** Monthly, during low-traffic hours
- **Major updates:** Quarterly, scheduled maintenance window
- **Security patches:** As needed, with 24-hour notice

**Maintenance procedure:**

1. **Announce maintenance** (webhook, email, status page)
2. **Create backup** (see Backup section)
3. **Put app in maintenance mode** (optional)
4. **Perform updates**
5. **Run smoke tests**
6. **Monitor for issues**
7. **Announce completion**

### Zero-Downtime Deployments

**Blue-green deployment:**

1. Deploy new version to separate stack
2. Run health checks on new version
3. Switch load balancer to new version
4. Keep old version running for quick rollback
5. Decomission old version after validation period

---

## Checklist: Production Readiness

Before going live, verify:

- [ ] All secrets generated and configured (JWT_SECRET, ENCRYPTION_KEY)
- [ ] Database passwords changed from defaults
- [ ] SSL/TLS certificate installed and auto-renewal configured
- [ ] Firewall configured (ports 80, 443 open; others closed)
- [ ] Automated backups scheduled and tested
- [ ] Health checks passing on all services
- [ ] Monitoring and alerting configured
- [ ] Log aggregation set up
- [ ] Resource limits configured appropriately
- [ ] OAuth credentials configured for integrations
- [ ] Webhook URLs validated (no SSRF vulnerabilities)
- [ ] Rate limiting enabled
- [ ] Documentation reviewed by team
- [ ] Disaster recovery plan documented and tested
- [ ] Security scan completed (no critical vulnerabilities)
- [ ] Performance testing completed

---

## Additional Resources

- [Configuration Reference](/Users/beckett/Projects/Openahrush/docs/CONFIGURATION.md)
- [Troubleshooting Guide](/Users/beckett/Projects/Openahrush/docs/TROUBLESHOOTING.md)
- [API Reference](/Users/beckett/Projects/Openahrush/docs/API_REFERENCE.md)
- [Developer Guide](/Users/beckett/Projects/Openahrush/docs/DEVELOPER_GUIDE.md)
