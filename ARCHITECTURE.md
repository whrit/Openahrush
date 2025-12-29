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

Schema defined in `infra/clickhouse/cc_schema.sql`:

**Tables:**
- `cc_edges`: Raw link edges from Common Crawl (billions of rows)
  - Columns: snapshot_id, source_url, source_domain, target_url, target_domain, anchor, rel_nofollow, rel_ugc, rel_sponsored, discovered_at
  - Engine: MergeTree()
  - Partition: (snapshot_id, substring(target_domain, 1, 2))
  - Order: (target_domain, source_domain, source_url)

- `cc_snapshots`: Snapshot registry and status tracking
  - Engine: ReplacingMergeTree(updated_at)

**Materialized Views (auto-updated on insert):**
- `cc_refdomains_mv`: Referring domain aggregates per target domain
  - Engine: SummingMergeTree()
- `cc_anchors_mv`: Anchor text distribution per target domain
  - Engine: SummingMergeTree()
- `cc_domain_stats_mv`: Quick domain-level stats (total backlinks, unique ref domains)
  - Engine: SummingMergeTree()

**Helper Views:**
- `cc_top_refdomains`: Top referring domains by backlink count
- `cc_top_anchors`: Top anchor texts by usage count
- `cc_domain_overview`: Aggregated domain stats across snapshots

**Design Rationale:**
- LowCardinality(String) for domains: Dictionary encoding for repeated values
- SummingMergeTree for aggregates: Automatic incremental aggregation on merge
- Partition by snapshot + domain prefix: Efficient pruning and parallel processing
- Order by target_domain first: Optimized for "backlinks to domain X" queries

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