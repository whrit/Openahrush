Below are **complete, updated, ready-to-commit** versions of:

* `docs/ARCHITECTURE.md`
* `openapi.yaml`
* `.github/ISSUE_TEMPLATE/mvp-checklist.yml`

…followed by a **Common Crawl ingestion spec** (pipeline choices, indexes, storage layout, ClickHouse schema, and an MVP subset strategy).

---

## `docs/ARCHITECTURE.md`

```markdown
# ARCHITECTURE.md — OSS “Semrush-core” (MVP)
Python-first control plane + Rust data plane • Self-hostable • Provider-pluggable • Privacy-forward

## 1) Overview

The system is split into two planes:

- **Control plane (Python):** product API, integrations (OAuth + sync), normalization, orchestration, rules, diffs, alerts, exports/reports.
- **Data plane (Rust):** high-throughput crawling + parsing + frontier scheduling (and other “hot path” ingestion tasks where it materially improves cost/perf).

Primary principles:
- **Truth-first:** first-party integrations (GSC/GA4/BWT) are core and drive prioritization.
- **Free data moat:** Common Crawl ingestion is core MVP for backlinks + competitive link intel.
- **Hybrid crawling:** HTML-first with deterministic Playwright fallback under budgets.
- **Stable event schemas:** message payloads are stable even if transport changes (Redis queue → NATS/Kafka later).
- **Self-hostable:** Docker Compose base (Postgres + Redis + MinIO + optional ClickHouse).

---

## 2) Services

### 2.1 `apps/api` (FastAPI) — Public API + Dashboard Queries
Responsibilities:
- Auth (JWT), `/me`
- Project CRUD + **Project Settings** CRUD
- Crawl triggers and status reads
- Integration connect/callback endpoints (may delegate to integrations service)
- Dashboard endpoints (audit/performance/backlinks/exports)
- Webhooks config endpoints

Reads/writes:
- Writes to Postgres (system of record)
- Enqueues jobs to Redis (work queue)
- Reads aggregates from Postgres and/or ClickHouse

---

### 2.2 `apps/integrations` (Python) — OAuth + Sync + Normalization
Responsibilities:
- OAuth flows, token refresh, secure token storage
- Property discovery + mapping provider properties to project/site
- Backfills + incremental sync scheduling
- **Normalization layer** (canonical fact tables):
  - `search_fact_daily`
  - `analytics_fact_daily`
  - `link_facts` (provider link data where available)

Provider adapters:
- Search adapters: Google Search Console, Bing Webmaster Tools
- Analytics adapters: GA4 (optional others later)
- Import adapters: CSV → canonical schemas

---

### 2.3 `apps/workers` (Python) — Orchestration + Rules + Diffs + Alerts
Responsibilities:
- Scheduler (cron-like) for:
  - daily integration sync
  - weekly audits
  - alert evaluation
  - export schedules
- Orchestration state machines:
  - crawl pipeline (HTML + optional JS fallback)
  - audit analysis + diffs
  - Common Crawl ingest pipeline
- Rules engine + issue taxonomy + evidence generation
- Impact scoring by joining issues to canonical facts
- Alerts engine (visibility drops, CTR opportunities, regressions)

---

### 2.4 `apps/reports` (Python) — Exports + PDF Reports
Responsibilities:
- Render templates → PDF
- CSV/JSON exports
- Export status updates + artifact storage (MinIO/S3)
- Optional delivery later (email, slack); MVP uses download + webhooks

---

### 2.5 `crates/crawler` (Rust) — Crawl Data Plane
Responsibilities:
- Frontier + URL normalization + dedupe
- High concurrency fetch with per-host politeness
- HTML parsing + extraction (title/meta/canonical/h1/outlinks/text stats)
- Emits structured page records and link edges into Postgres/MinIO (via workers)

Notes:
- MVP may start with a Python crawler; Rust crawler should conform to the same page/event schema so it can be swapped in.

---

### 2.6 `apps/commoncrawl_ingest` (Python-first, Rust optional later)
Responsibilities:
- Ingest Common Crawl link data into:
  - raw edge store (ClickHouse recommended)
  - materialized aggregates for fast domain queries
- Compute:
  - referring domains
  - anchors distribution
  - new/lost between snapshots
  - overlap/intersect vs competitors
- Exposes snapshots list + ingestion status via API (operator/admin endpoints)

---

## 3) Storage

### 3.1 Postgres (System of record)
- Users, auth
- Projects, sites, competitors
- Project settings + schedules + retention/budgets
- Integration accounts + property mappings + sync runs
- Crawl runs + extracted pages + internal link edges
- Issues + diffs + alerts
- Exports + webhooks metadata
- Common Crawl snapshot metadata (ingestion status, specs)

### 3.2 MinIO/S3 (Object storage)
- Optional raw HTML artifacts (HTML + rendered HTML)
- Export artifacts (PDF/CSV/JSON)
- Optional SERP snapshots (if enabled)

### 3.3 Redis (Queue + locks)
- Work queue for:
  - integration sync jobs
  - crawl jobs
  - audit analysis jobs
  - common crawl ingest jobs
  - export jobs

### 3.4 ClickHouse (Recommended for MVP when enabling Common Crawl at meaningful scale)
- Raw edge table(s) (domain/url-level link edges)
- Aggregate tables (ref domains, anchors, overlap/intersect)
- Time-series rollups (optional)

---

## 4) Deployment diagram (Docker Compose)

+---------------------+         +-------------------+
|  Browser / Client   |  HTTPS  |   apps/api        |
+----------+----------+ ------> | (FastAPI)         |
           |                    +----+--------------+
           |                         |
           |                         | SQL
           |                         v
           |                    +----+--------------+
           |                    |   Postgres        |
           |                    +-------------------+
           |
           |                     Queue / Locks
           |                         |
           |                         v
           |                    +----+--------------+
           |                    |   Redis           |
           |                    +----+--------------+
           |                         |
           |               jobs/events|
           |                         v
           |   +---------------------+---------------------+
           |   |                                           |
           v   v                                           v
+----------+----------+                          +----------+----------+
| apps/integrations   |                          | apps/workers        |
| (sync + normalize)  |                          | (orchestrate/rules) |
+----------+----------+                          +----------+----------+
           |                                              |
           | artifacts / exports                           | crawl + ingest triggers
           v                                              v
+----------+----------+                          +----------+----------+
|   MinIO / S3        |                          | crates/crawler      |
| (HTML/exports/etc.) |                          | (Rust fetch/parse)  |
+----------+----------+                          +----------+----------+
           |
           | Common Crawl edges / aggregates
           v
+----------+----------+
|   ClickHouse        |
| (edges + rollups)   |
+---------------------+

---

## 5) Data flows

### 5.1 Onboarding + Integrations
1) User creates Project + Site.
2) User connects provider(s) via OAuth (GSC/GA4/BWT).
3) Integrations service lists properties; user maps property → project/site.
4) Integrations runs:
   - initial backfill (chunked)
   - daily incremental sync
5) Writes normalized facts:
   - `search_fact_daily`, `analytics_fact_daily` (+ `link_facts` where available)

### 5.2 Hybrid Site Audit (HTML-first + Playwright fallback)
1) User triggers crawl (API → queue `crawl.requested`).
2) Crawler fetches HTML pages under budgets and project scope rules.
3) Workers apply heuristics to select JS render candidates:
   - thin DOM/text
   - SPA shell detection
   - required selectors missing (project-configurable)
   - client-side redirect patterns
4) Playwright renders selected pages under strict budgets:
   - max rendered pages per run
   - per-page render timeout
   - separate JS concurrency
5) Workers run rules engine:
   - issues + evidence
   - impact score via joins to canonical facts
6) Diff engine compares crawl runs; alert engine fires as needed.

### 5.3 Common Crawl ingestion (Backlinks + Competitive)
1) Operator triggers ingestion: `POST /commoncrawl/ingest` (or scheduled).
2) Ingest pipeline:
   - loads snapshot metadata/spec
   - extracts link edges (domain/url + anchor when available)
   - writes raw edges and builds aggregates/materializations
3) API serves:
   - domain backlinks/ref-domains/anchors
   - new/lost between snapshots
   - overlap/intersect against competitors
4) Project backlink views may merge:
   - Common Crawl edges
   - provider links
   - CSV imports
   - (optional) community-fed edges

---

## 6) Project settings (enforced everywhere)

Project settings influence:
- URL normalization rules (tracking params, allow/deny lists)
- Crawl scope (hosts, regex include/exclude, depth)
- Crawl budgets (max pages, concurrency, politeness)
- Hybrid JS rendering budgets + heuristics config
- Schedules and retention

All crawls store a **config snapshot** so results remain reproducible.

---

## 7) Event schemas

### 7.1 Event envelope (common)
All internal events use:

- `event_id` (uuid)
- `event_type` (string)
- `occurred_at` (RFC3339)
- `project_id` (uuid)
- `trace_id` (uuid)
- `payload` (object)

### 7.2 Core events (MVP)

#### Integration events
- `integration.sync_requested`
- `integration.sync_progress` (optional)
- `integration.sync_completed`
- `integration.sync_failed`

Payload includes:
- provider, integration_account_id, property_id, date_range, mode, records_written, error

#### Crawl events
- `crawl.requested`
- `crawl.page_fetched`
- `crawl.js_candidates_selected`
- `crawl.page_rendered`
- `crawl.completed`

Key payload fields:
- crawl_run_id, site_id, URL(s), status_code, timings, hashes, artifact pointers

#### Audit/rules events
- `rules.completed`
- `diff.completed` (optional)
- `alert.fired`

#### Common Crawl events
- `commoncrawl.ingest_requested`
- `commoncrawl.ingest_progress` (optional)
- `commoncrawl.ingest_completed`
- `commoncrawl.ingest_failed`

---

## 8) Webhooks

Webhooks are configured per project:
- URL + secret + enabled events

Delivery semantics:
- at-least-once
- retries with exponential backoff
- signature header (HMAC-SHA256(body, secret))

Webhook payload uses the same event envelope, plus `delivery_id`.

---

## 9) Scaling notes (MVP → v1)
- Add ClickHouse early if Common Crawl ingestion is enabled beyond tiny subsets.
- Move Redis queue → NATS/Kafka when needing higher throughput or multiple worker groups.
- Shard crawl runs horizontally; enforce per-host politeness globally.
- Partition clickhouse tables by snapshot and by hash buckets for fast filtering.
- Materialize aggregates (ref domains/anchors/overlap/intersect) for interactive UX.

---
```

