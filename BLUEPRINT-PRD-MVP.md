# BLUEPRINT-PRD-MVP.md — Openahrush (MVP)
**Python-first control plane + Rust data plane** • **Self-hostable** • **Truth-first integrations** • **Free data moat (Common Crawl + your crawls + opt-in aggregation)**

## 1) Summary

Build an open-source, self-hostable SEO platform that delivers a Semrush-like “Projects” workflow:

- **Projects**: sites, competitors, keyword sets, locations/devices, schedules, retention, budgets
- **Integrations (MVP core)**: Google Search Console (GSC), Google Analytics (GA4), Bing Webmaster Tools (BWT)
- **Site Audit (Hybrid crawl)**: HTML-first crawling with **Playwright fallback** for pages that look JS-dependent; rules → issues → diffs
- **Impact-aware prioritization**: prioritize issues using integrated impressions/sessions/conversions
- **Visibility / Rank**: first-party search performance as default; optional SERP snapshot providers (BYO key)
- **Backlinks (MVP)**:
  - **Common Crawl ingestion (core MVP)** for a free backlink explorer + competitive overlap/intersect
  - plus: crawl-discovered edges, provider links (where available), CSV imports, opt-in community-fed graph (hashed)
- **Reports + Exports**: dashboards + scheduled PDF/CSV/JSON + API + webhooks

Design goal: generate as much value as possible without paying for large datasets by combining:
- first-party integrations (truth)
- open web corpus ingestion (Common Crawl)
- your own crawl corpus (content + internal link graph)
- opt-in community aggregation (privacy-forward)

---

## 2) Goals

### Product goals (MVP)
1. User connects **GSC + GA4 + BWT**, maps properties to a Project, and sees immediate performance dashboards.
2. User runs a **Site Audit** and gets a prioritized fix list tied to real impressions/sessions/conversions.
3. User tracks **visibility changes** and gets alerts for significant drops/spikes.
4. User explores **backlinks and referring domains** using:
   - Common Crawl link snapshots (open corpus)
   - plus additional sources (imports, provider links, crawl-discovered edges)
5. User sees **competitive link overlap/intersect** for a target domain vs competitors.
6. User exports weekly **PDF** and **CSV/JSON**, integrates via API/webhooks, and self-hosts via Docker Compose.

### Technical goals (MVP)
- Python for orchestration/rules/integrations; Rust for high-throughput crawl/fetch/parse when applicable.
- Provider-pluggable contracts (integrations + SERP) so “all engines” can expand cleanly.
- Deterministic, reproducible scoring with explicit provenance and confidence.

---

## 3) Non-goals (MVP)

- Internet-wide backlink index parity with Semrush (we start with Common Crawl snapshots + incremental improvements).
- Clickstream-based competitor traffic estimation (panel/third-party estimates are v2+ only).
- Full ads intelligence with long archives (owned PPC may be v1+; competitor ads optional module).
- Any browser automation intended to bypass bot protections or violate ToS (SERP is provider-based).

---

## 4) Users / Personas

- **SEO lead / Growth**: wants prioritized fixes, weekly reporting, competitive link insights.
- **SEO engineer**: wants APIs, reproducibility, CI gates, automation hooks.
- **Agency**: multi-client projects, schedules, exports.

---

## 5) Scope

### 5.1 MVP features

#### A) Projects (with a full settings spec)
Projects are the unit of configuration, scheduling, retention, and budgets.

**Must**
- Create Projects
- Add: primary site + competitor domains
- Configure: locale/device preferences, schedules, retention, budgets
- Expose health: last audit run, last sync, last link snapshot ingest, last alerts

