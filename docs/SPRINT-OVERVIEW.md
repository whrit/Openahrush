# Sprint Overview — Openahrush MVP

This document provides a high-level overview of all sprints required to deliver the Openahrush MVP. Each sprint has a dedicated detailed document with specific tasks, acceptance criteria, and dependencies.

## MVP Delivery Structure

| Sprint | Name | Duration | Dependencies | Status |
|--------|------|----------|--------------|--------|
| 0 | Foundation & Platform | 2-3 weeks | None | Not Started |
| 1 | Integrations (GSC/GA4/BWT) | 2-3 weeks | Sprint 0 | Not Started |
| 2 | Hybrid Crawl & Site Audit | 3-4 weeks | Sprint 0 | Not Started |
| 3 | Backlinks & Common Crawl | 2-3 weeks | Sprint 0 | Not Started |
| 4 | Reports, Exports & Webhooks | 1-2 weeks | Sprints 1-3 | Not Started |
| 5 | Hardening & Polish | 1-2 weeks | Sprints 0-4 | Not Started |

---

## Sprint 0: Foundation & Platform

**Goal:** Establish the core platform skeleton with working API, database, and development infrastructure.

### Deliverables
- FastAPI application with auth scaffolding (JWT)
- Postgres schema with Alembic migrations
- Redis queue infrastructure
- Docker Compose dev environment
- Health endpoints + Projects CRUD
- Project Settings model and endpoints

### Key Metrics
- [ ] `GET /healthz` returns 200
- [ ] `GET /readyz` returns 200 (with DB check)
- [ ] Projects CRUD works end-to-end
- [ ] Settings GET/PUT works per project
- [ ] Docker Compose brings up full stack

**Detailed Plan:** [SPRINT-0-FOUNDATION.md](./SPRINT-0-FOUNDATION.md)

---

## Sprint 1: Integrations (GSC/GA4/BWT)

**Goal:** Implement OAuth flows and data sync for truth-first integrations.

### Deliverables
- OAuth connect/callback for Google + Bing
- Encrypted token storage with refresh logic
- Property discovery and mapping to projects
- Daily sync scheduler + backfill mode
- Canonical fact tables (search_fact_daily, analytics_fact_daily)
- GSC, GA4, BWT provider adapters

### Key Metrics
- [ ] OAuth flow completes for GSC
- [ ] OAuth flow completes for GA4
- [ ] OAuth flow completes for BWT
- [ ] Properties can be mapped to projects
- [ ] Daily sync populates fact tables
- [ ] Backfill retrieves historical data

**Detailed Plan:** [SPRINT-1-INTEGRATIONS.md](./SPRINT-1-INTEGRATIONS.md)

---

## Sprint 2: Hybrid Crawl & Site Audit

**Goal:** Implement the hybrid HTML+JS crawling engine with rules-based issue detection.

### Deliverables
- Crawl orchestration state machine
- HTML-first crawler with frontier management
- Playwright fallback with budget enforcement
- Hybrid heuristics (thin DOM, SPA detection, selector checks)
- Rules engine with issue taxonomy
- Impact scoring via canonical facts
- Diff engine for crawl comparisons
- Alert engine for visibility changes

### Key Metrics
- [ ] HTML crawl completes under page budget
- [ ] Hybrid heuristics trigger JS rendering correctly
- [ ] Playwright fallback respects time/page budgets
- [ ] Issues generated with evidence
- [ ] Impact scores computed from fact joins
- [ ] Diffs show new/resolved issues between runs
- [ ] Alerts fire for significant drops

**Detailed Plan:** [SPRINT-2-CRAWL-AUDIT.md](./SPRINT-2-CRAWL-AUDIT.md)

---

## Sprint 3: Backlinks & Common Crawl

**Goal:** Implement the free data moat via Common Crawl ingestion and backlink explorer.

### Deliverables
- Common Crawl snapshot registry
- WAT-first ingestion pipeline
- Edge storage (Postgres MVP, ClickHouse optional)
- Aggregate materialization (ref domains, anchors)
- Domain backlink explorer endpoints
- New/lost link detection between snapshots
- Competitive overlap/intersect analysis
- CSV import for additional backlink sources

### Key Metrics
- [ ] Snapshot registry lists available CC snapshots
- [ ] Ingestion pipeline processes WAT files
- [ ] Ref domains endpoint returns data
- [ ] Backlinks endpoint with pagination works
- [ ] Anchors distribution computed
- [ ] New/lost comparison between snapshots works
- [ ] Overlap/intersect with competitors works

**Detailed Plan:** [SPRINT-3-BACKLINKS.md](./SPRINT-3-BACKLINKS.md)

---

## Sprint 4: Reports, Exports & Webhooks

**Goal:** Implement data export capabilities and event-driven webhook delivery.