---

## `openapi.yaml`

```yaml
openapi: 3.0.3
info:
  title: OSS Semrush-core API
  version: 0.2.0
  description: >
    Starter OpenAPI spec for OSS “Semrush-core” MVP:
    Projects + Settings, Integrations (GSC/GA4/BWT), Hybrid Site Audit, Visibility endpoints,
    Backlinks (multi-source) + Common Crawl ingestion + competitive overlap/intersect, Exports, Alerts, Webhooks.

servers:
  - url: http://localhost:8000
    description: Local dev

tags:
  - name: Health
  - name: Auth
  - name: Projects
  - name: Settings
  - name: Integrations
  - name: Crawls
  - name: Audit
  - name: Performance
  - name: Backlinks
  - name: CommonCrawl
  - name: Alerts
  - name: Exports
  - name: Webhooks

security:
  - bearerAuth: []

paths:
  /healthz:
    get:
      tags: [Health]
      summary: Liveness probe
      security: []
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema: { $ref: "#/components/schemas/HealthResponse" }

  /readyz:
    get:
      tags: [Health]
      summary: Readiness probe
      security: []
      responses:
        "200":
          description: Ready
          content:
            application/json:
              schema: { $ref: "#/components/schemas/HealthResponse" }

  /auth/login:
    post:
      tags: [Auth]
      summary: Login and obtain an access token
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/LoginRequest" }
      responses:
        "200":
          description: Token response
          content:
            application/json:
              schema: { $ref: "#/components/schemas/LoginResponse" }
        "401":
          $ref: "#/components/responses/Unauthorized"

  /auth/logout:
    post:
      tags: [Auth]
      summary: Logout
      responses:
        "200":
          description: Logged out
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /me:
    get:
      tags: [Auth]
      summary: Get current user
      responses:
        "200":
          description: User
          content:
            application/json:
              schema: { $ref: "#/components/schemas/User" }

  /projects:
    get:
      tags: [Projects]
      summary: List projects
      responses:
        "200":
          description: Projects
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ProjectList" }
    post:
      tags: [Projects]
      summary: Create a project
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/ProjectCreate" }
      responses:
        "201":
          description: Created
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Project" }
        "400":
          $ref: "#/components/responses/BadRequest"

  /projects/{project_id}:
    get:
      tags: [Projects]
      summary: Get a project
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Project
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Project" }
        "404":
          $ref: "#/components/responses/NotFound"
    patch:
      tags: [Projects]
      summary: Update a project
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/ProjectUpdate" }
      responses:
        "200":
          description: Updated
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Project" }
    delete:
      tags: [Projects]
      summary: Delete a project
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "204":
          description: Deleted

  /projects/{project_id}/settings:
    get:
      tags: [Settings]
      summary: Get project settings
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Settings
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ProjectSettings" }
    put:
      tags: [Settings]
      summary: Update project settings
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/ProjectSettings" }
      responses:
        "200":
          description: Updated
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /projects/{project_id}/sites:
    post:
      tags: [Projects]
      summary: Add a site to a project
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/SiteCreate" }
      responses:
        "201":
          description: Created
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Site" }

  /projects/{project_id}/competitors:
    post:
      tags: [Projects]
      summary: Add a competitor domain
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CompetitorCreate" }
      responses:
        "201":
          description: Created
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Competitor" }
    get:
      tags: [Projects]
      summary: List competitors
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Competitors
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CompetitorList" }

  /integrations/{provider}/connect:
    post:
      tags: [Integrations]
      summary: Start OAuth connect flow for a provider
      parameters:
        - $ref: "#/components/parameters/Provider"
      responses:
        "200":
          description: Connect URL (or redirect hint)
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IntegrationConnectResponse" }

  /integrations/{provider}/callback:
    post:
      tags: [Integrations]
      summary: OAuth callback handler
      parameters:
        - $ref: "#/components/parameters/Provider"
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/OAuthCallbackRequest" }
      responses:
        "200":
          description: Connected
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IntegrationAccount" }

  /integrations/accounts:
    get:
      tags: [Integrations]
      summary: List integration accounts
      responses:
        "200":
          description: Accounts
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IntegrationAccountList" }

  /integrations/accounts/{integration_account_id}/disconnect:
    post:
      tags: [Integrations]
      summary: Disconnect an integration account
      parameters:
        - $ref: "#/components/parameters/IntegrationAccountId"
      responses:
        "200":
          description: Disconnected
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /integrations/{provider}/properties:
    get:
      tags: [Integrations]
      summary: List available properties for a provider account
      parameters:
        - $ref: "#/components/parameters/Provider"
        - in: query
          name: integration_account_id
          schema: { type: string, format: uuid }
          required: true
      responses:
        "200":
          description: Properties
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IntegrationPropertyList" }

  /projects/{project_id}/integrations/map:
    post:
      tags: [Integrations]
      summary: Map a provider property to a project/site
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/IntegrationMapRequest" }
      responses:
        "200":
          description: Mapping created/updated
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /projects/{project_id}/integrations/sync:
    post:
      tags: [Integrations]
      summary: Trigger an integration sync (manual)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: false
        content:
          application/json:
            schema: { $ref: "#/components/schemas/IntegrationSyncRequest" }
      responses:
        "202":
          description: Sync queued
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /projects/{project_id}/crawls:
    post:
      tags: [Crawls]
      summary: Trigger a crawl
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: false
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CrawlRequest" }
      responses:
        "202":
          description: Crawl queued
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CrawlRun" }
    get:
      tags: [Crawls]
      summary: List crawl runs
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Crawl runs
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CrawlRunList" }

  /crawls/{crawl_run_id}:
    get:
      tags: [Crawls]
      summary: Get crawl run details
      parameters:
        - $ref: "#/components/parameters/CrawlRunId"
      responses:
        "200":
          description: Crawl run
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CrawlRun" }

  /crawls/{crawl_run_id}/issues:
    get:
      tags: [Audit]
      summary: List issues for a crawl run
      parameters:
        - $ref: "#/components/parameters/CrawlRunId"
        - in: query
          name: sort
          schema:
            type: string
            enum: [impact, severity, category]
      responses:
        "200":
          description: Issues
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IssueList" }

  /projects/{project_id}/issues:
    get:
      tags: [Audit]
      summary: Get latest issues (impact-sorted by default)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - in: query
          name: limit
          schema: { type: integer, minimum: 1, maximum: 500, default: 100 }
      responses:
        "200":
          description: Issues
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IssueList" }

  /projects/{project_id}/issues/diffs:
    get:
      tags: [Audit]
      summary: Compare issues between two crawl runs
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - in: query
          name: from_crawl_run_id
          schema: { type: string, format: uuid }
          required: true
        - in: query
          name: to_crawl_run_id
          schema: { type: string, format: uuid }
          required: true
      responses:
        "200":
          description: Diff
          content:
            application/json:
              schema: { $ref: "#/components/schemas/IssueDiffResponse" }

  /projects/{project_id}/performance/queries:
    get:
      tags: [Performance]
      summary: Query-level performance trends
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - $ref: "#/components/parameters/DateRangeStart"
        - $ref: "#/components/parameters/DateRangeEnd"
      responses:
        "200":
          description: Queries
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PerformanceQueryList" }

  /projects/{project_id}/performance/pages:
    get:
      tags: [Performance]
      summary: Page-level performance trends
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - $ref: "#/components/parameters/DateRangeStart"
        - $ref: "#/components/parameters/DateRangeEnd"
      responses:
        "200":
          description: Pages
          content:
            application/json:
              schema: { $ref: "#/components/schemas/PerformancePageList" }

  /projects/{project_id}/analytics/pages:
    get:
      tags: [Performance]
      summary: Page-level analytics trends
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - $ref: "#/components/parameters/DateRangeStart"
        - $ref: "#/components/parameters/DateRangeEnd"
      responses:
        "200":
          description: Analytics pages
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AnalyticsPageList" }

  /projects/{project_id}/opportunities/ctr:
    get:
      tags: [Performance]
      summary: CTR opportunities (high impressions, low CTR)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - $ref: "#/components/parameters/DateRangeStart"
        - $ref: "#/components/parameters/DateRangeEnd"
      responses:
        "200":
          description: CTR opportunities
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CtrOpportunityList" }

  /projects/{project_id}/backlinks/import:
    post:
      tags: [Backlinks]
      summary: Import backlinks from CSV
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file]
              properties:
                file: { type: string, format: binary }
                source: { type: string, description: "Source label (e.g., semrush_export)" }
      responses:
        "202":
          description: Import queued
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /projects/{project_id}/backlinks/new_lost:
    get:
      tags: [Backlinks]
      summary: New/lost backlinks over time (project merged sources)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - $ref: "#/components/parameters/DateRangeStart"
        - $ref: "#/components/parameters/DateRangeEnd"
      responses:
        "200":
          description: New/lost series
          content:
            application/json:
              schema: { $ref: "#/components/schemas/NewLostBacklinksResponse" }

  /projects/{project_id}/backlinks/targets:
    get:
      tags: [Backlinks]
      summary: Top linked target pages (project merged sources)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Targets
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BacklinkTargetList" }

  /projects/{project_id}/backlinks/anchors:
    get:
      tags: [Backlinks]
      summary: Anchor distribution (project merged sources)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Anchors
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BacklinkAnchorList" }

  /projects/{project_id}/backlinks/overlap:
    get:
      tags: [Backlinks]
      summary: Project overlap (ref domains) vs competitors
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - in: query
          name: competitors
          schema:
            type: array
            items: { type: string }
          style: form
          explode: true
          required: true
      responses:
        "200":
          description: Overlap
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DomainOverlapResponse" }

  /projects/{project_id}/backlinks/intersect:
    get:
      tags: [Backlinks]
      summary: Project intersect (domains linking to competitors but not project)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - in: query
          name: competitors
          schema:
            type: array
            items: { type: string }
          style: form
          explode: true
          required: true
      responses:
        "200":
          description: Intersect
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DomainIntersectResponse" }

  /commoncrawl/snapshots:
    get:
      tags: [CommonCrawl]
      summary: List Common Crawl snapshots (known/ingested)
      responses:
        "200":
          description: Snapshots
          content:
            application/json:
              schema: { $ref: "#/components/schemas/CommonCrawlSnapshotList" }

  /commoncrawl/ingest:
    post:
      tags: [CommonCrawl]
      summary: Trigger Common Crawl ingestion (operator/admin)
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/CommonCrawlIngestRequest" }
      responses:
        "202":
          description: Ingest queued
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /links/domain/{domain}/refdomains:
    get:
      tags: [CommonCrawl]
      summary: Referring domains for a domain (Common Crawl snapshot)
      parameters:
        - $ref: "#/components/parameters/Domain"
        - $ref: "#/components/parameters/SnapshotId"
        - in: query
          name: limit
          schema: { type: integer, default: 100, minimum: 1, maximum: 10000 }
      responses:
        "200":
          description: Referring domains
          content:
            application/json:
              schema: { $ref: "#/components/schemas/RefDomainList" }

  /links/domain/{domain}/backlinks:
    get:
      tags: [CommonCrawl]
      summary: Backlinks list for a domain (Common Crawl snapshot)
      parameters:
        - $ref: "#/components/parameters/Domain"
        - $ref: "#/components/parameters/SnapshotId"
        - in: query
          name: limit
          schema: { type: integer, default: 100, minimum: 1, maximum: 1000 }
        - in: query
          name: offset
          schema: { type: integer, default: 0, minimum: 0 }
      responses:
        "200":
          description: Backlinks
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BacklinkList" }

  /links/domain/{domain}/anchors:
    get:
      tags: [CommonCrawl]
      summary: Anchor distribution for a domain (Common Crawl snapshot)
      parameters:
        - $ref: "#/components/parameters/Domain"
        - $ref: "#/components/parameters/SnapshotId"
        - in: query
          name: limit
          schema: { type: integer, default: 100, minimum: 1, maximum: 10000 }
      responses:
        "200":
          description: Anchors
          content:
            application/json:
              schema: { $ref: "#/components/schemas/BacklinkAnchorList" }

  /links/domain/{domain}/new-lost:
    get:
      tags: [CommonCrawl]
      summary: New/lost backlinks between two snapshots (Common Crawl)
      parameters:
        - $ref: "#/components/parameters/Domain"
        - in: query
          name: snapshot_a
          schema: { type: string }
          required: true
        - in: query
          name: snapshot_b
          schema: { type: string }
          required: true
      responses:
        "200":
          description: New/lost
          content:
            application/json:
              schema: { $ref: "#/components/schemas/NewLostBacklinksResponse" }

  /links/domain/{domain}/overlap:
    get:
      tags: [CommonCrawl]
      summary: Referring-domain overlap between a domain and competitors (Common Crawl)
      parameters:
        - $ref: "#/components/parameters/Domain"
        - $ref: "#/components/parameters/SnapshotId"
        - in: query
          name: competitors
          schema:
            type: array
            items: { type: string }
          style: form
          explode: true
          required: true
      responses:
        "200":
          description: Overlap
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DomainOverlapResponse" }

  /links/domain/{domain}/intersect:
    get:
      tags: [CommonCrawl]
      summary: Link intersect (domains linking to competitors but not you) (Common Crawl)
      parameters:
        - $ref: "#/components/parameters/Domain"
        - $ref: "#/components/parameters/SnapshotId"
        - in: query
          name: competitors
          schema:
            type: array
            items: { type: string }
          style: form
          explode: true
          required: true
      responses:
        "200":
          description: Intersect
          content:
            application/json:
              schema: { $ref: "#/components/schemas/DomainIntersectResponse" }

  /projects/{project_id}/alerts:
    get:
      tags: [Alerts]
      summary: List alerts
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Alerts
          content:
            application/json:
              schema: { $ref: "#/components/schemas/AlertList" }

  /projects/{project_id}/alerts/rules:
    post:
      tags: [Alerts]
      summary: Create/update alert rules for a project
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/AlertRulesUpsert" }
      responses:
        "200":
          description: Updated
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /projects/{project_id}/exports:
    post:
      tags: [Exports]
      summary: Create an export (CSV/JSON/PDF)
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/ExportCreate" }
      responses:
        "202":
          description: Export queued
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Export" }
    get:
      tags: [Exports]
      summary: List exports
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Exports
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ExportList" }

  /projects/{project_id}/exports/schedule:
    post:
      tags: [Exports]
      summary: Schedule exports
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/ExportScheduleRequest" }
      responses:
        "200":
          description: Scheduled
          content:
            application/json:
              schema: { $ref: "#/components/schemas/OkResponse" }

  /projects/{project_id}/webhooks:
    post:
      tags: [Webhooks]
      summary: Create a webhook
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/WebhookCreate" }
      responses:
        "201":
          description: Created
          content:
            application/json:
              schema: { $ref: "#/components/schemas/Webhook" }
    get:
      tags: [Webhooks]
      summary: List webhooks
      parameters:
        - $ref: "#/components/parameters/ProjectId"
      responses:
        "200":
          description: Webhooks
          content:
            application/json:
              schema: { $ref: "#/components/schemas/WebhookList" }

  /projects/{project_id}/webhooks/{webhook_id}:
    delete:
      tags: [Webhooks]
      summary: Delete a webhook
      parameters:
        - $ref: "#/components/parameters/ProjectId"
        - $ref: "#/components/parameters/WebhookId"
      responses:
        "204":
          description: Deleted

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  parameters:
    ProjectId:
      in: path
      name: project_id
      required: true
      schema: { type: string, format: uuid }

    CrawlRunId:
      in: path
      name: crawl_run_id
      required: true
      schema: { type: string, format: uuid }

    IntegrationAccountId:
      in: path
      name: integration_account_id
      required: true
      schema: { type: string, format: uuid }

    WebhookId:
      in: path
      name: webhook_id
      required: true
      schema: { type: string, format: uuid }

    Provider:
      in: path
      name: provider
      required: true
      schema:
        type: string
        enum: [google_search_console, ga4, bing_webmaster, matomo, plausible, other]

    Domain:
      in: path
      name: domain
      required: true
      schema:
        type: string
        example: example.com

    SnapshotId:
      in: query
      name: snapshot_id
      required: false
      schema:
        type: string
        description: Optional snapshot selector; defaults to latest ingested snapshot.

    DateRangeStart:
      in: query
      name: start_date
      required: false
      schema: { type: string, format: date }

    DateRangeEnd:
      in: query
      name: end_date
      required: false
      schema: { type: string, format: date }

  responses:
    BadRequest:
      description: Bad request
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ErrorResponse" }
    Unauthorized:
      description: Unauthorized
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ErrorResponse" }
    NotFound:
      description: Not found
      content:
        application/json:
          schema: { $ref: "#/components/schemas/ErrorResponse" }

  schemas:
    HealthResponse:
      type: object
      properties:
        ok: { type: boolean }
        version: { type: string }
      required: [ok]

    OkResponse:
      type: object
      properties:
        ok: { type: boolean }
        message: { type: string }
      required: [ok]

    ErrorResponse:
      type: object
      properties:
        error:
          type: object
          properties:
            code: { type: string }
            message: { type: string }
            details: { type: object, additionalProperties: true }
          required: [code, message]
      required: [error]

    LoginRequest:
      type: object
      properties:
        email: { type: string, format: email }
        password: { type: string, format: password }
      required: [email, password]

    LoginResponse:
      type: object
      properties:
        access_token: { type: string }
        token_type: { type: string, example: bearer }
        expires_in: { type: integer, example: 3600 }
      required: [access_token, token_type]

    User:
      type: object
      properties:
        id: { type: string, format: uuid }
        email: { type: string, format: email }
        name: { type: string }
      required: [id, email]

    Project:
      type: object
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
        created_at: { type: string, format: date-time }
      required: [id, name]

    ProjectCreate:
      type: object
      properties:
        name: { type: string }
      required: [name]

    ProjectUpdate:
      type: object
      properties:
        name: { type: string }

    ProjectList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Project" }
      required: [items]

    ProjectSettings:
      type: object
      properties:
        seed_url: { type: string, example: "https://example.com/" }
        include_subdomains: { type: boolean, default: true }
        allowed_hosts:
          type: array
          items: { type: string }
        include_regexes:
          type: array
          items: { type: string }
        exclude_regexes:
          type: array
          items: { type: string }
        query_param_policy:
          type: string
          enum: [allow_all, strip_all, allowlist, denylist]
          default: strip_all
        query_param_allowlist:
          type: array
          items: { type: string }
        query_param_denylist:
          type: array
          items: { type: string }
        strip_tracking_params: { type: boolean, default: true }

        max_pages: { type: integer, default: 5000 }
        max_depth: { type: integer, default: 6 }
        concurrency_html: { type: integer, default: 16 }
        politeness_delay_ms: { type: integer, default: 0 }
        respect_robots: { type: boolean, default: true }
        use_sitemaps: { type: boolean, default: true }
        user_agent: { type: string, example: "oss-semrush-core/0.2 (+https://yourdomain)" }

        js_render_mode:
          type: string
          enum: [off, hybrid, js_only]
          default: hybrid
        max_rendered_pages: { type: integer, default: 200 }
        max_render_time_ms: { type: integer, default: 15000 }
        concurrency_js: { type: integer, default: 2 }
        required_selectors:
          type: array
          items: { type: string }
          description: Optional CSS selectors used by hybrid rendering heuristics.

        audit_frequency:
          type: string
          enum: [off, daily, weekly]
          default: weekly
        integration_sync_frequency:
          type: string
          enum: [daily, weekly]
          default: daily
        visibility_refresh_frequency:
          type: string
          enum: [daily, weekly]
          default: daily
        links_refresh_frequency:
          type: string
          enum: [off, monthly]
          default: monthly

        retain_audit_runs: { type: integer, default: 10 }
        retain_serp_snapshots_days: { type: integer, default: 90 }
        retain_raw_html_days: { type: integer, default: 0 }
      required: [seed_url]

    Site:
      type: object
      properties:
        id: { type: string, format: uuid }
        project_id: { type: string, format: uuid }
        domain: { type: string, example: example.com }
        base_url: { type: string, example: "https://example.com" }
      required: [id, project_id, domain, base_url]

    SiteCreate:
      type: object
      properties:
        domain: { type: string }
        base_url: { type: string }
      required: [domain, base_url]

    Competitor:
      type: object
      properties:
        id: { type: string, format: uuid }
        project_id: { type: string, format: uuid }
        domain: { type: string }
      required: [id, project_id, domain]

    CompetitorCreate:
      type: object
      properties:
        domain: { type: string }
      required: [domain]

    CompetitorList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Competitor" }
      required: [items]

    IntegrationConnectResponse:
      type: object
      properties:
        connect_url: { type: string }
        state: { type: string }
      required: [connect_url]

    OAuthCallbackRequest:
      type: object
      properties:
        code: { type: string }
        state: { type: string }
        redirect_uri: { type: string }
      required: [code, state]

    IntegrationAccount:
      type: object
      properties:
        id: { type: string, format: uuid }
        provider: { type: string }
        status: { type: string, enum: [connected, degraded, disconnected] }
        created_at: { type: string, format: date-time }
      required: [id, provider, status]

    IntegrationAccountList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/IntegrationAccount" }
      required: [items]

    IntegrationProperty:
      type: object
      properties:
        provider: { type: string }
        property_id: { type: string }
        display_name: { type: string }
      required: [provider, property_id]

    IntegrationPropertyList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/IntegrationProperty" }
      required: [items]

    IntegrationMapRequest:
      type: object
      properties:
        integration_account_id: { type: string, format: uuid }
        provider: { type: string }
        property_id: { type: string }
        site_id: { type: string, format: uuid }
      required: [integration_account_id, provider, property_id, site_id]

    IntegrationSyncRequest:
      type: object
      properties:
        provider: { type: string }
        property_id: { type: string }
        mode: { type: string, enum: [backfill, incremental] }
        start_date: { type: string, format: date }
        end_date: { type: string, format: date }

    CrawlRequest:
      type: object
      properties:
        site_id: { type: string, format: uuid }
        max_pages: { type: integer, default: 5000 }
        max_depth: { type: integer, default: 6 }
        concurrency: { type: integer, default: 16 }
        respect_robots: { type: boolean, default: true }
        use_sitemaps: { type: boolean, default: true }
        store_html: { type: boolean, default: false }
        js_render: { type: string, enum: [off, hybrid, js_only], default: hybrid }

    CrawlRun:
      type: object
      properties:
        id: { type: string, format: uuid }
        project_id: { type: string, format: uuid }
        site_id: { type: string, format: uuid }
        status: { type: string, enum: [queued, running, completed, failed] }
        started_at: { type: string, format: date-time, nullable: true }
        completed_at: { type: string, format: date-time, nullable: true }
        stats:
          type: object
          additionalProperties: true
      required: [id, project_id, site_id, status]

    CrawlRunList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/CrawlRun" }
      required: [items]

    Issue:
      type: object
      properties:
        id: { type: string, format: uuid }
        crawl_run_id: { type: string, format: uuid }
        issue_type_id: { type: string }
        category: { type: string }
        severity: { type: integer, minimum: 1, maximum: 5 }
        confidence: { type: number, minimum: 0, maximum: 1 }
        affected_url: { type: string }
        impact_score: { type: number }
        evidence: { type: object, additionalProperties: true }
      required: [id, crawl_run_id, issue_type_id, severity, confidence, affected_url]

    IssueList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Issue" }
      required: [items]

    IssueDiffResponse:
      type: object
      properties:
        from_crawl_run_id: { type: string, format: uuid }
        to_crawl_run_id: { type: string, format: uuid }
        added:
          type: array
          items: { $ref: "#/components/schemas/Issue" }
        resolved:
          type: array
          items: { $ref: "#/components/schemas/Issue" }
        changed:
          type: array
          items: { $ref: "#/components/schemas/Issue" }

    PerformanceQueryRow:
      type: object
      properties:
        query: { type: string }
        impressions: { type: integer }
        clicks: { type: integer }
        ctr: { type: number }
        avg_position: { type: number, nullable: true }
        top_page_url: { type: string, nullable: true }
      required: [query, impressions, clicks]

    PerformanceQueryList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/PerformanceQueryRow" }
      required: [items]

    PerformancePageRow:
      type: object
      properties:
        page_url: { type: string }
        impressions: { type: integer }
        clicks: { type: integer }
        ctr: { type: number }
        avg_position: { type: number, nullable: true }
      required: [page_url, impressions, clicks]

    PerformancePageList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/PerformancePageRow" }
      required: [items]

    AnalyticsPageRow:
      type: object
      properties:
        page_url: { type: string }
        sessions: { type: integer }
        users: { type: integer, nullable: true }
        conversions: { type: integer, nullable: true }
        revenue: { type: number, nullable: true }
      required: [page_url, sessions]

    AnalyticsPageList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/AnalyticsPageRow" }
      required: [items]

    CtrOpportunity:
      type: object
      properties:
        query: { type: string }
        page_url: { type: string, nullable: true }
        impressions: { type: integer }
        clicks: { type: integer }
        ctr: { type: number }
        suggested_action: { type: string }
      required: [query, impressions, clicks, ctr]

    CtrOpportunityList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/CtrOpportunity" }
      required: [items]

    NewLostBacklinksResponse:
      type: object
      properties:
        series:
          type: array
          items:
            type: object
            properties:
              date: { type: string, format: date }
              new: { type: integer }
              lost: { type: integer }
            required: [date, new, lost]
      required: [series]

    BacklinkTarget:
      type: object
      properties:
        target_url: { type: string }
        referring_domains: { type: integer }
        backlinks: { type: integer }
      required: [target_url, referring_domains, backlinks]

    BacklinkTargetList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/BacklinkTarget" }
      required: [items]

    BacklinkAnchor:
      type: object
      properties:
        anchor: { type: string }
        count: { type: integer }
      required: [anchor, count]

    BacklinkAnchorList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/BacklinkAnchor" }
      required: [items]

    BacklinkRow:
      type: object
      properties:
        source_url: { type: string }
        source_domain: { type: string }
        target_url: { type: string }
        target_domain: { type: string }
        anchor: { type: string, nullable: true }
        flags: { type: object, additionalProperties: true }
      required: [source_url, source_domain, target_url, target_domain]

    BacklinkList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/BacklinkRow" }
      required: [items]

    RefDomainRow:
      type: object
      properties:
        ref_domain: { type: string }
        backlinks: { type: integer }
        first_seen: { type: string, nullable: true }
        last_seen: { type: string, nullable: true }
      required: [ref_domain, backlinks]

    RefDomainList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/RefDomainRow" }
      required: [items]

    DomainOverlapResponse:
      type: object
      properties:
        domain: { type: string }
        competitors:
          type: array
          items: { type: string }
        shared_ref_domains:
          type: array
          items:
            type: object
            properties:
              ref_domain: { type: string }
              in_domain: { type: boolean }
              in_competitors:
                type: object
                additionalProperties: { type: boolean }
            required: [ref_domain, in_domain, in_competitors]
      required: [domain, competitors, shared_ref_domains]

    DomainIntersectResponse:
      type: object
      properties:
        domain: { type: string }
        competitors:
          type: array
          items: { type: string }
        intersect_ref_domains:
          type: array
          items:
            type: object
            properties:
              ref_domain: { type: string }
              links_to_competitors:
                type: object
                additionalProperties: { type: boolean }
            required: [ref_domain, links_to_competitors]
      required: [domain, competitors, intersect_ref_domains]

    Alert:
      type: object
      properties:
        id: { type: string, format: uuid }
        kind: { type: string }
        entity_type: { type: string, enum: [project, page, query] }
        entity_key: { type: string }
        severity: { type: string, enum: [info, warn, critical] }
        created_at: { type: string, format: date-time }
        payload: { type: object, additionalProperties: true }
      required: [id, kind, entity_type, entity_key, severity, created_at]

    AlertList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Alert" }
      required: [items]

    AlertRulesUpsert:
      type: object
      properties:
        visibility_drop_threshold_pct: { type: number, default: 30 }
        ctr_opportunity_min_impressions: { type: integer, default: 1000 }
        regression_issue_delta_threshold: { type: integer, default: 10 }

    Export:
      type: object
      properties:
        id: { type: string, format: uuid }
        format: { type: string, enum: [csv, json, pdf] }
        status: { type: string, enum: [queued, running, completed, failed] }
        download_url: { type: string, nullable: true }
        created_at: { type: string, format: date-time }
      required: [id, format, status, created_at]

    ExportCreate:
      type: object
      properties:
        format: { type: string, enum: [csv, json, pdf] }
        resource: { type: string }
        params: { type: object, additionalProperties: true }
      required: [format, resource]

    ExportList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Export" }
      required: [items]

    ExportScheduleRequest:
      type: object
      properties:
        format: { type: string, enum: [csv, json, pdf] }
        resource: { type: string }
        cron: { type: string, example: "0 9 * * 1" }
        timezone: { type: string, example: "America/Los_Angeles" }
        params: { type: object, additionalProperties: true }
      required: [format, resource, cron]

    Webhook:
      type: object
      properties:
        id: { type: string, format: uuid }
        url: { type: string }
        events:
          type: array
          items: { type: string }
        is_enabled: { type: boolean }
        created_at: { type: string, format: date-time }
      required: [id, url, events, is_enabled, created_at]

    WebhookCreate:
      type: object
      properties:
        url: { type: string }
        secret: { type: string }
        events:
          type: array
          items:
            type: string
            enum: [crawl.completed, alert.fired, integration.sync_failed, export.completed, commoncrawl.ingest_completed]
      required: [url, secret, events]

    WebhookList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Webhook" }
      required: [items]

    CommonCrawlSnapshot:
      type: object
      properties:
        snapshot_id: { type: string, example: "CC-MAIN-2025-05" }
        status: { type: string, enum: [known, ingesting, ingested, failed] }
        ingested_at: { type: string, format: date-time, nullable: true }
        notes: { type: string, nullable: true }
      required: [snapshot_id, status]

    CommonCrawlSnapshotList:
      type: object
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/CommonCrawlSnapshot" }
      required: [items]

    CommonCrawlIngestRequest:
      type: object
      properties:
        snapshot_id: { type: string, example: "CC-MAIN-2025-05" }
        subset:
          type: object
          description: Optional subset spec (partitions, domain allowlists, limits).
          additionalProperties: true
        build_aggregates: { type: boolean, default: true }
      required: [snapshot_id]
```

