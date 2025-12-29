# Sprint 3: Backlinks & Common Crawl

**Duration:** 2-3 weeks
**Dependencies:** Sprint 0 (Foundation)
**Status:** ✅ Complete

This sprint implements the "free data moat" via Common Crawl ingestion for backlink analysis, plus CSV import and competitive link intelligence.

---

## Objectives

1. Build Common Crawl snapshot registry
2. Implement WAT-first ingestion pipeline
3. Create edge storage (Postgres MVP, ClickHouse optional)
4. Materialize aggregates (ref domains, anchors)
5. Build domain backlink explorer endpoints
6. Implement new/lost link detection
7. Create competitive overlap/intersect analysis
8. Support CSV backlink imports

---

## Epic 3.1: Common Crawl Infrastructure

### Task 3.1.1: Create commoncrawl_snapshots table migration

**Description:** Store metadata about known and ingested snapshots.

**Schema:**
```sql
CREATE TABLE commoncrawl_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id TEXT UNIQUE NOT NULL,  -- e.g., 'CC-MAIN-2025-05'
    status TEXT NOT NULL DEFAULT 'known',
    -- known, ingesting, ingested, failed
    date_range_start DATE,
    date_range_end DATE,
    spec JSONB DEFAULT '{}',  -- subset/filter configuration used
    total_records BIGINT,
    edges_ingested BIGINT,
    ingestion_started_at TIMESTAMPTZ,
    ingestion_completed_at TIMESTAMPTZ,
    error_message TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_cc_snapshots_status ON commoncrawl_snapshots(status);
CREATE INDEX idx_cc_snapshots_id ON commoncrawl_snapshots(snapshot_id);
```

**Acceptance Criteria:**
- [x] Migration creates table
- [x] Status tracks ingestion lifecycle
- [x] Spec stores subset configuration for reproducibility
- [x] Stats track progress and completion

---

### Task 3.1.2: Create link edge tables migration (Postgres)

**Description:** Store link edges in Postgres for MVP.

**Schema (commoncrawl_edges):**
```sql
CREATE TABLE commoncrawl_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id TEXT NOT NULL REFERENCES commoncrawl_snapshots(snapshot_id),
    source_url TEXT NOT NULL,
    source_domain TEXT NOT NULL,
    target_url TEXT NOT NULL,
    target_domain TEXT NOT NULL,
    anchor TEXT,
    rel_flags TEXT[],  -- ['nofollow', 'ugc', 'sponsored']
    discovered_at TIMESTAMPTZ DEFAULT now()
);

-- Partition by target_domain first letter for basic sharding (optional)
CREATE INDEX idx_cc_edges_target_domain ON commoncrawl_edges(target_domain);
CREATE INDEX idx_cc_edges_source_domain ON commoncrawl_edges(source_domain);
CREATE INDEX idx_cc_edges_snapshot ON commoncrawl_edges(snapshot_id);
CREATE INDEX idx_cc_edges_target_domain_snapshot ON commoncrawl_edges(target_domain, snapshot_id);
```

**Note:** For scale, ClickHouse is recommended. See Task 3.1.3.

**Acceptance Criteria:**
- [x] Migration creates table with indexes
- [x] Indexes optimized for domain lookups
- [x] Foreign key to snapshots table

---

### Task 3.1.3: Create ClickHouse schema (optional)

**Description:** Define ClickHouse tables for large-scale edge storage.

**Schema (ClickHouse):**
```sql
-- Raw edges table
CREATE TABLE cc_edges (
    snapshot_id String,
    source_url String,
    source_domain LowCardinality(String),
    target_url String,
    target_domain LowCardinality(String),
    anchor String,
    rel_nofollow UInt8,
    rel_ugc UInt8,
    rel_sponsored UInt8,
    discovered_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY (snapshot_id, substring(target_domain, 1, 2))
ORDER BY (target_domain, source_domain, source_url)
SETTINGS index_granularity = 8192;

-- Referring domains aggregate
CREATE MATERIALIZED VIEW cc_refdomains_mv
ENGINE = SummingMergeTree()
PARTITION BY snapshot_id
ORDER BY (target_domain, source_domain)
AS SELECT
    snapshot_id,
    target_domain,
    source_domain,
    count() as backlink_count,
    min(discovered_at) as first_seen,
    max(discovered_at) as last_seen
FROM cc_edges
GROUP BY snapshot_id, target_domain, source_domain;

-- Anchor distribution aggregate
CREATE MATERIALIZED VIEW cc_anchors_mv
ENGINE = SummingMergeTree()
PARTITION BY snapshot_id
ORDER BY (target_domain, anchor)
AS SELECT
    snapshot_id,
    target_domain,
    anchor,
    count() as count
FROM cc_edges
GROUP BY snapshot_id, target_domain, anchor;
```

