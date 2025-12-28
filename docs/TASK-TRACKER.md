# Task Tracker — Openahrush MVP

Last Updated: 2025-01-28

This document tracks overall progress across all sprints. Each task references its detailed sprint document.

---

## Progress Overview

| Sprint | Status | Tasks | Completed | Progress |
|--------|--------|-------|-----------|----------|
| Sprint 0: Foundation | Not Started | 25 | 0 | 0% |
| Sprint 1: Integrations | Not Started | 24 | 0 | 0% |
| Sprint 2: Crawl & Audit | Not Started | 31 | 0 | 0% |
| Sprint 3: Backlinks | Not Started | 22 | 0 | 0% |
| Sprint 4: Reports | Not Started | 22 | 0 | 0% |
| Sprint 5: Hardening | Not Started | 18 | 0 | 0% |
| **Total** | | **142** | **0** | **0%** |

---

## Sprint 0: Foundation & Platform

**Status:** Not Started | **Doc:** [SPRINT-0-FOUNDATION.md](./SPRINT-0-FOUNDATION.md)

### Epic 0.1: Workspace Bootstrap
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.1.1 | Create libs/core package | [ ] | | |
| 0.1.2 | Create libs/seo package | [ ] | | |
| 0.1.3 | Create libs/backlinks package | [ ] | | |
| 0.1.4 | Create apps/api package | [ ] | | |
| 0.1.5 | Create apps/workers package | [ ] | | |
| 0.1.6 | Create remaining app packages | [ ] | | |

### Epic 0.2: Database & Migrations
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.2.1 | Set up Alembic migrations | [ ] | | |
| 0.2.2 | Create initial schema migration | [ ] | | |
| 0.2.3 | Create SQLAlchemy models | [ ] | | |

### Epic 0.3: Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.3.1 | Create Docker Compose configuration | [ ] | | |
| 0.3.2 | Create Dockerfile for API | [ ] | | |
| 0.3.3 | Create dev scripts | [ ] | | |

### Epic 0.4: Auth & Health Endpoints
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.4.1 | Implement health endpoints | [ ] | | |
| 0.4.2 | Implement auth endpoints | [ ] | | |
| 0.4.3 | Implement user registration | [ ] | | |

### Epic 0.5: Projects CRUD
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.5.1 | Implement Projects list/create | [ ] | | |
| 0.5.2 | Implement Projects get/update/delete | [ ] | | |
| 0.5.3 | Implement Sites management | [ ] | | |
| 0.5.4 | Implement Competitors management | [ ] | | |

### Epic 0.6: Project Settings
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 0.6.1 | Define ProjectSettings Pydantic model | [ ] | | |
| 0.6.2 | Implement Settings endpoints | [ ] | | |
| 0.6.3 | Create settings defaults logic | [ ] | | |

---

## Sprint 1: Integrations (GSC/GA4/BWT)

**Status:** Not Started | **Doc:** [SPRINT-1-INTEGRATIONS.md](./SPRINT-1-INTEGRATIONS.md)

### Epic 1.1: Integration Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.1.1 | Create integration_accounts table | [ ] | | |
| 1.1.2 | Implement token encryption | [ ] | | |
| 1.1.3 | Create integration_properties table | [ ] | | |
| 1.1.4 | Create sync_runs table | [ ] | | |

### Epic 1.2: OAuth Flows
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.2.1 | Implement Google OAuth connect | [ ] | | |
| 1.2.2 | Implement Google OAuth callback | [ ] | | |
| 1.2.3 | Implement Bing OAuth | [ ] | | |
| 1.2.4 | Implement token refresh | [ ] | | |
| 1.2.5 | Implement account management | [ ] | | |

### Epic 1.3: Property Discovery & Mapping
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.3.1 | Implement GSC property discovery | [ ] | | |
| 1.3.2 | Implement GA4 property discovery | [ ] | | |
| 1.3.3 | Implement BWT property discovery | [ ] | | |
| 1.3.4 | Implement property → project mapping | [ ] | | |

### Epic 1.4: Canonical Fact Tables
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.4.1 | Create search_fact_daily table | [ ] | | |
| 1.4.2 | Create analytics_fact_daily table | [ ] | | |
| 1.4.3 | Create link_facts table | [ ] | | |

### Epic 1.5: Provider Adapters
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.5.1 | Define SearchAdapter protocol | [ ] | | |
| 1.5.2 | Implement GSC adapter | [ ] | | |
| 1.5.3 | Implement GA4 adapter | [ ] | | |
| 1.5.4 | Implement BWT adapter | [ ] | | |

### Epic 1.6: Sync Scheduler
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.6.1 | Create sync job infrastructure | [ ] | | |
| 1.6.2 | Implement incremental sync | [ ] | | |
| 1.6.3 | Implement backfill sync | [ ] | | |
| 1.6.4 | Create daily sync scheduler | [ ] | | |
| 1.6.5 | Implement manual sync trigger | [ ] | | |

### Epic 1.7: Data Quality & Status
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 1.7.1 | Implement data quality flags | [ ] | | |
| 1.7.2 | Implement sync status endpoints | [ ] | | |
| 1.7.3 | Implement health monitoring | [ ] | | |

---

## Sprint 2: Hybrid Crawl & Site Audit

**Status:** Not Started | **Doc:** [SPRINT-2-CRAWL-AUDIT.md](./SPRINT-2-CRAWL-AUDIT.md)