---

## `.github/ISSUE_TEMPLATE/mvp-checklist.yml`

```yaml
name: "✅ MVP Checklist"
description: "Track MVP completion for OSS Semrush-core (Hybrid Audit + Integrations + Common Crawl Backlinks)."
title: "MVP Checklist: <epic/milestone>"
labels: ["mvp", "tracking"]
body:
  - type: markdown
    attributes:
      value: |
        Use this checklist to track MVP completion. Keep it updated as items are delivered.
        Recommended workflow:
        - Create one checklist per milestone/epic (Integrations, Audit, Common Crawl, Backlinks, Reports)
        - Link supporting issues/PRs next to each checkbox

  - type: input
    id: owner
    attributes:
      label: Owner
      placeholder: "@your-handle"
    validations:
      required: true

  - type: input
    id: milestone
    attributes:
      label: Milestone
      placeholder: "MVP Phase 1"
    validations:
      required: false

  - type: textarea
    id: scope
    attributes:
      label: Scope / Notes
      placeholder: |
        Links:
        - PRD.md
        - docs/ARCHITECTURE.md
        - openapi.yaml
    validations:
      required: false

  - type: markdown
    attributes:
      value: "## Phase 0 — Skeleton"

  - type: checkboxes
    id: phase0
    attributes:
      label: Platform skeleton
      options:
        - label: FastAPI bootstrapped (`apps/api`) with auth scaffolding
        - label: Postgres schema + migrations framework in place
        - label: Redis queue wired + worker runner skeleton
        - label: Docker Compose boots core services (api, postgres, redis, minio)
        - label: Health endpoints (`/healthz`, `/readyz`) implemented
        - label: Basic Projects CRUD endpoints implemented
        - label: OpenAPI served (or generated) and matches `openapi.yaml` baseline

  - type: markdown
    attributes:
      value: "## Phase 0b — Project Settings (Scope/Budgets/Retention)"

  - type: checkboxes
    id: phase0b
    attributes:
      label: Project settings
      options:
        - label: Settings model implemented (include/exclude regex, query param policy, budgets, retention, schedules)
        - label: Settings endpoints implemented (`GET/PUT /projects/{id}/settings`)
        - label: Settings enforced by crawler scope (allowed hosts, include/exclude, query params)
        - label: Settings snapshot stored per crawl_run for reproducibility

  - type: markdown
    attributes:
      value: "## Phase 1 — Integrations + Normalization (MVP Core)"

  - type: checkboxes
    id: phase1
    attributes:
      label: Integrations
      options:
        - label: OAuth connect/callback flows implemented for providers
        - label: Token storage encrypted + refresh handling
        - label: Provider property discovery implemented
        - label: Property → Project/Site mapping implemented
        - label: Daily incremental sync scheduler implemented
        - label: Backfill mode implemented (chunked date ranges)
        - label: Canonical fact tables implemented (`search_fact_daily`, `analytics_fact_daily`, `link_facts` when available)
        - label: Data quality flags recorded (sampling/thresholds/missing dims)
        - label: GSC adapter implemented and syncing
        - label: GA4 adapter implemented and syncing
        - label: Bing Webmaster adapter implemented and syncing
        - label: Sync status endpoints show last sync time + errors

  - type: markdown
    attributes:
      value: "## Phase 2 — Hybrid Crawl + Audit + Diffs (MVP Core)"

  - type: checkboxes
    id: phase2
    attributes:
      label: Crawl & Audit
      options:
        - label: Crawl trigger endpoint implemented (`POST /projects/{id}/crawls`)
        - label: Crawl run state machine (queued/running/completed/failed)
        - label: robots.txt respected by default + sitemap discovery enabled by default
        - label: URL normalization rules implemented (tracking params stripping + allow/deny policy)
        - label: HTML page fetch records stored (`crawl_pages`)
        - label: Link extraction stored (`link_edges`)
        - label: Hybrid mode implemented (HTML-first + Playwright fallback)
        - label: Hybrid heuristics implemented (thin DOM/text, SPA shell, required selectors missing, client-side redirects)
        - label: Playwright budgets enforced (max rendered pages, per-page timeout, separate JS concurrency)
        - label: Rendered vs non-rendered evidence visible on page detail
        - label: Rules engine implemented with MVP checks + stable issue taxonomy
        - label: Impact score implemented (joins to canonical facts last 28d)
        - label: Audit view returns impact-sorted issues
        - label: Crawl-to-crawl diffs implemented (added/resolved/changed issues)
        - label: Regression summary (“top 10 regressions”) implemented

  - type: markdown
    attributes:
      value: "## Phase 2b — Visibility + Alerts (MVP Core)"

  - type: checkboxes
    id: phase2b
    attributes:
      label: Visibility & Alerts
      options:
        - label: Query trends endpoint implemented (`/performance/queries`)
        - label: Page trends endpoint implemented (`/performance/pages`)
        - label: Analytics pages endpoint implemented (`/analytics/pages`)
        - label: CTR opportunities endpoint implemented (`/opportunities/ctr`)
        - label: Alert engine computes visibility drops (query/page)
        - label: Alert rules configurable (`/alerts/rules`)
        - label: Alerts listed via endpoint (`/alerts`)
        - label: Webhook event `alert.fired` delivered (at-least-once)

  - type: markdown
    attributes:
      value: "## Phase 3 — Common Crawl Ingestion (Core MVP Backlinks)"

  - type: checkboxes
    id: phase3
    attributes:
      label: Common Crawl ingestion + explorer
      options:
        - label: Snapshot registry implemented (`GET /commoncrawl/snapshots`)
        - label: Ingest trigger endpoint implemented (`POST /commoncrawl/ingest`) (operator/admin)
        - label: Ingest pipeline implemented (WAT-first or chosen approach) and writes raw edges (ClickHouse recommended)
        - label: Aggregates/materializations built (ref domains, anchors, counts)
        - label: Domain backlinks explorer endpoints implemented (`/links/domain/{domain}/...`)
        - label: New/lost between two snapshots implemented (`/links/domain/{domain}/new-lost`)
        - label: Competitive overlap implemented (`/links/domain/{domain}/overlap`)
        - label: Competitive intersect implemented (`/links/domain/{domain}/intersect`)
        - label: Ingest status/progress visible (admin endpoint or logs + status table)

  - type: markdown
    attributes:
      value: "## Phase 3b — Project Backlinks (Multi-source merge)"

  - type: checkboxes
    id: phase3b
    attributes:
      label: Project backlinks merge
      options:
        - label: CSV backlink import endpoint implemented and queues ingestion
        - label: Provider links ingested into `link_facts` where available
        - label: Project backlink views merge Common Crawl + imports + provider links (+ optional community edges)
        - label: Project overlap/intersect endpoints implemented (project domain vs competitors)
        - label: Optional opt-in community-fed link edges stored (hashed-by-default)

  - type: markdown
    attributes:
      value: "## Phase 4 — Reports + Exports + Webhooks"

  - type: checkboxes
    id: phase4
    attributes:
      label: Reporting & Webhooks
      options:
        - label: PDF reporting pipeline implemented (HTML → PDF)
        - label: Scheduled exports implemented (cron/timezone)
        - label: Exports list endpoint implemented with status tracking
        - label: Webhook configuration endpoints implemented
        - label: Webhook signature (HMAC) implemented
        - label: Webhook event `crawl.completed` delivered (at-least-once)
        - label: Webhook event `export.completed` delivered (at-least-once)
        - label: Webhook event `commoncrawl.ingest_completed` delivered (at-least-once)

  - type: markdown
    attributes:
      value: "## Optional hardening"

  - type: checkboxes
    id: optional
    attributes:
      label: Hardening
      options:
        - label: Rate limiting for crawl triggers and export endpoints
        - label: Per-project concurrency caps for crawler
        - label: Integration sync retry/backoff policies tested
        - label: ClickHouse enabled for edges at scale (partitioning + TTL)
        - label: End-to-end smoke tests in CI
        - label: Seed data + demo fixtures

  - type: textarea
    id: risks
    attributes:
      label: Risks / Blockers
      placeholder: |
        - Provider quotas / OAuth scope issues
        - URL normalization edge cases
        - Crawl politeness + performance constraints
        - Common Crawl ingest scale / storage
        - PDF rendering reliability
    validations:
      required: false
```