**Files to Create:**
```
infra/clickhouse/
├── init.sql
└── cc_schema.sql
```

**Acceptance Criteria:**
- [x] ClickHouse schema files created
- [x] Tables partition by snapshot + domain prefix
- [x] Materialized views for ref domains and anchors
- [x] Docker Compose overlay includes ClickHouse

---

### Task 3.1.4: Create storage adapter interface

**Description:** Abstract storage layer for Postgres/ClickHouse.

**Acceptance Criteria:**
- [x] `apps/commoncrawl_ingest/src/semrush_commoncrawl/storage/base.py` created
- [x] Protocol defines: insert_edges, query_refdomains, query_backlinks, query_anchors
- [x] PostgresStorage implementation
- [x] ClickHouseStorage implementation (optional)
- [x] Storage backend selectable via config

**Interface:**
```python
class EdgeStorage(Protocol):
    async def insert_edges(self, edges: list[Edge]) -> int: ...
    async def query_refdomains(
        self, domain: str, snapshot_id: str | None, limit: int
    ) -> list[RefDomain]: ...
    async def query_backlinks(
        self, domain: str, snapshot_id: str | None, limit: int, offset: int
    ) -> list[Backlink]: ...
    async def query_anchors(
        self, domain: str, snapshot_id: str | None, limit: int
    ) -> list[AnchorCount]: ...
```

---

## Epic 3.2: Ingestion Pipeline

### Task 3.2.1: Implement snapshot registry

**Description:** Manage known Common Crawl snapshots.

**Acceptance Criteria:**
- [x] `GET /commoncrawl/snapshots` lists snapshots
- [x] Returns snapshot_id, status, date_range, ingested_at
- [x] Can seed known snapshots from CC index
- [x] Tracks ingestion status per snapshot

---

### Task 3.2.2: Implement WAT file downloader

**Description:** Download WAT metadata files from Common Crawl.

**Acceptance Criteria:**
- [x] `apps/commoncrawl_ingest/src/semrush_commoncrawl/downloader.py` created
- [x] Fetches wat.paths.gz for snapshot
- [x] Streams individual WAT files from S3
- [x] Supports domain filtering to reduce data
- [x] Handles gzip decompression
- [x] Parallel download with configurable concurrency

**Common Crawl Structure:**
```
s3://commoncrawl/crawl-data/CC-MAIN-YYYY-WW/wat.paths.gz
  → Lists all WAT segment files
s3://commoncrawl/crawl-data/CC-MAIN-YYYY-WW/segments/{segment}/wat/{file}.warc.wat.gz
  → Individual WAT files with metadata
```

---

### Task 3.2.3: Implement WAT parser

**Description:** Parse WAT files to extract link edges.

**Acceptance Criteria:**
- [x] `apps/commoncrawl_ingest/src/semrush_commoncrawl/parser.py` created
- [x] Parses WARC-formatted WAT records
- [x] Extracts Links metadata from JSON payloads
- [x] Normalizes source/target URLs
- [x] Extracts anchor text and rel flags
- [x] Filters to links with anchor (optional)
- [x] Yields Edge objects

**WAT Record Format:**
```json
{
  "Envelope": {
    "Payload-Metadata": {
      "HTTP-Response-Metadata": {
        "HTML-Metadata": {
          "Links": [
            {"path": "A@/href", "url": "...", "text": "anchor"}
          ]
        }
      }
    }
  }
}
```

---

### Task 3.2.4: Implement domain filtering

**Description:** Filter edges to target domains of interest.

**Acceptance Criteria:**
- [x] Supports allowlist of target domains
- [x] Supports domain pattern matching (*.example.com)
- [x] Reduces storage by 99%+ when focused
- [x] Configurable in ingestion spec

**Subset Strategy (MVP):**
- Focus on user's project domains + competitors
- Or: random sample (1 in N edges)
- Or: top-N domains by frequency

---

### Task 3.2.5: Build ingestion orchestrator

**Description:** Coordinate download, parse, store pipeline.