**Project settings (MVP spec)**
- `seed_url` (e.g., https://example.com/)
- Scope
  - `include_subdomains` (bool)
  - `allowed_hosts` (list; default derived from seed)
  - `allowed_schemes` (https/http; default https+http)
- URL patterns
  - `include_regexes` (list)
  - `exclude_regexes` (list)
- Query parameter rules
  - `query_param_policy` (enum: `allow_all` | `strip_all` | `allowlist` | `denylist`)
  - `query_param_allowlist` (list)
  - `query_param_denylist` (list)
  - `strip_tracking_params` (bool; default true; e.g., utm_*, gclid, fbclid)
- Crawl budgets
  - `max_pages` (int)
  - `max_depth` (int)
  - `concurrency_html` (int)
  - `politeness_delay_ms` (int)
  - `respect_robots` (bool; default true)
  - `use_sitemaps` (bool; default true)
  - `user_agent` (string)
- Hybrid rendering budgets (Playwright)
  - `js_render_mode` (enum: `off` | `hybrid` | `js_only`)
  - `max_rendered_pages` (int)
  - `max_render_time_ms` (int per page)
  - `concurrency_js` (int, separate from HTML concurrency)
- Schedules
  - `audit_frequency` (off/daily/weekly)
  - `integration_sync_frequency` (daily default)
  - `visibility_refresh_frequency` (daily/weekly)
  - `links_refresh_frequency` (depends on ingestion cadence; default monthly snapshot)
- Retention policy
  - `retain_audit_runs` (keep last N runs)
  - `retain_serp_snapshots_days` (N days; if enabled)
  - `retain_raw_html_days` (N days; if enabled)
  - `retain_clickhouse_rollups_days` (if enabled)

Optional MVP-lite:
- Teams/workspaces + roles (admin/editor/viewer)

---

#### B) Integrations (MVP core)
**Supported connectors**
- Google Search Console
- Google Analytics (GA4)
- Bing Webmaster Tools

**Connector requirements**
- OAuth + property selection + mapping to Project/Site
- Daily incremental sync + initial backfill
- Quotas/rate limits + retries
- Data quality flags (sampling/thresholds/missing dims)
- Writes canonical facts (engine-agnostic)

**All search engines strategy**
- Adapters are pluggable.
- For engines without accessible APIs: CSV import flows map into canonical schema.

---

#### C) Site Audit (Hybrid HTML-first + Playwright fallback)
**Core requirement:** ship Hybrid crawl as MVP, not optional.

##### Crawl modes
- **HTML-only** (supported)
- **Hybrid (MVP default)**: HTML-first; selectively render with Playwright when heuristic triggers
- **JS-only** (supported, optional per project; higher cost)

##### Hybrid fallback heuristics (MVP explicit)
After fetching HTML, mark a page for JS rendering if ANY of:

**(1) Thin/empty DOM heuristic**
- extracted visible text < `min_text_chars` (default 200), OR
- word count < `min_word_count` (default 50), OR
- body is mostly scripts/links with minimal text

**(2) SPA shell heuristic**
- body contains only a small number of root nodes (e.g., one `#root`/`#app` div)
- plus presence of common SPA bundles (`app.*.js`, `chunk.*.js`, `main.*.js`) OR framework markers

**(3) Critical selector missing heuristic (project-configurable)**
- user specifies CSS selectors that must exist (e.g., `h1`, `.product-title`, `main article`)
- HTML parse does not find them

**(4) Canonical/meta/structured signals missing**
- canonical missing AND page is supposed to be indexable
- meta robots missing AND page looks like a template where it should exist (optional)
- NOTE: keep this light; avoid over-triggering renders

**(5) Client-side redirect heuristic**
- HTML includes immediate JS redirect patterns (`window.location`, meta refresh)
- fetch final URL differs suspiciously from canonical patterns

##### Render budgets (MVP)
- `max_rendered_pages` per run (default 200)
- `max_render_time_ms` per page (default 15000)
- separate concurrency:
  - `concurrency_html` (default 16)
  - `concurrency_js` (default 2–4)

##### Collected fields (per page)
- final URL after redirects
- status code, content type
- response time
- title, meta description, canonical
- meta robots (index/noindex)
- H1 count + first H1
- basic word count + text length
- internal outlinks + broken internal links targets
- (Hybrid) rendered HTML snapshot hash + extracted fields
- content hashes (html hash, rendered hash)

##### Issue rules (MVP)
**Critical**
- 5xx pages
- redirect loops / excessive chains
- broken internal links (targets 4xx/5xx)

**High**
- internal 4xx pages
- missing title
- duplicate title (exact)
- canonical issues (missing self canonical; canonical to different domain)

**Medium**
- title too long/short
- meta description too long/short
- missing meta description (configurable)
- missing H1 / multiple H1s
- non-https URLs (if project is https)
- mixed content

**Low**
- thin content (word count below threshold)
- orphan pages (sitemap-only not internally linked)

##### Outputs
- Audit summary dashboard
- Issues table (filter/sort/paginate/export)
- Pages table (filter/sort/paginate)
- Page detail view with evidence
- Diff vs last run (new/resolved, deltas)

**Impact-aware prioritization**
- Every issue is scored by:
  - `impact_score = severity * confidence * traffic_weight`
  - `traffic_weight` derived from last 28 days of canonical facts (impressions/sessions/conversions)

---

#### D) Visibility / Rank Tracking (MVP)
Default: visibility derived from canonical first-party search facts
- query/page trends
- CTR opportunities
- cannibalization hints (query→page mapping shifts)
- alerts for significant changes

Optional module:
- SERP snapshot providers (BYO key) for strict rank + SERP features

---

#### E) Backlinks (MVP: multi-source, includes Common Crawl core)
Backlinks are built from multiple sources and normalized into a common link model.

##### Sources (MVP)
1) **Common Crawl ingestion (core MVP)**
2) Provider links (GSC/BWT, where available)
3) CSV imports
4) Crawl-discovered edges (outbound/internal; used for context and enrichment)
5) Opt-in community-fed graph (hashed) (MVP-lite)