---

# Common Crawl ingestion spec (exact pipeline choices + storage + schema + MVP subset plan)

This spec is designed to be **MVP-feasible** while still giving you *real backlink/competitive intel* from open data.

## 1) Formats choice: WARC vs WAT vs WET

Common Crawl publishes three relevant formats:

* **WARC**: raw crawl records (full HTTP responses). ([Common Crawl][1])
* **WAT**: computed metadata derived from WARC (includes extracted metadata and link-related fields; anchor text improvements have been discussed by Common Crawl). ([Common Crawl][1])
* **WET**: extracted plaintext for NLP (not needed for backlinks). ([Common Crawl][2])

### MVP decision

**Use WAT-first for link extraction**, fall back to WARC parsing only if you hit metadata gaps.

Why:

* Parsing WARC HTML at scale is expensive and slow.
* WAT is specifically intended to store computed metadata, and it’s the closest “ready-made” input for link graph extraction. ([Common Crawl][1])
* WET is irrelevant for backlinks; keep it for future keyword/content analysis only. ([Common Crawl][2])

## 2) Indexing strategy: CDX (ZipNum) + snapshot manifests

Common Crawl provides an index for each crawl collection, commonly referred to as **CDX in ZipNum format**. ([Common Crawl][3])
This index allows you to locate records by URL and filter by fields like status (e.g., process only HTTP 200). ([Common Crawl][4])