**Acceptance Criteria:**
- [x] `apps/commoncrawl_ingest/src/semrush_commoncrawl/orchestrator.py` created
- [x] Loads subset spec from request/config
- [x] Downloads WAT segments in parallel
- [x] Parses and filters edges
- [x] Batches inserts to storage
- [x] Tracks progress in commoncrawl_snapshots
- [x] Emits events: `commoncrawl.ingest_progress`, `commoncrawl.ingest_completed`
- [x] Handles failures gracefully with retry

**Orchestration Flow:**
1. Create/update snapshot record (status=ingesting)
2. Fetch wat.paths.gz, filter to subset
3. For each WAT file:
   - Download and decompress
   - Parse edges with domain filter
   - Batch insert to storage
   - Update progress
4. Update snapshot (status=ingested, stats)
5. Emit completion event

---

### Task 3.2.6: Implement ingestion trigger endpoint

**Description:** API endpoint to start ingestion.

**Acceptance Criteria:**
- [x] `POST /commoncrawl/ingest` triggers ingestion
- [x] Accepts snapshot_id and subset spec
- [x] Validates snapshot exists
- [x] Returns 202 Accepted with job info
- [x] Admin/operator only (protected endpoint)
- [x] Rate limited to prevent abuse

**Request Body:**
```json
{
  "snapshot_id": "CC-MAIN-2025-05",
  "subset": {
    "target_domains": ["example.com", "competitor.com"],
    "sample_rate": 1.0,
    "max_edges": 10000000
  },
  "build_aggregates": true
}
```

---

## Epic 3.3: Aggregate Materialization

### Task 3.3.1: Build ref domains aggregator

**Description:** Compute referring domains per target domain.

**Acceptance Criteria:**
- [x] Groups edges by (target_domain, source_domain)
- [x] Counts backlinks per ref domain
- [x] Tracks first_seen/last_seen
- [x] Stores in `commoncrawl_refdomains` table or ClickHouse MV
- [x] Updates incrementally after ingestion

**Schema (Postgres fallback):**
```sql
CREATE TABLE commoncrawl_refdomains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id TEXT NOT NULL,
    target_domain TEXT NOT NULL,
    source_domain TEXT NOT NULL,
    backlink_count INTEGER NOT NULL,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    UNIQUE(snapshot_id, target_domain, source_domain)
);

CREATE INDEX idx_cc_refdomains_target ON commoncrawl_refdomains(target_domain, snapshot_id);
```

---

### Task 3.3.2: Build anchor aggregator

**Description:** Compute anchor text distribution per domain.

**Acceptance Criteria:**
- [x] Groups edges by (target_domain, anchor)
- [x] Counts occurrences per anchor
- [x] Normalizes anchor text (trim, lowercase optional)
- [x] Stores in `commoncrawl_anchors` table or ClickHouse MV
- [x] Top-N anchors queryable

**Schema (Postgres fallback):**
```sql
CREATE TABLE commoncrawl_anchors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id TEXT NOT NULL,
    target_domain TEXT NOT NULL,
    anchor TEXT NOT NULL,
    count INTEGER NOT NULL,
    UNIQUE(snapshot_id, target_domain, anchor)
);

CREATE INDEX idx_cc_anchors_target ON commoncrawl_anchors(target_domain, snapshot_id);
```

---

### Task 3.3.3: Implement aggregate build job

**Description:** Background job to build aggregates after ingestion.

**Acceptance Criteria:**
- [x] Runs automatically after ingestion completes
- [x] Can be triggered manually
- [x] Builds ref domains and anchors aggregates
- [x] Updates snapshot record with completion
- [x] Works for both Postgres and ClickHouse

---

## Epic 3.4: Domain Explorer API

### Task 3.4.1: Implement ref domains endpoint

**Description:** API to get referring domains for a domain.

**Acceptance Criteria:**
- [x] `GET /links/domain/{domain}/refdomains` returns ref domains
- [x] Supports optional snapshot_id (defaults to latest)
- [x] Supports limit parameter (default 100, max 10000)
- [x] Returns: ref_domain, backlinks count, first_seen, last_seen
- [x] Sorted by backlink count descending

**Response:**
```json
{
  "items": [
    {
      "ref_domain": "blog.example.org",
      "backlinks": 45,
      "first_seen": "2025-01-15",
      "last_seen": "2025-01-15"
    }
  ]
}
```

---

### Task 3.4.2: Implement backlinks endpoint

**Description:** API to get individual backlinks for a domain.

