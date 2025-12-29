# Task Tracker — Openahrush MVP

Last Updated: 2025-12-28

This document tracks overall progress across all sprints. Each task references its detailed sprint document.

---

## Progress Overview

| Sprint | Status | Tasks | Completed | Progress |
|--------|--------|-------|-----------|----------|
| Sprint 0: Foundation | Complete | 25 | 25 | 100% |
| Sprint 1: Integrations | Complete | 24 | 24 | 100% |
| Sprint 2: Crawl & Audit | Complete | 31 | 31 | 100% |
| Sprint 3: Backlinks | Complete | 22 | 22 | 100% |
| Sprint 4: Reports | Not Started | 22 | 0 | 0% |
| Sprint 5: Hardening | Not Started | 18 | 0 | 0% |
| **Total** | | **142** | **102** | **72%** |

---

## Sprint 0: Foundation & Platform

**Status:** Complete | **Doc:** [SPRINT-0-FOUNDATION.md](./SPRINT-0-FOUNDATION.md)

### Epic 0.1: Workspace Bootstrap
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.1.1 | Create libs/core package | [x] | Agent | config.py, database.py, models/ |
| 0.1.2 | Create libs/seo package | [x] | Agent | url.py with normalization |
| 0.1.3 | Create libs/backlinks package | [x] | Agent | models.py placeholder |
| 0.1.4 | Create apps/api package | [x] | Agent | FastAPI main.py, routers/ |
| 0.1.5 | Create apps/workers package | [x] | Agent | runner.py, scheduler.py |
| 0.1.6 | Create remaining app packages | [x] | Agent | integrations, reports, commoncrawl_ingest |

### Epic 0.2: Database & Migrations
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.2.1 | Set up Alembic migrations | [x] | Agent | migrations/env.py, alembic.ini |
| 0.2.2 | Create initial schema migration | [x] | Agent | 001_initial_schema.py |
| 0.2.3 | Create SQLAlchemy models | [x] | Agent | User, Project, Site, Competitor, Settings |

### Epic 0.3: Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.3.1 | Create Docker Compose configuration | [x] | Agent | infra/compose/docker-compose.yml |
| 0.3.2 | Create Dockerfile for API | [x] | Agent | Multi-stage Dockerfile |
| 0.3.3 | Create dev scripts | [x] | Agent | scripts/dev.sh, lint.sh, test.sh |

### Epic 0.4: Auth & Health Endpoints
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.4.1 | Implement health endpoints | [x] | Agent | /healthz, /readyz (9 tests) |
| 0.4.2 | Implement auth endpoints | [x] | Agent | /auth/login, /logout, /me (20 tests) |
| 0.4.3 | Implement user registration | [x] | Agent | POST /auth/register |

### Epic 0.5: Projects CRUD
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.5.1 | Implement Projects list/create | [x] | Agent | GET/POST /projects (35 tests) |
| 0.5.2 | Implement Projects get/update/delete | [x] | Agent | CRUD complete |
| 0.5.3 | Implement Sites management | [x] | Agent | /projects/{id}/sites |
| 0.5.4 | Implement Competitors management | [x] | Agent | /projects/{id}/competitors |

### Epic 0.6: Project Settings
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.6.1 | Define ProjectSettings Pydantic model | [x] | Agent | 30+ validated fields |
| 0.6.2 | Implement Settings endpoints | [x] | Agent | GET/PUT (28 tests) |
| 0.6.3 | Create settings defaults logic | [x] | Agent | Default merge logic |

---

## Sprint 1: Integrations (GSC/GA4/BWT)

**Status:** Complete | **Doc:** [SPRINT-1-INTEGRATIONS.md](./SPRINT-1-INTEGRATIONS.md)