### MVP index usage

You’ll use the index primarily to:

* discover **which segments** contain captures you care about (for subset ingestion)
* filter to likely useful records (e.g., `status=200`, HTML responses)
* avoid downloading WAT/WARC segments blindly

## 3) MVP subset strategy (so you can ship fast)

Full-corpus ingestion is enormous. MVP should intentionally ingest a **small-but-useful** subset.

Pick **one** of these MVP strategies (A is recommended):

### A) “User-demand + cache” (recommended)

* Ingest on demand for **domains the user searches** in the backlink explorer.
* Maintain a cache keyed by `(snapshot_id, target_domain)` of aggregates:

  * referring domains
  * top anchors
  * sample backlinks list
* This keeps ingestion proportional to product usage.

How it works:

1. User requests `/links/domain/{domain}/refdomains?snapshot_id=...`
2. If cache miss: enqueue job `commoncrawl.build_domain_aggregates(snapshot_id, domain)`
3. Worker uses CDX+WAT scanning with domain-level filtering to build aggregates for that domain
4. Store aggregates in ClickHouse (fast query) + Postgres metadata (job status)

### B) “Top N domains” (good for demos)

* Choose a popularity list seed (e.g., Tranco) and ingest top 50k–200k domains.
* Provides instant backlink explorer results for popular sites, but still heavy.