### Deliverables
- CSV/JSON export generation
- PDF report rendering (WeasyPrint or Playwright)
- Export scheduling (cron-based)
- Webhook configuration endpoints
- At-least-once webhook delivery with retries
- HMAC signature verification
- Download URL generation via MinIO presigned URLs

### Key Metrics
- [ ] CSV export downloads correctly
- [ ] JSON export downloads correctly
- [ ] PDF report renders with correct data
- [ ] Scheduled exports run on time
- [ ] Webhooks configured per project
- [ ] Webhook delivery with retry logic works
- [ ] Signature verification passes

**Detailed Plan:** [SPRINT-4-REPORTS.md](./SPRINT-4-REPORTS.md)

---

## Sprint 5: Hardening & Polish

**Goal:** Production readiness, performance, security, and quality assurance.

### Deliverables
- Rate limiting on crawl triggers and exports
- Concurrency caps and resource limits
- ClickHouse migration for edge storage (optional)
- End-to-end test suite
- Performance optimization
- Security audit (token encryption, input validation)
- Documentation polish

### Key Metrics
- [ ] Rate limits enforced correctly
- [ ] Resource limits prevent runaway jobs
- [ ] E2E tests pass for critical flows
- [ ] No critical security vulnerabilities
- [ ] API response times acceptable
- [ ] Documentation complete and accurate

**Detailed Plan:** [SPRINT-5-HARDENING.md](./SPRINT-5-HARDENING.md)

---

## Dependency Graph

```
Sprint 0 (Foundation)
    ├── Sprint 1 (Integrations)
    │       └── Sprint 4 (Reports) [needs canonical facts]
    ├── Sprint 2 (Crawl & Audit)
    │       └── Sprint 4 (Reports) [needs issues/diffs]
    └── Sprint 3 (Backlinks)
            └── Sprint 4 (Reports) [needs backlink data]

All Sprints 0-4
    └── Sprint 5 (Hardening)
```

**Parallelization Note:** Sprints 1, 2, and 3 can be worked in parallel after Sprint 0 completes. Sprint 4 requires outputs from 1-3. Sprint 5 is the final polish phase.

---

## Technology Stack Reference

| Layer | Technology | Notes |
|-------|------------|-------|
| API | FastAPI | Python 3.12, async support |
| Database | PostgreSQL | System of record |
| Queue | Redis | Work queue + distributed locks |
| Objects | MinIO/S3 | Artifacts, exports, HTML storage |
| Analytics DB | ClickHouse | Optional, for CC edge storage at scale |
| Crawler | Rust | High-throughput data plane (future) |
| JS Rendering | Playwright | Budgeted hybrid fallback |
| PDF | WeasyPrint | HTML template → PDF |
| Migrations | Alembic | Database schema versioning |
| Package Mgmt | uv | Python workspace management |

---

## Definition of Done (Per Sprint)

Each sprint is considered complete when:

1. **Code Complete:** All tasks implemented and merged
2. **Tests Passing:** Unit tests + integration tests green
3. **Linting Clean:** `scripts/lint.sh` passes (Ruff + MyPy)
4. **Migrations Applied:** Schema changes via Alembic
5. **Docker Works:** `scripts/dev.sh up` brings up stack
6. **Endpoints Verified:** OpenAPI spec matches implementation
7. **Documentation Updated:** README/docs reflect changes
8. **Acceptance Criteria Met:** All sprint metrics checked

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Common Crawl data volume | High | Start with domain-filtered subsets |
| OAuth complexity (3 providers) | Medium | Implement one provider fully first |
| Playwright resource usage | Medium | Strict budgets, separate concurrency |
| ClickHouse learning curve | Low | Postgres-only MVP path available |
| Rust crawler integration | Low | Python fallback crawler for MVP |

---

## Related Documents

- [SPRINT-0-FOUNDATION.md](./SPRINT-0-FOUNDATION.md) — Foundation tasks
- [SPRINT-1-INTEGRATIONS.md](./SPRINT-1-INTEGRATIONS.md) — Integration tasks
- [SPRINT-2-CRAWL-AUDIT.md](./SPRINT-2-CRAWL-AUDIT.md) — Crawl & audit tasks
- [SPRINT-3-BACKLINKS.md](./SPRINT-3-BACKLINKS.md) — Backlink tasks
- [SPRINT-4-REPORTS.md](./SPRINT-4-REPORTS.md) — Reports & webhooks tasks
- [SPRINT-5-HARDENING.md](./SPRINT-5-HARDENING.md) — Hardening tasks
- [TASK-TRACKER.md](./TASK-TRACKER.md) — Overall progress tracking
- [../BLUEPRINT-PRD-MVP.md](../BLUEPRINT-PRD-MVP.md) — Product requirements
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — System architecture