### Epic 1.1: Integration Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.1.1 | Create integration_accounts table | [x] | Agent | 002_integration_tables.py |
| 1.1.2 | Implement token encryption | [x] | Agent | Fernet encryption in security/ |
| 1.1.3 | Create integration_properties table | [x] | Agent | With integration_mappings |
| 1.1.4 | Create sync_runs table | [x] | Agent | SyncMode, SyncStatus enums |

### Epic 1.2: OAuth Flows
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.2.1 | Implement Google OAuth connect | [x] | Agent | oauth/google.py (27 tests) |
| 1.2.2 | Implement Google OAuth callback | [x] | Agent | Token exchange, storage |
| 1.2.3 | Implement Bing OAuth | [x] | Agent | oauth/microsoft.py (23 tests) |
| 1.2.4 | Implement token refresh | [x] | Agent | TokenService (20 tests) |
| 1.2.5 | Implement account management | [x] | Agent | List, disconnect endpoints |

### Epic 1.3: Property Discovery & Mapping
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.3.1 | Implement GSC property discovery | [x] | Agent | gsc_adapter.py |
| 1.3.2 | Implement GA4 property discovery | [x] | Agent | ga4_adapter.py |
| 1.3.3 | Implement BWT property discovery | [x] | Agent | bwt_adapter.py |
| 1.3.4 | Implement property → project mapping | [x] | Agent | PropertyService (44 tests) |

### Epic 1.4: Canonical Fact Tables
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.4.1 | Create search_fact_daily table | [x] | Agent | 003_fact_tables.py |
| 1.4.2 | Create analytics_fact_daily table | [x] | Agent | With unique indexes |
| 1.4.3 | Create link_facts table | [x] | Agent | LinkSource enum |

### Epic 1.5: Provider Adapters
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.5.1 | Define SearchAdapter protocol | [x] | Agent | adapters/base.py |
| 1.5.2 | Implement GSC adapter | [x] | Agent | data/gsc_data.py (45 tests) |
| 1.5.3 | Implement GA4 adapter | [x] | Agent | data/ga4_data.py |
| 1.5.4 | Implement BWT adapter | [x] | Agent | data/bwt_data.py |

### Epic 1.6: Sync Scheduler
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.6.1 | Create sync job infrastructure | [x] | Agent | jobs/base.py, sync_job.py |
| 1.6.2 | Implement incremental sync | [x] | Agent | DataSyncService |
| 1.6.3 | Implement backfill sync | [x] | Agent | Chunked historical fetch |
| 1.6.4 | Create daily sync scheduler | [x] | Agent | scheduler.py (27 tests) |
| 1.6.5 | Implement manual sync trigger | [x] | Agent | POST /mappings/{id}/sync |

### Epic 1.7: Data Quality & Status
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.7.1 | Implement data quality flags | [x] | Agent | JSONB flags in fact tables |
| 1.7.2 | Implement sync status endpoints | [x] | Agent | /sync-status, /data-freshness |
| 1.7.3 | Implement health monitoring | [x] | Agent | IntegrationHealthService (36 tests) |

---

## Sprint 2: Hybrid Crawl & Site Audit

**Status:** Complete | **Doc:** [SPRINT-2-CRAWL-AUDIT.md](./SPRINT-2-CRAWL-AUDIT.md)

### Epic 2.1: Crawl Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.1.1 | Create crawl_runs table | [x] | Agent | 004_crawl_infrastructure.py |
| 2.1.2 | Create crawl_pages table | [x] | Agent | With SEO fields, hashes, artifacts |
| 2.1.3 | Create link_edges table | [x] | Agent | With broken link tracking |
| 2.1.4 | Create issue tables | [x] | Agent | issue_types seeded with 25 MVP issues |