### C) “Vertical-focused” (best for go-to-market)

* Ingest only SaaS/ecom/local vertical domains that match your ICP.
* Bootstraps “competitive overlap” where users care most.

## 4) Ingestion pipeline design (WAT-first)

### 4.1 Snapshot registry

Store in Postgres:

* `commoncrawl_snapshots(snapshot_id, status, ingested_at, spec_json, notes)`
* `commoncrawl_jobs(job_id, snapshot_id, job_type, status, started_at, finished_at, progress_json, error)`

### 4.2 Work units

Partition work by:

* `(snapshot_id, segment_id)` or `(snapshot_id, wat_file_path)` depending on manifests
* Each unit:

  * downloads (or streams) a WAT file
  * parses JSON records line-by-line
  * emits edges `(src_url, src_domain, dst_url, dst_domain, anchor?, rel_flags?)`

### 4.3 Filtering during ingest (critical for MVP feasibility)

Apply early filters:

* skip non-HTML captures where possible (using index metadata)
* emit only edges that match:

  * `dst_domain == target_domain` (for on-demand domain builds)
  * OR `dst_domain in allowlist` (for top-N or vertical builds)
* optionally exclude “technical asset” edges (images/fonts/js) by:

  * file extension heuristics on `dst_url` (fast)
  * content-type hints if present in metadata