##### Common Crawl ingestion requirements (MVP)
- Ingest at least:
  - one “latest” snapshot subset OR one monthly snapshot, plus a second snapshot for new/lost comparisons
- Store:
  - source_url, target_url
  - source_domain, target_domain
  - anchor (if available / parseable)
  - rel flags where parseable (nofollow/ugc/sponsored)
  - snapshot_id + first_seen/last_seen (by snapshot)

##### Backlink explorer views (MVP)
- Referring domains
- Backlinks list with filters (domain, target path, anchor, flags)
- Anchors summary
- New/lost links between two ingested snapshots
- Competitive:
  - overlap (shared referring domains)
  - intersect (domains linking to competitors but not you)

##### Storage strategy
- MVP can store a subset in Postgres for initial implementation.
- Recommended: ClickHouse for large edge volumes (feature flag); keep aggregates/materializations.

---

#### F) Reports + Exports + API
Dashboards:
- Overview (audit health + search + analytics + link overview)
- Audit issues (ranked by impact)
- Performance (queries/pages trends)
- Backlinks (ref domains, new/lost, overlap/intersect)

Exports:
- CSV/JSON exports everywhere
- Scheduled PDF reports (HTML template → PDF)

API + Webhooks:
- REST endpoints for core entities
- webhooks for crawl completion + alert firing + integration failures + export completed

---

## 6) Architecture (summary)

### Control plane (Python)
- `apps/api` (FastAPI): public API + dashboards
- `apps/integrations`: OAuth + adapters + normalization
- `apps/workers`: orchestration + rules + diffs + alerts
- `apps/reports`: PDF + exports

### Data plane (Rust)
- `crates/crawler`: frontier + fetch + parse + extraction

### Storage
- Postgres (system of record)
- Redis (queues)
- MinIO/S3 (artifacts, exports)
- Optional ClickHouse (edges/time-series)

---

## 7) Provider adapter contracts

### SearchAdapter
- `list_properties()`
- `fetch_search_performance(property_id, date_range, dimensions)`
- `fetch_links(property_id)` (if supported)
- `fetch_sitemaps(property_id)` (if supported)

### AnalyticsAdapter
- `list_properties()`
- `fetch_page_metrics(property_id, date_range, dimensions, metrics)`

### SERPProviderAdapter (optional)
- `fetch_serp(keyword, locale, device) -> SerpSnapshot`

---

## 8) Canonical facts (normalization layer)

### SearchFactDaily
Dimensions: engine, property_id, date, query?, page_url, country?, device?, search_type?
Metrics: impressions, clicks, ctr, avg_position?, data_quality_flags

### AnalyticsFactDaily
Dimensions: property_id, date, page_url, country?, device?, source_medium?, campaign?
Metrics: sessions, users?, engagement?, conversions?, revenue?, data_quality_flags

### LinkFact
source (commoncrawl/provider/import/crawl/community), source_domain/url, target_domain/url, anchor?, rel?, first_seen, last_seen, snapshot_id?

---

## 9) Data model (MVP tables)

### Core
- users
- projects
- sites
- competitors
- project_settings (json or columns)
- schedules

### Integrations
- integration_accounts
- integration_tokens (encrypted)
- integration_properties
- sync_runs

### Crawl / Audit
- crawl_runs
- crawl_pages
- link_edges
- issue_types
- issue_instances

### Facts
- search_fact_daily
- analytics_fact_daily
- link_facts

### Common Crawl
- commoncrawl_snapshots (id, name, date_range, spec_json, ingested_at)
- commoncrawl_edges (optional; can be ClickHouse)
- commoncrawl_aggregates (ref domains, anchors)
- competitive_views (overlap/intersect materializations; optional)

### Alerts / Exports / Webhooks
- alerts
- exports
- webhooks

---

## 10) API (MVP endpoints)

Auth
- POST /auth/login
- POST /auth/logout
- GET /me

Projects
- POST /projects
- GET /projects
- GET /projects/{id}
- PATCH /projects/{id}
- DELETE /projects/{id}

Project Settings
- GET /projects/{id}/settings
- PUT /projects/{id}/settings

Integrations
- POST /integrations/{provider}/connect
- POST /integrations/{provider}/callback
- GET /integrations/accounts
- POST /integrations/accounts/{id}/disconnect
- GET /integrations/{provider}/properties
- POST /projects/{id}/integrations/map
- POST /projects/{id}/integrations/sync