### Epic 2.2: HTML Crawler
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.2.1 | Create URL frontier manager | [x] | Agent | crawl/frontier.py (32 tests) |
| 2.2.2 | Implement robots.txt parser | [x] | Agent | libs/seo/robots.py |
| 2.2.3 | Implement sitemap parser | [x] | Agent | libs/seo/sitemap.py |
| 2.2.4 | Implement HTTP fetcher | [x] | Agent | crawl/fetcher.py (23 tests) |
| 2.2.5 | Implement HTML extractor | [x] | Agent | libs/seo/extraction.py |
| 2.2.6 | Build crawl orchestrator | [x] | Agent | crawl/orchestrator.py (21 tests) |

### Epic 2.3: Hybrid JS Rendering
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.3.1 | Implement thin DOM heuristic | [x] | Agent | crawl/heuristics.py (36 tests) |
| 2.3.2 | Implement SPA shell heuristic | [x] | Agent | SPA_ROOT_IDS detection |
| 2.3.3 | Implement selectors heuristic | [x] | Agent | CSS selector matching |
| 2.3.4 | Implement redirect heuristic | [x] | Agent | JS redirect patterns |
| 2.3.5 | Build JS candidate selector | [x] | Agent | crawl/js_selector.py (17 tests) |
| 2.3.6 | Implement Playwright renderer | [x] | Agent | crawl/renderer.py (14 tests) |
| 2.3.7 | Build render orchestrator | [x] | Agent | crawl/render_orchestrator.py (12 tests) |

### Epic 2.4: Rules Engine
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.4.1 | Seed issue types | [x] | Agent | 25 MVP issue types in migration |
| 2.4.2 | Implement rule evaluators | [x] | Agent | rules/evaluators.py (68 tests) |
| 2.4.3 | Implement rules engine | [x] | Agent | rules/engine.py (14 tests) |
| 2.4.4 | Implement broken link detection | [x] | Agent | rules/broken_links.py (12 tests) |
| 2.4.5 | Implement orphan page detection | [x] | Agent | rules/orphan_pages.py (12 tests) |

### Epic 2.5: Impact Scoring
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.5.1 | Implement traffic weight computation | [x] | Agent | scoring/traffic_weight.py (15 tests) |
| 2.5.2 | Compute and store impact scores | [x] | Agent | scoring/impact.py (12 tests) |
| 2.5.3 | Create issue API endpoints | [x] | Agent | routers/issues.py |
| 2.5.4 | Create project issues endpoint | [x] | Agent | GET /projects/{id}/issues |

### Epic 2.6: Diff Engine
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.6.1 | Implement issue diff computation | [x] | Agent | diff/diff_engine.py (14 tests) |
| 2.6.2 | Implement diff API endpoint | [x] | Agent | routers/diffs.py |
| 2.6.3 | Store diff snapshots | [x] | Agent | Via DiffResult model |

### Epic 2.7: Visibility & Alerts
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.7.1 | Create alerts table | [x] | Agent | alert_rules + alerts tables |
| 2.7.2 | Implement visibility drop detector | [x] | Agent | alerts/visibility_detector.py (12 tests) |
| 2.7.3 | Implement CTR opportunity detector | [x] | Agent | alerts/ctr_detector.py (15 tests) |
| 2.7.4 | Implement regression detector | [x] | Agent | alerts/regression_detector.py (12 tests) |
| 2.7.5 | Build alert scheduler | [x] | Agent | alerts/scheduler.py (7 tests) |
| 2.7.6 | Create alert API endpoints | [x] | Agent | routers/alerts.py |

---

## Sprint 3: Backlinks & Common Crawl

**Status:** Complete | **Doc:** [SPRINT-3-BACKLINKS.md](./SPRINT-3-BACKLINKS.md)

### Epic 3.1: Common Crawl Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.1.1 | Create commoncrawl_snapshots table | [x] | Agent | 005_commoncrawl.py migration |
| 3.1.2 | Create link edge tables (Postgres) | [x] | Agent | commoncrawl_edges table |
| 3.1.3 | Create ClickHouse schema (optional) | [x] | Agent | infra/clickhouse/cc_schema.sql |
| 3.1.4 | Create storage adapter interface | [x] | Agent | storage/base.py, postgres.py, clickhouse.py |

