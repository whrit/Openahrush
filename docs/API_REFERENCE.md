# API Reference

Openahrush REST API provides comprehensive access to all platform features including project management, integrations, site audits, backlink analysis, and reporting.

**Base URL:** `http://localhost:8000` (development)

**API Version:** 0.1.0

## Table of Contents

- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Responses](#error-responses)
- [Pagination](#pagination)
- [Endpoints](#endpoints)
  - [Health](#health)
  - [Authentication](#authentication-endpoints)
  - [Projects](#projects)
  - [Project Settings](#project-settings)
  - [Integrations](#integrations)
  - [Crawls & Issues](#crawls--issues)
  - [Diffs](#diffs)
  - [Alerts](#alerts)
  - [Backlinks](#backlinks)
  - [Common Crawl](#common-crawl)
  - [Exports](#exports)
  - [Webhooks](#webhooks)

---

## Authentication

All API endpoints (except `/health`, `/auth/login`, and `/auth/register`) require JWT bearer token authentication.

### Obtaining a Token

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your-password"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Using the Token

Include the token in the `Authorization` header for all authenticated requests:

```bash
curl -X GET http://localhost:8000/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Token Expiration

- Default expiration: 60 minutes (3600 seconds)
- Configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` environment variable
- No automatic refresh mechanism in MVP (re-authenticate to obtain new token)

---

## Rate Limiting

Rate limits protect the API from abuse and ensure fair resource allocation.

### Default Limits (MVP)

| Category | Limit | Scope |
|----------|-------|-------|
| Auth endpoints | 5/minute | Per IP |
| Crawl triggers | 10/hour | Per project |
| Export triggers | 20/hour | Per project |
| API reads | 100/minute | Per user |
| Webhook config | 10/minute | Per project |

### Rate Limit Headers

All responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

### Rate Limit Exceeded

When rate limit is exceeded, the API returns HTTP 429:

```json
{
  "error": "rate_limited",
  "message": "Rate limit exceeded. Retry after 45 seconds."
}
```

---

## Error Responses

All errors follow a consistent JSON structure:

```json
{
  "error": "error_code",
  "message": "Human-readable error description"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `bad_request` | 400 | Invalid request format or parameters |
| `unauthorized` | 401 | Missing or invalid authentication token |
| `forbidden` | 403 | Authenticated but lacks permission |
| `not_found` | 404 | Resource does not exist |
| `conflict` | 409 | Resource conflict (e.g., duplicate email) |
| `validation_error` | 422 | Request validation failed |
| `rate_limited` | 429 | Rate limit exceeded |
| `internal_error` | 500 | Server error |

### Validation Errors

Validation errors (422) include detailed field-level information:

```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": [
    {
      "loc": ["body", "email"],
      "msg": "Invalid email format",
      "type": "value_error.email"
    }
  ]
}
```

---

## Pagination

List endpoints support cursor-based pagination via query parameters.

### Parameters

- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 50, max: 100) - Items per page

### Example Request

```bash
GET /projects?page=2&page_size=20
```

### Response Format

```json
{
  "items": [...],
  "total": 150,
  "page": 2,
  "page_size": 20
}
```

### Navigation

Calculate pagination:
- Total pages: `ceil(total / page_size)`
- Has next page: `page * page_size < total`
- Has previous page: `page > 1`

---

## Endpoints

### Health

#### GET /health

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Status Codes:**
- `200` - Service is healthy
- `503` - Service is degraded or unhealthy

---

### Authentication Endpoints

#### POST /auth/register

Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecureP@ssw0rd",
  "name": "John Doe"
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "is_active": true
}
```

**Errors:**
- `409` - Email already registered
- `422` - Validation error (invalid email or password too short)

---

#### POST /auth/login

Authenticate with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecureP@ssw0rd"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errors:**
- `401` - Invalid credentials or inactive account

---

#### POST /auth/logout

Logout current user (informational, JWT is stateless).

**Request Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response (200):**
```json
{
  "message": "Successfully logged out"
}
```

**Note:** Client should discard the token. For true token invalidation, implement a token blacklist in future versions.

---

#### GET /me

Get current authenticated user information.

**Request Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "is_active": true
}
```

**Errors:**
- `401` - Not authenticated
- `404` - User not found

---

### Projects

#### GET /projects

List all projects owned by the authenticated user.

**Query Parameters:**
- `page` (integer, default: 1)
- `page_size` (integer, default: 50, max: 100)

**Response (200):**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "My Website",
      "owner_id": "123e4567-e89b-12d3-a456-426614174000",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 50
}
```

---

#### POST /projects

Create a new project.

**Request Body:**
```json
{
  "name": "My Website"
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Website",
  "owner_id": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

---

#### GET /projects/{project_id}

Get a specific project.

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Website",
  "owner_id": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Errors:**
- `404` - Project not found or not owned by user

---

#### PATCH /projects/{project_id}

Update a project's fields. Only provided fields are updated.

**Request Body:**
```json
{
  "name": "Updated Project Name"
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Updated Project Name",
  "owner_id": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T10:35:00Z"
}
```

---

#### DELETE /projects/{project_id}

Delete a project and all associated data (sites, crawls, issues, etc.).

**Response (204):** No content

**Errors:**
- `404` - Project not found or not owned by user

---

#### POST /projects/{project_id}/sites

Add a site to a project.

**Request Body:**
```json
{
  "domain": "example.com",
  "base_url": "https://example.com"
}
```

**Response (201):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "example.com",
  "base_url": "https://example.com",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### POST /projects/{project_id}/competitors

Add a competitor domain to a project.

**Request Body:**
```json
{
  "domain": "competitor.com"
}
```

**Response (201):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "competitor.com",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### GET /projects/{project_id}/competitors

List all competitors for a project.

**Response (200):**
```json
{
  "items": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "domain": "competitor.com",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

---

### Project Settings

#### GET /projects/{project_id}/settings

Get project configuration settings.

**Response (200):**
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "seed_url": "https://example.com",
  "include_subdomains": true,
  "allowed_hosts": ["example.com", "www.example.com"],
  "allowed_schemes": ["https", "http"],
  "include_regexes": [],
  "exclude_regexes": ["/admin/.*"],
  "query_param_policy": "strip_tracking",
  "strip_tracking_params": true,
  "max_pages": 10000,
  "max_depth": 5,
  "concurrency_html": 16,
  "politeness_delay_ms": 1000,
  "respect_robots": true,
  "use_sitemaps": true,
  "js_render_mode": "hybrid",
  "max_rendered_pages": 200,
  "max_render_time_ms": 15000,
  "concurrency_js": 4,
  "audit_frequency": "weekly",
  "integration_sync_frequency": "daily",
  "retain_audit_runs": 10,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

---

#### PUT /projects/{project_id}/settings

Update project settings. Full replacement of settings.

**Request Body:**
```json
{
  "seed_url": "https://example.com",
  "include_subdomains": true,
  "max_pages": 5000,
  "max_depth": 3,
  "js_render_mode": "hybrid",
  "audit_frequency": "daily"
}
```

**Response (200):** Returns updated settings object (same format as GET)

---

### Integrations

#### POST /integrations/{provider}/connect

Initiate OAuth flow for an integration provider.

**Providers:** `google`, `microsoft`

**Response (200):**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
  "state": "randomly-generated-state-token"
}
```

**Client Flow:**
1. Redirect user to `auth_url`
2. User authorizes application
3. Provider redirects to callback URL with authorization code
4. Callback endpoint exchanges code for tokens

---

#### POST /integrations/{provider}/callback

OAuth callback handler (typically called by provider, not directly).

**Query Parameters:**
- `code` - Authorization code from provider
- `state` - State token for CSRF protection

**Response (200):**
```json
{
  "success": true,
  "account_id": "990e8400-e29b-41d4-a716-446655440000"
}
```

---

#### GET /integrations/accounts

List all connected integration accounts for the current user.

**Response (200):**
```json
{
  "items": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440000",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider": "google",
      "account_email": "user@example.com",
      "connected_at": "2025-01-15T10:30:00Z",
      "last_sync_at": "2025-01-20T08:00:00Z"
    }
  ]
}
```

---

#### POST /integrations/accounts/{account_id}/disconnect

Disconnect an integration account and revoke tokens.

**Response (200):**
```json
{
  "message": "Integration account disconnected successfully"
}
```

---

#### GET /integrations/{provider}/properties

List available properties for a connected integration account.

**Query Parameters:**
- `account_id` (UUID, required) - Integration account ID

**Response (200):**
```json
{
  "items": [
    {
      "property_id": "properties/123456789",
      "property_name": "https://example.com",
      "property_type": "SITE_VERIFICATION",
      "provider": "google_search_console"
    }
  ]
}
```

---

#### POST /projects/{project_id}/integrations/map

Map an integration property to a project site.

**Request Body:**
```json
{
  "account_id": "990e8400-e29b-41d4-a716-446655440000",
  "property_id": "properties/123456789",
  "site_id": "660e8400-e29b-41d4-a716-446655440000"
}
```

**Response (201):**
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "account_id": "990e8400-e29b-41d4-a716-446655440000",
  "property_id": "properties/123456789",
  "site_id": "660e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### POST /projects/{project_id}/integrations/sync

Trigger a manual sync for all mapped integrations in a project.

**Response (202):**
```json
{
  "message": "Sync jobs queued",
  "job_ids": [
    "bb0e8400-e29b-41d4-a716-446655440000",
    "cc0e8400-e29b-41d4-a716-446655440000"
  ]
}
```

---

### Crawls & Issues

#### POST /projects/{project_id}/crawls

Trigger a new site audit crawl.

**Request Body (optional):**
```json
{
  "site_id": "660e8400-e29b-41d4-a716-446655440000"
}
```

**Response (202):**
```json
{
  "crawl_run_id": "dd0e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### GET /projects/{project_id}/crawls

List crawl runs for a project.

**Query Parameters:**
- `page`, `page_size` - Pagination
- `status` (optional) - Filter by status: `queued`, `running`, `completed`, `failed`

**Response (200):**
```json
{
  "items": [
    {
      "id": "dd0e8400-e29b-41d4-a716-446655440000",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "site_id": "660e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "pages_crawled": 1247,
      "pages_rendered": 42,
      "issues_found": 156,
      "started_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T11:45:00Z",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 50
}
```

---

#### GET /crawls/{crawl_run_id}

Get detailed information about a specific crawl run.

**Response (200):**
```json
{
  "id": "dd0e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "site_id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "pages_crawled": 1247,
  "pages_rendered": 42,
  "issues_found": 156,
  "config_snapshot": { /* project settings at time of crawl */ },
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T11:45:00Z",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### GET /crawls/{crawl_run_id}/issues

List issues found in a specific crawl run.

**Query Parameters:**
- `page`, `page_size` - Pagination
- `severity` (optional) - Filter by: `critical`, `high`, `medium`, `low`
- `type` (optional) - Filter by issue type code

**Response (200):**
```json
{
  "items": [
    {
      "id": "ee0e8400-e29b-41d4-a716-446655440000",
      "crawl_run_id": "dd0e8400-e29b-41d4-a716-446655440000",
      "issue_type_code": "missing_title",
      "severity": "high",
      "page_url": "https://example.com/page1",
      "impact_score": 8.5,
      "evidence": {
        "expected": "Title tag",
        "found": null
      },
      "created_at": "2025-01-15T11:00:00Z"
    }
  ],
  "total": 156,
  "page": 1,
  "page_size": 50
}
```

---

#### GET /projects/{project_id}/issues

List all current issues for a project (from most recent crawl).

**Query Parameters:**
- `page`, `page_size` - Pagination
- `severity` (optional)
- `type` (optional)
- `sort` (optional) - Sort by: `impact` (default), `severity`, `created_at`

**Response:** Same format as `/crawls/{crawl_run_id}/issues`

---

### Diffs

#### GET /projects/{project_id}/issues/diffs

Compare issues between two crawl runs.

**Query Parameters:**
- `base_crawl_id` (UUID, optional) - Base crawl run (defaults to previous run)
- `compare_crawl_id` (UUID, optional) - Comparison crawl run (defaults to latest run)

**Response (200):**
```json
{
  "base_crawl_id": "cc0e8400-e29b-41d4-a716-446655440000",
  "compare_crawl_id": "dd0e8400-e29b-41d4-a716-446655440000",
  "new_issues": 23,
  "resolved_issues": 15,
  "unchanged_issues": 118,
  "new_issues_list": [ /* issue objects */ ],
  "resolved_issues_list": [ /* issue objects */ ]
}
```

---

### Alerts

#### GET /projects/{project_id}/alerts

List alert rules configured for a project.

**Response (200):**
```json
{
  "items": [
    {
      "id": "ff0e8400-e29b-41d4-a716-446655440000",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "alert_type": "visibility_drop",
      "threshold": 20.0,
      "enabled": true,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

---

#### POST /projects/{project_id}/alerts/rules

Create a new alert rule.

**Request Body:**
```json
{
  "alert_type": "visibility_drop",
  "threshold": 20.0,
  "enabled": true
}
```

**Response (201):** Returns created alert rule object

---

### Backlinks

#### GET /links/domain/{domain}/refdomains

Get referring domains for a target domain (from Common Crawl data).

**Query Parameters:**
- `page`, `page_size` - Pagination
- `snapshot_id` (optional) - Specific snapshot ID

**Response (200):**
```json
{
  "domain": "example.com",
  "total_refdomains": 1250,
  "items": [
    {
      "source_domain": "news.example.org",
      "backlink_count": 45,
      "first_seen": "2024-12-01T00:00:00Z",
      "last_seen": "2025-01-01T00:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 50
}
```

---

#### GET /links/domain/{domain}/backlinks

Get individual backlinks for a target domain.

**Query Parameters:**
- `page`, `page_size` - Pagination
- `source_domain` (optional) - Filter by source domain
- `snapshot_id` (optional)

**Response (200):**
```json
{
  "domain": "example.com",
  "total_backlinks": 15420,
  "items": [
    {
      "source_url": "https://news.example.org/article-123",
      "target_url": "https://example.com/page1",
      "anchor": "helpful resource",
      "rel_nofollow": false,
      "first_seen": "2024-12-15T00:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 50
}
```

---

#### GET /links/domain/{domain}/anchors

Get anchor text distribution for backlinks to a domain.

**Response (200):**
```json
{
  "domain": "example.com",
  "anchors": [
    {
      "anchor": "example website",
      "count": 234,
      "percentage": 15.2
    },
    {
      "anchor": "click here",
      "count": 189,
      "percentage": 12.3
    }
  ]
}
```

---

#### GET /links/domain/{domain}/new-lost

Compare backlinks between two Common Crawl snapshots.

**Query Parameters:**
- `snapshot_a` (required) - Earlier snapshot ID
- `snapshot_b` (required) - Later snapshot ID

**Response (200):**
```json
{
  "domain": "example.com",
  "snapshot_a": "CC-MAIN-2024-40",
  "snapshot_b": "CC-MAIN-2025-01",
  "new_backlinks": 342,
  "lost_backlinks": 127,
  "new_refdomains": 45,
  "lost_refdomains": 12
}
```

---

#### GET /links/domain/{domain}/overlap

Find shared referring domains between target and competitors.

**Query Parameters:**
- `competitors` (required) - Comma-separated competitor domains

**Response (200):**
```json
{
  "domain": "example.com",
  "competitors": ["competitor1.com", "competitor2.com"],
  "shared_refdomains": [
    {
      "source_domain": "industry-blog.com",
      "links_to_target": 5,
      "links_to_competitors": ["competitor1.com"]
    }
  ]
}
```

---

#### GET /links/domain/{domain}/intersect

Find domains linking to competitors but not to target.

**Query Parameters:**
- `competitors` (required) - Comma-separated competitor domains

**Response (200):**
```json
{
  "domain": "example.com",
  "competitors": ["competitor1.com", "competitor2.com"],
  "gap_refdomains": [
    {
      "source_domain": "opportunity-site.com",
      "links_to_competitors": ["competitor1.com", "competitor2.com"],
      "backlink_count": 12
    }
  ]
}
```

---

#### POST /projects/{project_id}/backlinks/import

Import backlinks from CSV file.

**Request Body (multipart/form-data):**
- `file` - CSV file with columns: source_url, target_url, anchor (optional)

**Response (202):**
```json
{
  "message": "Import job queued",
  "job_id": "110e8400-e29b-41d4-a716-446655440000",
  "rows_submitted": 1500
}
```

---

#### GET /projects/{project_id}/backlinks/targets

List backlink targets for project sites (aggregated from all sources).

**Response (200):**
```json
{
  "items": [
    {
      "target_url": "https://example.com/page1",
      "total_backlinks": 234,
      "referring_domains": 45,
      "sources": ["commoncrawl", "import", "crawl"]
    }
  ]
}
```

---

### Common Crawl

#### GET /commoncrawl/snapshots

List available Common Crawl snapshots.

**Response (200):**
```json
{
  "items": [
    {
      "id": "120e8400-e29b-41d4-a716-446655440000",
      "snapshot_id": "CC-MAIN-2025-01",
      "snapshot_date": "2025-01-01",
      "status": "completed",
      "edges_ingested": 1250000000,
      "ingested_at": "2025-01-10T00:00:00Z"
    }
  ]
}
```

---

#### POST /commoncrawl/ingest

Trigger Common Crawl snapshot ingestion (admin/operator only).

**Request Body:**
```json
{
  "snapshot_id": "CC-MAIN-2025-01",
  "wat_paths": ["crawl-data/CC-MAIN-2025-01/segments/..."]
}
```

**Response (202):**
```json
{
  "message": "Ingestion job queued",
  "job_id": "130e8400-e29b-41d4-a716-446655440000"
}
```

---

### Exports

#### POST /projects/{project_id}/exports

Generate an export (CSV, JSON, or PDF).

**Request Body:**
```json
{
  "export_type": "csv",
  "content_type": "issues",
  "filters": {
    "severity": ["critical", "high"]
  }
}
```

**Export Types:** `csv`, `json`, `pdf`

**Content Types:** `issues`, `pages`, `backlinks`, `performance`

**Response (202):**
```json
{
  "export_id": "140e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### GET /projects/{project_id}/exports

List exports for a project.

**Response (200):**
```json
{
  "items": [
    {
      "id": "140e8400-e29b-41d4-a716-446655440000",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "export_type": "pdf",
      "content_type": "issues",
      "status": "completed",
      "download_url": "https://storage.example.com/exports/report.pdf",
      "created_at": "2025-01-15T10:30:00Z",
      "completed_at": "2025-01-15T10:31:00Z"
    }
  ]
}
```

---

#### GET /projects/{project_id}/exports/{export_id}

Get export details and download URL.

**Response (200):**
```json
{
  "id": "140e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "export_type": "pdf",
  "content_type": "issues",
  "status": "completed",
  "download_url": "https://storage.example.com/exports/report.pdf",
  "file_size_bytes": 2458624,
  "expires_at": "2025-01-22T10:31:00Z",
  "created_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:31:00Z"
}
```

---

#### POST /projects/{project_id}/exports/schedules

Create a scheduled export.

**Request Body:**
```json
{
  "export_type": "pdf",
  "content_type": "issues",
  "frequency": "weekly",
  "day_of_week": 1,
  "hour": 9,
  "enabled": true
}
```

**Frequencies:** `daily`, `weekly`, `monthly`

**Response (201):** Returns created schedule object

---

#### GET /projects/{project_id}/exports/schedules

List export schedules for a project.

**Response (200):**
```json
{
  "items": [
    {
      "id": "150e8400-e29b-41d4-a716-446655440000",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "export_type": "pdf",
      "content_type": "issues",
      "frequency": "weekly",
      "day_of_week": 1,
      "hour": 9,
      "enabled": true,
      "last_run_at": "2025-01-13T09:00:00Z",
      "next_run_at": "2025-01-20T09:00:00Z"
    }
  ]
}
```

---

### Webhooks

#### POST /projects/{project_id}/webhooks

Create a webhook for project events.

**Request Body:**
```json
{
  "url": "https://your-app.com/webhooks/openahrush",
  "secret": "your-webhook-secret",
  "events": ["crawl.completed", "alert.fired"],
  "enabled": true
}
```

**Available Events:**
- `crawl.completed` - Crawl run finished
- `alert.fired` - Alert threshold triggered
- `integration.sync_failed` - Integration sync error
- `export.completed` - Export generation finished
- `commoncrawl.ingest_completed` - CC ingestion finished (optional)

**Response (201):**
```json
{
  "id": "160e8400-e29b-41d4-a716-446655440000",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://your-app.com/webhooks/openahrush",
  "events": ["crawl.completed", "alert.fired"],
  "enabled": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

#### GET /projects/{project_id}/webhooks

List webhooks for a project.

**Response (200):**
```json
{
  "items": [
    {
      "id": "160e8400-e29b-41d4-a716-446655440000",
      "project_id": "550e8400-e29b-41d4-a716-446655440000",
      "url": "https://your-app.com/webhooks/openahrush",
      "events": ["crawl.completed", "alert.fired"],
      "enabled": true,
      "last_delivery_at": "2025-01-15T11:45:00Z",
      "last_delivery_status": "success",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

---

#### DELETE /projects/{project_id}/webhooks/{webhook_id}

Delete a webhook.

**Response (204):** No content

---

## Webhook Delivery

When events occur, Openahrush sends HTTP POST requests to configured webhook URLs.

### Payload Format

```json
{
  "event_id": "170e8400-e29b-41d4-a716-446655440000",
  "event_type": "crawl.completed",
  "occurred_at": "2025-01-15T11:45:00Z",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "delivery_id": "180e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "crawl_run_id": "dd0e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "pages_crawled": 1247,
    "issues_found": 156
  }
}
```

### Signature Verification

All webhook deliveries include an `X-Openahrush-Signature` header with HMAC-SHA256 signature:

```python
import hmac
import hashlib

def verify_signature(payload_body, signature_header, webhook_secret):
    expected = hmac.new(
        webhook_secret.encode(),
        payload_body.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

### Retry Policy

- **Retry attempts:** 5
- **Backoff strategy:** Exponential (1s, 2s, 4s, 8s, 16s)
- **Timeout:** 30 seconds per request
- **Success criteria:** HTTP 2xx response
- **Failure:** After 5 failed attempts, webhook is marked as failed

---

## OpenAPI Specification

Interactive API documentation is available at:

- **Swagger UI:** `http://localhost:8000/docs` (development only)
- **ReDoc:** `http://localhost:8000/redoc` (development only)
- **OpenAPI JSON:** `http://localhost:8000/openapi.json` (development) or `/api/openapi.json` (production)

---

## Client Libraries

### Python

```python
import requests

class OpenahrushClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def list_projects(self):
        response = requests.get(
            f"{self.base_url}/projects",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def trigger_crawl(self, project_id):
        response = requests.post(
            f"{self.base_url}/projects/{project_id}/crawls",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = OpenahrushClient("http://localhost:8000", "your-token")
projects = client.list_projects()
```

### JavaScript/TypeScript

```typescript
class OpenahrushClient {
  constructor(private baseUrl: string, private accessToken: string) {}

  private async request(path: string, options: RequestInit = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  async listProjects() {
    return this.request('/projects');
  }

  async triggerCrawl(projectId: string) {
    return this.request(`/projects/${projectId}/crawls`, {
      method: 'POST',
    });
  }
}
```

---

## Rate Limit Best Practices

1. **Respect rate limits:** Check `X-RateLimit-Remaining` header
2. **Implement backoff:** Wait when `X-RateLimit-Remaining` is low
3. **Handle 429 responses:** Parse `Retry-After` header and wait
4. **Batch requests:** Use list endpoints with pagination instead of individual GETs
5. **Cache responses:** Cache data that doesn't change frequently

---

## API Versioning

Current API version: **0.1.0**

- Breaking changes will increment major version (1.0.0)
- New features will increment minor version (0.2.0)
- Bug fixes will increment patch version (0.1.1)
- Version is included in OpenAPI spec and `/health` response

Future versions may use URL path versioning: `/v2/projects`

---

## Support

For API questions, issues, or feature requests:

- **GitHub Issues:** https://github.com/yourusername/openahrush/issues
- **Documentation:** https://docs.openahrush.org
- **Community:** https://discord.gg/openahrush
