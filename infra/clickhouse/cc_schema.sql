-- ClickHouse Schema for Common Crawl Edge Storage
-- ================================================
-- This schema provides scalable storage for billions of backlink edges
-- extracted from Common Crawl data. It includes:
--   1. Raw edges table (cc_edges) - primary storage for link data
--   2. Referring domains materialized view (cc_refdomains_mv) - aggregated by domain pairs
--   3. Anchor distribution materialized view (cc_anchors_mv) - anchor text aggregates
--   4. Domain stats materialized view (cc_domain_stats_mv) - quick domain-level lookups
--
-- Design Rationale:
-- -----------------
-- - LowCardinality(String) for domains: Domains repeat frequently, LowCardinality
--   provides dictionary encoding with significant storage and query performance gains.
-- - Partitioning by (snapshot_id, domain prefix): Enables efficient partition pruning
--   for snapshot-specific queries and distributes data for parallel processing.
-- - ORDER BY (target_domain, source_domain, source_url): Optimized for the most common
--   query pattern: "find all backlinks to a given target domain".
-- - SummingMergeTree for aggregates: Automatic incremental aggregation on merge,
--   perfect for count-based metrics.
-- - Separate snapshot tracking: Supports time-travel queries and new/lost analysis.
--
-- Usage:
-- ------
-- This file is sourced by init.sql during container initialization.
-- Tables are created in the 'semrush' database.

-- =============================================================================
-- RAW EDGES TABLE
-- =============================================================================
-- Stores individual link relationships extracted from Common Crawl WAT files.
-- Each row represents a single <a href> link from source_url to target_url.

CREATE TABLE IF NOT EXISTS cc_edges (
    -- Common Crawl snapshot identifier (e.g., 'CC-MAIN-2024-10')
    snapshot_id String,

    -- Source (linking) page information
    source_url String,
    source_domain LowCardinality(String),

    -- Target (linked-to) page information
    target_url String,
    target_domain LowCardinality(String),

    -- Link metadata
    anchor String DEFAULT '',

    -- Rel attribute flags (stored as UInt8 for efficiency)
    -- 1 = present, 0 = absent
    rel_nofollow UInt8 DEFAULT 0,
    rel_ugc UInt8 DEFAULT 0,
    rel_sponsored UInt8 DEFAULT 0,

    -- Timestamps
    discovered_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
-- Partition by snapshot and first 2 chars of target domain for distribution
-- This enables efficient partition pruning for snapshot-specific queries
-- and spreads data across partitions for parallel processing
PARTITION BY (snapshot_id, substring(target_domain, 1, 2))
-- Primary ordering optimized for "backlinks to domain X" queries
-- Most queries filter by target_domain first, then optionally by source_domain
ORDER BY (target_domain, source_domain, source_url)
SETTINGS index_granularity = 8192;


-- =============================================================================
-- REFERRING DOMAINS MATERIALIZED VIEW
-- =============================================================================
-- Pre-aggregated view of unique referring domains per target domain.
-- Uses SummingMergeTree for automatic incremental aggregation on merges.
-- Answers: "How many backlinks does domain X have from domain Y?"

CREATE MATERIALIZED VIEW IF NOT EXISTS cc_refdomains_mv
ENGINE = SummingMergeTree()
PARTITION BY snapshot_id
ORDER BY (target_domain, source_domain)
AS SELECT
    snapshot_id,
    target_domain,
    source_domain,
    count() AS backlink_count,
    min(discovered_at) AS first_seen,
    max(discovered_at) AS last_seen
FROM cc_edges
GROUP BY snapshot_id, target_domain, source_domain;


-- =============================================================================
-- ANCHOR TEXT DISTRIBUTION MATERIALIZED VIEW
-- =============================================================================
-- Pre-aggregated view of anchor text usage per target domain.
-- Answers: "What anchor texts are used in links to domain X?"

CREATE MATERIALIZED VIEW IF NOT EXISTS cc_anchors_mv
ENGINE = SummingMergeTree()
PARTITION BY snapshot_id
ORDER BY (target_domain, anchor)
AS SELECT
    snapshot_id,
    target_domain,
    anchor,
    count() AS count
FROM cc_edges
GROUP BY snapshot_id, target_domain, anchor;


-- =============================================================================
-- DOMAIN STATS MATERIALIZED VIEW
-- =============================================================================
-- Quick domain-level statistics for dashboard and overview queries.
-- Provides total backlink count and unique referring domain count.
-- Note: uniqExact is used for accurate counts; consider uniq() for faster
-- approximate counts at very large scale.

CREATE MATERIALIZED VIEW IF NOT EXISTS cc_domain_stats_mv
ENGINE = SummingMergeTree()
PARTITION BY snapshot_id
ORDER BY target_domain
AS SELECT
    snapshot_id,
    target_domain,
    count() AS total_backlinks,
    uniqExact(source_domain) AS unique_ref_domains
FROM cc_edges
GROUP BY snapshot_id, target_domain;


-- =============================================================================
-- SNAPSHOT REGISTRY TABLE
-- =============================================================================
-- Tracks ingestion status and metadata for each Common Crawl snapshot.
-- Mirrors the Postgres commoncrawl_snapshots table for ClickHouse-local queries.

CREATE TABLE IF NOT EXISTS cc_snapshots (
    snapshot_id String,
    status LowCardinality(String) DEFAULT 'known',
    edges_count UInt64 DEFAULT 0,
    refdomains_count UInt64 DEFAULT 0,
    anchors_count UInt64 DEFAULT 0,
    ingested_at Nullable(DateTime),
    aggregates_built_at Nullable(DateTime),
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY snapshot_id;


-- =============================================================================
-- HELPER VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Top referring domains for a target (use with WHERE target_domain = 'example.com')
-- Example: SELECT * FROM cc_top_refdomains WHERE target_domain = 'example.com' LIMIT 100
CREATE VIEW IF NOT EXISTS cc_top_refdomains AS
SELECT
    snapshot_id,
    target_domain,
    source_domain,
    sum(backlink_count) AS total_backlinks,
    min(first_seen) AS first_seen,
    max(last_seen) AS last_seen
FROM cc_refdomains_mv
GROUP BY snapshot_id, target_domain, source_domain
ORDER BY total_backlinks DESC;


-- Top anchors for a target domain
-- Example: SELECT * FROM cc_top_anchors WHERE target_domain = 'example.com' LIMIT 100
CREATE VIEW IF NOT EXISTS cc_top_anchors AS
SELECT
    snapshot_id,
    target_domain,
    anchor,
    sum(count) AS total_count
FROM cc_anchors_mv
GROUP BY snapshot_id, target_domain, anchor
ORDER BY total_count DESC;


-- Domain overview with aggregated stats across all snapshots
-- Example: SELECT * FROM cc_domain_overview WHERE target_domain = 'example.com'
CREATE VIEW IF NOT EXISTS cc_domain_overview AS
SELECT
    target_domain,
    count(DISTINCT snapshot_id) AS snapshot_count,
    sum(total_backlinks) AS total_backlinks_all_snapshots,
    max(unique_ref_domains) AS max_unique_ref_domains
FROM cc_domain_stats_mv
GROUP BY target_domain;