### Epic 3.2: Ingestion Pipeline
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.2.1 | Implement snapshot registry | [x] | Agent | API endpoints for snapshots |
| 3.2.2 | Implement WAT file downloader | [x] | Agent | downloader.py |
| 3.2.3 | Implement WAT parser | [x] | Agent | parser.py |
| 3.2.4 | Implement domain filtering | [x] | Agent | filter.py |
| 3.2.5 | Build ingestion orchestrator | [x] | Agent | orchestrator.py with events |
| 3.2.6 | Implement ingestion trigger endpoint | [x] | Agent | POST /commoncrawl/ingest |

### Epic 3.3: Aggregate Materialization
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.3.1 | Build ref domains aggregator | [x] | Agent | aggregates/refdomains.py |
| 3.3.2 | Build anchor aggregator | [x] | Agent | aggregates/anchors.py |
| 3.3.3 | Implement aggregate build job | [x] | Agent | aggregates/builder.py |

### Epic 3.4: Domain Explorer API
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.4.1 | Implement ref domains endpoint | [x] | Agent | GET /links/domain/{domain}/refdomains |
| 3.4.2 | Implement backlinks endpoint | [x] | Agent | GET /links/domain/{domain}/backlinks |
| 3.4.3 | Implement anchors endpoint | [x] | Agent | GET /links/domain/{domain}/anchors |

### Epic 3.5: New/Lost Detection
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.5.1 | Implement snapshot comparison | [x] | Agent | new-lost endpoint |
| 3.5.2 | Implement new/lost time series | [x] | Agent | Time series support |

### Epic 3.6: Competitive Analysis
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.6.1 | Implement domain overlap | [x] | Agent | /overlap endpoint |
| 3.6.2 | Implement domain intersect | [x] | Agent | /intersect endpoint |
| 3.6.3 | Project-scoped competitive analysis | [x] | Agent | Project backlinks routes |

### Epic 3.7: CSV Import & Multi-Source
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.7.1 | Implement CSV import endpoint | [x] | Agent | POST /projects/{id}/backlinks/import |
| 3.7.2 | Implement project backlinks merge | [x] | Agent | Multi-source merge |
| 3.7.3 | Implement project new/lost endpoint | [x] | Agent | Project new/lost |
| 3.7.4 | Implement project anchors endpoint | [x] | Agent | Project anchors |

---

## Sprint 4: Reports, Exports & Webhooks

**Status:** Not Started | **Doc:** [SPRINT-4-REPORTS.md](./SPRINT-4-REPORTS.md)

### Epic 4.1: Export Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 4.1.1 | Create exports table | [ ] | | |
| 4.1.2 | Create export_schedules table | [ ] | | |
| 4.1.3 | Implement MinIO storage utilities | [ ] | | |

### Epic 4.2: CSV/JSON Exports
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 4.2.1 | Implement export job queue | [ ] | | |
| 4.2.2 | Implement issues CSV export | [ ] | | |
| 4.2.3 | Implement performance CSV export | [ ] | | |
| 4.2.4 | Implement backlinks CSV export | [ ] | | |
| 4.2.5 | Implement JSON export format | [ ] | | |
| 4.2.6 | Create export trigger endpoint | [ ] | | |
| 4.2.7 | Create export list endpoint | [ ] | | |

### Epic 4.3: PDF Reports
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 4.3.1 | Create report templates | [ ] | | |
| 4.3.2 | Implement template data builders | [ ] | | |
| 4.3.3 | Implement PDF renderer | [ ] | | |
| 4.3.4 | Implement chart generation | [ ] | | |
| 4.3.5 | Implement PDF export job | [ ] | | |

### Epic 4.4: Export Scheduling
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 4.4.1 | Implement schedule creation endpoint | [ ] | | |
| 4.4.2 | Implement schedule executor | [ ] | | |
| 4.4.3 | Implement schedule management | [ ] | | |