**Acceptance Criteria:**
- [x] `GET /links/domain/{domain}/backlinks` returns backlinks
- [x] Supports pagination (limit, offset)
- [x] Supports filter by source_domain
- [x] Returns: source_url, source_domain, target_url, anchor, flags
- [x] Sorted by source_domain, source_url

**Response:**
```json
{
  "items": [
    {
      "source_url": "https://blog.example.org/post/123",
      "source_domain": "blog.example.org",
      "target_url": "https://example.com/product",
      "target_domain": "example.com",
      "anchor": "great product",
      "flags": {}
    }
  ]
}
```

---

### Task 3.4.3: Implement anchors endpoint

**Description:** API to get anchor distribution for a domain.

**Acceptance Criteria:**
- [x] `GET /links/domain/{domain}/anchors` returns anchor distribution
- [x] Supports limit parameter
- [x] Returns: anchor, count
- [x] Sorted by count descending

**Response:**
```json
{
  "items": [
    {"anchor": "example brand", "count": 234},
    {"anchor": "click here", "count": 89}
  ]
}
```

---

## Epic 3.5: New/Lost Detection

### Task 3.5.1: Implement snapshot comparison

**Description:** Compare edges between two snapshots.

**Acceptance Criteria:**
- [x] `GET /links/domain/{domain}/new-lost?snapshot_a=...&snapshot_b=...`
- [x] Returns new ref domains (in B, not in A)
- [x] Returns lost ref domains (in A, not in B)
- [x] Works at ref-domain level (not individual links)
- [x] Efficient query using aggregate tables

**Algorithm:**
```python
async def compute_new_lost(domain: str, snapshot_a: str, snapshot_b: str):
    refs_a = set(await get_refdomains(domain, snapshot_a))
    refs_b = set(await get_refdomains(domain, snapshot_b))

    new = refs_b - refs_a
    lost = refs_a - refs_b

    return NewLostResult(
        new=[{"ref_domain": d, "backlinks": count} for d in new],
        lost=[{"ref_domain": d, "backlinks": count} for d in lost]
    )
```

---

### Task 3.5.2: Implement new/lost time series

**Description:** Track new/lost over multiple snapshots.

**Acceptance Criteria:**
- [x] Computes new/lost between consecutive snapshots
- [x] Returns series: date, new_count, lost_count
- [x] Requires multiple ingested snapshots

---

## Epic 3.6: Competitive Analysis

### Task 3.6.1: Implement domain overlap

**Description:** Find shared referring domains between domain and competitors.

**Acceptance Criteria:**
- [x] `GET /links/domain/{domain}/overlap?competitors=a.com,b.com`
- [x] Returns ref domains linking to both domain and any competitor
- [x] Shows which domains each ref_domain links to
- [x] Useful for competitive positioning

**Algorithm:**
```python
async def compute_overlap(domain: str, competitors: list[str], snapshot_id: str):
    all_domains = [domain] + competitors
    ref_sets = {d: set(await get_refdomains(d, snapshot_id)) for d in all_domains}

    # Find refs that link to multiple domains
    all_refs = set.union(*ref_sets.values())
    shared = []
    for ref in all_refs:
        links_to = {d: ref in ref_sets[d] for d in all_domains}
        if sum(links_to.values()) >= 2:  # Links to at least 2
            shared.append({"ref_domain": ref, "links_to": links_to})

    return OverlapResult(domain=domain, competitors=competitors, shared_ref_domains=shared)
```

**Response:**
```json
{
  "domain": "example.com",
  "competitors": ["competitor1.com", "competitor2.com"],
  "shared_ref_domains": [
    {
      "ref_domain": "techblog.com",
      "in_domain": true,
      "in_competitors": {
        "competitor1.com": true,
        "competitor2.com": false
      }
    }
  ]
}
```

---

### Task 3.6.2: Implement domain intersect

**Description:** Find referring domains linking to competitors but not to you.

**Acceptance Criteria:**
- [x] `GET /links/domain/{domain}/intersect?competitors=a.com,b.com`
- [x] Returns ref domains that link to at least one competitor but NOT to domain
- [x] Shows which competitors each ref_domain links to
- [x] Useful for link building opportunities

**Algorithm:**
```python
async def compute_intersect(domain: str, competitors: list[str], snapshot_id: str):
    domain_refs = set(await get_refdomains(domain, snapshot_id))
    competitor_refs = {c: set(await get_refdomains(c, snapshot_id)) for c in competitors}

    # All refs to competitors
    all_competitor_refs = set.union(*competitor_refs.values())

    # Not linking to domain
    intersect_refs = all_competitor_refs - domain_refs

    result = []
    for ref in intersect_refs:
        links_to = {c: ref in competitor_refs[c] for c in competitors}
        result.append({"ref_domain": ref, "links_to_competitors": links_to})

    return IntersectResult(domain=domain, competitors=competitors, intersect_ref_domains=result)
```