### Epic 2.1: Crawl Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.1.1 | Create crawl_runs table | [ ] | | |
| 2.1.2 | Create crawl_pages table | [ ] | | |
| 2.1.3 | Create link_edges table | [ ] | | |
| 2.1.4 | Create issue tables | [ ] | | |

### Epic 2.2: HTML Crawler
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.2.1 | Create URL frontier manager | [ ] | | |
| 2.2.2 | Implement robots.txt parser | [ ] | | |
| 2.2.3 | Implement sitemap parser | [ ] | | |
| 2.2.4 | Implement HTTP fetcher | [ ] | | |
| 2.2.5 | Implement HTML extractor | [ ] | | |
| 2.2.6 | Build crawl orchestrator | [ ] | | |

### Epic 2.3: Hybrid JS Rendering
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.3.1 | Implement thin DOM heuristic | [ ] | | |
| 2.3.2 | Implement SPA shell heuristic | [ ] | | |
| 2.3.3 | Implement selectors heuristic | [ ] | | |
| 2.3.4 | Implement redirect heuristic | [ ] | | |
| 2.3.5 | Build JS candidate selector | [ ] | | |
| 2.3.6 | Implement Playwright renderer | [ ] | | |
| 2.3.7 | Build render orchestrator | [ ] | | |

### Epic 2.4: Rules Engine
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.4.1 | Seed issue types | [ ] | | |
| 2.4.2 | Implement rule evaluators | [ ] | | |
| 2.4.3 | Implement rules engine | [ ] | | |
| 2.4.4 | Implement broken link detection | [ ] | | |
| 2.4.5 | Implement orphan page detection | [ ] | | |

### Epic 2.5: Impact Scoring
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.5.1 | Implement traffic weight computation | [ ] | | |
| 2.5.2 | Compute and store impact scores | [ ] | | |
| 2.5.3 | Create issue API endpoints | [ ] | | |
| 2.5.4 | Create project issues endpoint | [ ] | | |

### Epic 2.6: Diff Engine
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.6.1 | Implement issue diff computation | [ ] | | |
| 2.6.2 | Implement diff API endpoint | [ ] | | |
| 2.6.3 | Store diff snapshots | [ ] | | |

### Epic 2.7: Visibility & Alerts
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 2.7.1 | Create alerts table | [ ] | | |
| 2.7.2 | Implement visibility drop detector | [ ] | | |
| 2.7.3 | Implement CTR opportunity detector | [ ] | | |
| 2.7.4 | Implement regression detector | [ ] | | |
| 2.7.5 | Build alert scheduler | [ ] | | |
| 2.7.6 | Create alert API endpoints | [ ] | | |

---

## Sprint 3: Backlinks & Common Crawl

**Status:** Not Started | **Doc:** [SPRINT-3-BACKLINKS.md](./SPRINT-3-BACKLINKS.md)

### Epic 3.1: Common Crawl Infrastructure
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.1.1 | Create commoncrawl_snapshots table | [ ] | | |
| 3.1.2 | Create link edge tables (Postgres) | [ ] | | |
| 3.1.3 | Create ClickHouse schema (optional) | [ ] | | |
| 3.1.4 | Create storage adapter interface | [ ] | | |

### Epic 3.2: Ingestion Pipeline
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.2.1 | Implement snapshot registry | [ ] | | |
| 3.2.2 | Implement WAT file downloader | [ ] | | |
| 3.2.3 | Implement WAT parser | [ ] | | |
| 3.2.4 | Implement domain filtering | [ ] | | |
| 3.2.5 | Build ingestion orchestrator | [ ] | | |
| 3.2.6 | Implement ingestion trigger endpoint | [ ] | | |

### Epic 3.3: Aggregate Materialization
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.3.1 | Build ref domains aggregator | [ ] | | |
| 3.3.2 | Build anchor aggregator | [ ] | | |
| 3.3.3 | Implement aggregate build job | [ ] | | |

### Epic 3.4: Domain Explorer API
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.4.1 | Implement ref domains endpoint | [ ] | | |
| 3.4.2 | Implement backlinks endpoint | [ ] | | |
| 3.4.3 | Implement anchors endpoint | [ ] | | |

### Epic 3.5: New/Lost Detection
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.5.1 | Implement snapshot comparison | [ ] | | |
| 3.5.2 | Implement new/lost time series | [ ] | | |

### Epic 3.6: Competitive Analysis
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.6.1 | Implement domain overlap | [ ] | | |
| 3.6.2 | Implement domain intersect | [ ] | | |
| 3.6.3 | Project-scoped competitive analysis | [ ] | | |

### Epic 3.7: CSV Import & Multi-Source
| Task | Description | Status | Assignee | Notes |
|------|-------------|--------|----------|-------|
| 3.7.1 | Implement CSV import endpoint | [ ] | | |
| 3.7.2 | Implement project backlinks merge | [ ] | | |
| 3.7.3 | Implement project new/lost endpoint | [ ] | | |
| 3.7.4 | Implement project anchors endpoint | [ ] | | |

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
| 5.4.1 | Unit test coverage | [ ] | | |
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
| 5.6.3 | Health and monitoring endpoints | [ ] | | |
| 5.6.4 | Database migrations for production | [ ] | | |

---

## Changelog

| Date | Change |
|------|--------|
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