### Epic 4.5: Webhooks
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 4.5.1 | Create webhooks table | [ ] | | |
| 4.5.2 | Implement webhook CRUD endpoints | [ ] | | |
| 4.5.3 | Implement webhook signature | [ ] | | |
| 4.5.4 | Implement webhook delivery queue | [ ] | | |
| 4.5.5 | Implement webhook delivery worker | [ ] | | |
| 4.5.6 | Implement event → webhook routing | [ ] | | |
| 4.5.7 | Implement webhook event types | [ ] | | |

---

## Sprint 5: Hardening & Polish

**Status:** Not Started | **Doc:** [SPRINT-5-HARDENING.md](./SPRINT-5-HARDENING.md)

### Epic 5.1: Rate Limiting & Resource Caps
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 5.1.1 | Implement API rate limiting | [ ] | | |
| 5.1.2 | Implement concurrent job caps | [ ] | | |
| 5.1.3 | Implement resource budget enforcement | [ ] | | |
| 5.1.4 | Implement timeout enforcement | [ ] | | |

### Epic 5.2: Security Hardening
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 5.2.1 | Security audit and fixes | [ ] | | |
| 5.2.2 | Implement webhook URL validation | [ ] | | |
| 5.2.3 | Implement audit logging | [ ] | | |
| 5.2.4 | Implement secret redaction | [ ] | | |

### Epic 5.3: Performance Optimization
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 5.3.1 | Database query optimization | [ ] | | |
| 5.3.2 | Implement response caching | [ ] | | |
| 5.3.3 | Optimize crawl performance | [ ] | | |
| 5.3.4 | Optimize CC ingestion | [ ] | | |

### Epic 5.4: Testing
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 5.4.1 | Unit test coverage | [~] | Agent | 951 tests passing |
| 5.4.2 | Integration tests | [ ] | | |
| 5.4.3 | End-to-end tests | [ ] | | |
| 5.4.4 | Load testing | [ ] | | |

### Epic 5.5: Documentation
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 5.5.1 | API documentation | [ ] | | |
| 5.5.2 | Deployment documentation | [ ] | | |
| 5.5.3 | User documentation | [ ] | | |
| 5.5.4 | Developer documentation | [ ] | | |

### Epic 5.6: Deployment Preparation
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 5.6.1 | Production Docker Compose | [ ] | | |
| 5.6.2 | Environment configuration | [ ] | | |
| 5.6.3 | Health and monitoring endpoints | [x] | Agent | Already in Sprint 0 |
| 5.6.4 | Database migrations for production | [ ] | | |

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-28 | Sprint 3 marked complete (CC infrastructure, ingestion, aggregates, API) |
| 2025-12-28 | Sprint 2 marked complete (951 tests passing) |
| 2025-12-28 | Sprint 0 and Sprint 1 marked complete (419 tests passing) |
| 2025-01-28 | Initial task tracker created |

---

## Legend

- [ ] Not Started
- [~] In Progress
- [x] Completed
- [!] Blocked
- [-] Cancelled

---

## Quick Links

- [Sprint Overview](./SPRINT-OVERVIEW.md)
- [Sprint 0: Foundation](./SPRINT-0-FOUNDATION.md)
- [Sprint 1: Integrations](./SPRINT-1-INTEGRATIONS.md)
- [Sprint 2: Crawl & Audit](./SPRINT-2-CRAWL-AUDIT.md)
- [Sprint 3: Backlinks](./SPRINT-3-BACKLINKS.md)
- [Sprint 4: Reports](./SPRINT-4-REPORTS.md)
- [Sprint 5: Hardening](./SPRINT-5-HARDENING.md)
- [Blueprint PRD](../BLUEPRINT-PRD-MVP.md)
- [Architecture](../ARCHITECTURE.md)
- [OpenAPI Spec](../openapi.yaml)