Crawls / Audit
- POST /projects/{id}/crawls
- GET /projects/{id}/crawls
- GET /crawls/{crawl_run_id}
- GET /crawls/{crawl_run_id}/issues
- GET /projects/{id}/issues
- GET /projects/{id}/issues/diffs

Performance
- GET /projects/{id}/performance/queries
- GET /projects/{id}/performance/pages
- GET /projects/{id}/analytics/pages
- GET /projects/{id}/opportunities/ctr

Backlinks (Project-scoped, multi-source)
- POST /projects/{id}/backlinks/import
- GET /projects/{id}/backlinks/new_lost
- GET /projects/{id}/backlinks/targets
- GET /projects/{id}/backlinks/anchors
- GET /projects/{id}/backlinks/overlap?competitors=...
- GET /projects/{id}/backlinks/intersect?competitors=...

Common Crawl (MVP core)
- GET /commoncrawl/snapshots
- POST /commoncrawl/ingest (admin/self-host operator)
- GET /links/domain/{domain}/refdomains
- GET /links/domain/{domain}/backlinks
- GET /links/domain/{domain}/anchors
- GET /links/domain/{domain}/new-lost?snapshot_a=...&snapshot_b=...
- GET /links/domain/{domain}/overlap?competitors=...
- GET /links/domain/{domain}/intersect?competitors=...

Alerts
- GET /projects/{id}/alerts
- POST /projects/{id}/alerts/rules

Exports / Reports
- POST /projects/{id}/exports
- GET /projects/{id}/exports
- POST /projects/{id}/exports/schedule

Webhooks
- POST /projects/{id}/webhooks
- GET /projects/{id}/webhooks
- DELETE /projects/{id}/webhooks/{webhook_id}

Webhook events
- crawl.completed
- alert.fired
- integration.sync_failed
- export.completed
- commoncrawl.ingest_completed (optional)

---

## 11) Background jobs (MVP)

### Integrations
- integration.sync_property (daily incremental)
- integration.backfill_property (chunked)

### Crawl/Audit pipeline
1) crawl.run_html(project_id, crawl_run_id)
2) crawl.select_js_candidates(crawl_run_id) (hybrid heuristics)
3) crawl.render_js(crawl_run_id) (budgeted)
4) audit.analyze(crawl_run_id) (rules + evidence)
5) audit.compute_diff(project_id, crawl_run_id)
6) alerts.evaluate(project_id)

### Common Crawl pipeline (MVP)
1) commoncrawl.ingest_snapshot(snapshot_spec)
2) commoncrawl.build_aggregates(snapshot_id)
3) commoncrawl.compute_competitive_views(snapshot_id)

### Reports/Exports
- exports.generate (csv/json/pdf)
- exports.schedule (cron)

---

## 12) Security / Privacy

- Encrypt integration tokens at rest
- Least-privilege OAuth scopes
- Rate limiting on crawl triggers and exports
- Opt-in community sharing defaults OFF, hashed-by-default, revocable
- Audit log for integration changes and exports (recommended)

---

## 13) Deployment

Docker Compose services:
- api (FastAPI)
- workers (Python)
- integrations (Python; may be merged with workers initially)
- crawler (Rust)
- postgres
- redis
- minio
- optional clickhouse (for edges/time-series)

---

## 14) Acceptance criteria (Definition of Done)

Integrations
- Connect GSC/GA4/BWT, map properties, run backfill + daily incremental
- Canonical facts populate dashboards and impact scoring
- Failures visible with actionable errors and timestamps

Hybrid Site Audit
- HTML crawl runs reliably in background
- Hybrid heuristics select JS candidates deterministically
- Playwright fallback respects budgets and shows rendered vs non-rendered evidence
- Issues generated with evidence + diffs + impact sorting

Visibility / Alerts
- Alerts for query/page drops and CTR opportunities
- Webhook `alert.fired` delivered at-least-once

Backlinks + Common Crawl
- Operator can ingest at least two Common Crawl snapshots/subsets
- Domain explorer returns referring domains/backlinks/anchors
- New/lost works between snapshots
- Overlap/intersect works for competitor lists
- Backlinks imports + provider links are merged into project backlink views

Reports/Exports/API
- PDF export works + scheduled exports
- CSV/JSON exports for major views
- Webhooks configured and delivered (crawl.completed, export.completed)

Self-hosting
- Docker Compose brings up stack with minimal env
- Health endpoints green when ready

---

## 15) Repo layout (suggested)

- apps/api/
- apps/workers/
- apps/integrations/
- apps/reports/
- crates/crawler/
- infra/compose/
- migrations/
- docs/