### 4.4 Dedupe & counting strategy

For backlink explorer you mostly need:

* counts per referring domain
* representative sample backlinks
* anchor distribution

So you can avoid storing every raw edge in MVP.

MVP approach:

* Maintain streaming aggregators:

  * `ref_domain -> count`
  * `anchor -> count` (bounded top-K; use space-saving algorithm)
  * sample backlink rows (reservoir sample per ref_domain)
* Write aggregates directly (plus samples), optionally also write raw edges if ClickHouse capacity allows.

## 5) Storage layout

### 5.1 Postgres

Use Postgres for:

* snapshot registry
* job status/progress
* small aggregates for tiny subsets
* API metadata and caching keys

Example tables:

* `commoncrawl_snapshots`
* `commoncrawl_jobs`
* `domain_backlink_cache_keys(snapshot_id, target_domain, status, updated_at, row_counts_json)`

### 5.2 ClickHouse (recommended core for MVP if Common Crawl is enabled)

Use ClickHouse for:

* aggregates (fast group-by, top-N, overlaps)
* optional raw edges if you want deeper functionality later

#### Partitioning & TTL

* Partition by `snapshot_id` (and optionally month)
* Optional TTL:

  * keep only last N snapshots (e.g., last 2–4)
  * keep raw edges shorter than aggregates