---

### Task 3.6.3: Project-scoped competitive analysis

**Description:** Use project competitors for overlap/intersect.

**Acceptance Criteria:**
- [x] `GET /projects/{id}/backlinks/overlap` uses project's competitors
- [x] `GET /projects/{id}/backlinks/intersect` uses project's competitors
- [x] Automatically includes project's primary site domain
- [x] Merges with other backlink sources (not just CC)

---

## Epic 3.7: CSV Import & Multi-Source Merge

### Task 3.7.1: Implement CSV import endpoint

**Description:** Import backlinks from CSV file.

**Acceptance Criteria:**
- [x] `POST /projects/{id}/backlinks/import` accepts CSV file
- [x] Parses CSV with columns: source_url, target_url, anchor (optional)
- [x] Validates URL formats
- [x] Stores in link_facts table with source='import'
- [x] Supports multiple import sources (label in request)
- [x] Returns import stats (rows imported, errors)

**CSV Format:**
```csv
source_url,target_url,anchor
https://blog.example.org/post,https://example.com/,Brand Name
https://news.site.com/article,https://example.com/product,Click Here
```

---

### Task 3.7.2: Implement project backlinks merge

**Description:** Merge backlinks from all sources for project view.

**Acceptance Criteria:**
- [x] `GET /projects/{id}/backlinks/targets` aggregates all sources
- [x] Sources: commoncrawl, import, provider (GSC/BWT links), crawl
- [x] Deduplicates by (source_domain, target_url)
- [x] Returns unified view sorted by backlink count

---

### Task 3.7.3: Implement project new/lost endpoint

**Description:** New/lost across all project sources.

**Acceptance Criteria:**
- [x] `GET /projects/{id}/backlinks/new-lost` returns time series
- [x] Aggregates from all sources with timestamps
- [x] Returns date, new, lost series

---

### Task 3.7.4: Implement project anchors endpoint

**Description:** Anchor distribution across all sources.

**Acceptance Criteria:**
- [x] `GET /projects/{id}/backlinks/anchors` returns distribution
- [x] Merges anchors from all sources
- [x] Returns anchor, count pairs

---

## Verification Checklist

### Common Crawl Infrastructure
- [x] Snapshot registry lists available snapshots
- [x] WAT files download correctly
- [x] WAT parser extracts edges
- [x] Domain filtering reduces volume
- [x] Edges stored in Postgres (or ClickHouse)

### Ingestion Pipeline
- [x] Ingest endpoint triggers job
- [x] Progress tracked in database
- [x] Aggregates built after ingestion
- [x] Completion event emitted

### Domain Explorer
- [x] Ref domains endpoint returns data
- [x] Backlinks endpoint with pagination
- [x] Anchors endpoint returns distribution
- [x] New/lost comparison works
- [x] Overlap analysis works
- [x] Intersect analysis works

### Project Backlinks
- [x] CSV import works
- [x] Multi-source merge works
- [x] Project overlap uses competitors
- [x] Project intersect uses competitors

---

## Notes

### Common Crawl Data Scale

**Full Snapshot:**
- ~3B pages crawled per month
- ~100B+ link edges per snapshot
- Uncompressed: hundreds of TB

**Subset Strategy (MVP):**
- Focus on specific target domains
- Sample 1-5% of WAT files
- Limit to top-N domains by frequency
- Expect 1M-100M edges per ingested snapshot

### Storage Recommendations

| Scale | Storage | Notes |
|-------|---------|-------|
| < 10M edges | Postgres | MVP sufficient |
| 10M-1B edges | ClickHouse | Recommended |
| > 1B edges | ClickHouse + sharding | Consider Elasticsearch |

### Performance Considerations
- Batch inserts (10K+ rows per batch)
- Use COPY for Postgres bulk loads
- ClickHouse async inserts
- Index after bulk load
- Materialized views for aggregates

### Next Sprint Dependencies
This sprint provides:
- Backlink data for all project domains
- Competitive link intelligence
- Export-ready backlink data

Required by:
- Sprint 4: Backlink exports and reports
- Sprint 2b: Backlink-based alerts (future)
