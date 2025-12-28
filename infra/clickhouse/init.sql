-- ClickHouse initialization script for Openahrush Common Crawl ingestion
-- This file is automatically executed when the ClickHouse container starts
--
-- NOTE: This is a placeholder. The actual schema will be populated based on
-- COMMONCRAWL_INGESTION.md specifications when Common Crawl integration is implemented.
--
-- Expected tables (to be created):
-- - commoncrawl_domains: Indexed domain data from Common Crawl
-- - commoncrawl_backlinks: Extracted backlink relationships
-- - commoncrawl_page_metadata: Page-level metadata (title, description, etc.)
-- - commoncrawl_index_references: References to WAT/WET files for traceability

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS openahrush;

-- Use the database
USE openahrush;

-- Placeholder table for tracking Common Crawl ingest progress
CREATE TABLE IF NOT EXISTS commoncrawl_ingest_metadata (
    ingest_id UUID DEFAULT generateUUIDv4(),
    crawl_index String NOT NULL,
    ingest_timestamp DateTime DEFAULT now(),
    status Enum8('pending' = 0, 'in_progress' = 1, 'completed' = 2, 'failed' = 3) DEFAULT 'pending',
    error_message Nullable(String),
    records_processed UInt64 DEFAULT 0,
    last_updated DateTime DEFAULT now(),

    PRIMARY KEY (ingest_id, ingest_timestamp)
) ENGINE = MergeTree()
ORDER BY (ingest_timestamp, ingest_id)
PARTITION BY toYYYYMM(ingest_timestamp);

-- Dictionary table for domain statistics
CREATE TABLE IF NOT EXISTS commoncrawl_domain_stats (
    domain String PRIMARY KEY,
    crawl_date Date,
    total_urls UInt64 DEFAULT 0,
    total_outbound_links UInt64 DEFAULT 0,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (domain, crawl_date);