## 6) ClickHouse schema (recommended)

### 6.1 `cc_edge_sample` (optional, sampled backlinks list)

Stores a sampled set of backlink rows for UI display.

```sql
CREATE TABLE IF NOT EXISTS cc_edge_sample (
  snapshot_id LowCardinality(String),
  target_domain LowCardinality(String),
  source_domain LowCardinality(String),
  source_url String,
  target_url String,
  anchor String,
  flags UInt32,
  first_seen Date DEFAULT toDate(now()),
  last_seen Date DEFAULT toDate(now())
)
ENGINE = MergeTree
PARTITION BY snapshot_id
ORDER BY (target_domain, source_domain, cityHash64(source_url))
SETTINGS index_granularity = 8192;
```

Notes:

* `flags` bitfield: nofollow/ugc/sponsored/other
* Keep this table bounded by sampling rather than full volume.

### 6.2 `cc_ref_domain_agg` (core)

```sql
CREATE TABLE IF NOT EXISTS cc_ref_domain_agg (
  snapshot_id LowCardinality(String),
  target_domain LowCardinality(String),
  ref_domain LowCardinality(String),
  backlinks UInt64,
  first_seen Date,
  last_seen Date
)
ENGINE = SummingMergeTree
PARTITION BY snapshot_id
ORDER BY (target_domain, ref_domain);
```

### 6.3 `cc_anchor_agg` (core)

```sql
CREATE TABLE IF NOT EXISTS cc_anchor_agg (
  snapshot_id LowCardinality(String),
  target_domain LowCardinality(String),
  anchor String,
  cnt UInt64
)
ENGINE = SummingMergeTree
PARTITION BY snapshot_id
ORDER BY (target_domain, cityHash64(anchor));
```

### 6.4 `cc_ref_domain_set` (optional helper for overlap/intersect)

Store a set-like representation:

```sql
CREATE TABLE IF NOT EXISTS cc_ref_domain_set (
  snapshot_id LowCardinality(String),
  target_domain LowCardinality(String),
  ref_domain LowCardinality(String),
  backlinks UInt64
)
ENGINE = MergeTree
PARTITION BY snapshot_id
ORDER BY (target_domain, ref_domain);
```

Then:

* overlap = intersection on `ref_domain`
* intersect = competitors’ ref_domains minus domain’s ref_domains

## 7) New/Lost between snapshots

Use two snapshot IDs:

* A (older), B (newer)

Compute:

* **new**: ref_domains present in B but not A
* **lost**: ref_domains present in A but not B
  Optionally measure deltas in backlink counts as well.

Implementation choices:

* On-demand query-time diff (fast if aggregates are materialized)
* Or materialize diff tables for popular domains

## 8) Competitive overlap/intersect (MVP)

Given `domain` and `competitors[]`:

* Overlap: `ref_domains(domain) ∩ ref_domains(competitor_i)` (and optionally union across competitors)
* Intersect: `ref_domains(competitors union) - ref_domains(domain)`

Compute against `cc_ref_domain_set` for chosen `snapshot_id`.

## 9) Operational notes

* Expect duplicates in crawl captures; handle idempotency on ingest jobs. ([Google Groups][5])
* Use index filtering to avoid processing non-200 or non-HTML records. ([Google Groups][6])
* Keep ingestion resumable:

  * store “processed file paths / segments” and checkpoint progress.

## 10) Sources for the above (Common Crawl docs)

* Format definitions (WARC/WAT/WET) and their purpose. ([Common Crawl][1])
* Index format and purpose (ZipNum CDX). ([Common Crawl][3])
* Notes on WAT anchor text improvements. ([Common Crawl][7])
* Web graph releases (host/domain graph datasets) if you later want domain-level link graph seeds. ([Common Crawl][8])

---

[1]: https://commoncrawl.org/blog/navigating-the-warc-file-format?utm_source=chatgpt.com "Navigating the WARC file format"
[2]: https://commoncrawl.org/blog/web-archiving-file-formats-explained?utm_source=chatgpt.com "Web Archiving File Formats Explained"
[3]: https://commoncrawl.org/blog/announcing-the-common-crawl-index?utm_source=chatgpt.com "Announcing the Common Crawl Index!"
[4]: https://commoncrawl.org/get-started?utm_source=chatgpt.com "Common Crawl - Get Started"
[5]: https://groups.google.com/g/common-crawl/c/DdEjqaVRwfg/m/Y1zUd0dIAwAJ?utm_source=chatgpt.com "Pages versus URLs, and uniqueness of WAT file entries"
[6]: https://groups.google.com/g/common-crawl/c/xTER7EJ5kuc?utm_source=chatgpt.com "How to obtain the text content from WET files for specific ..."
[7]: https://commoncrawl.org/blog/sep-oct-2022-crawl-archive-now-available?utm_source=chatgpt.com "September/October 2022 crawl archive now available"
[8]: https://commoncrawl.org/web-graphs?utm_source=chatgpt.com "Web Graphs"
