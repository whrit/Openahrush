-- ClickHouse Initialization Script for Openahrush
-- ================================================
-- This script is automatically executed when the ClickHouse container starts.
-- It creates the database and initializes all required schemas.
--
-- File Structure:
-- ---------------
-- - init.sql (this file): Database creation and legacy tables
-- - cc_schema.sql: Common Crawl edge storage schema (sourced below)
--
-- Usage:
-- ------
-- Mount this directory to /docker-entrypoint-initdb.d/ in the container.
-- ClickHouse executes .sql files in alphabetical order on first start.

-- =============================================================================
-- DATABASE SETUP
-- =============================================================================

-- Create the main database
CREATE DATABASE IF NOT EXISTS semrush;

-- Use the database for subsequent operations
USE semrush;

-- =============================================================================
-- INGEST METADATA TABLE
-- =============================================================================
-- Tracks Common Crawl ingestion jobs and their progress.
-- Used for monitoring, resumption, and debugging of ingest pipelines.

CREATE TABLE IF NOT EXISTS commoncrawl_ingest_metadata (
    ingest_id UUID DEFAULT generateUUIDv4(),
    crawl_index String NOT NULL COMMENT 'Common Crawl index identifier (e.g., CC-MAIN-2024-10)',
    ingest_timestamp DateTime DEFAULT now(),
    status Enum8(
        'pending' = 0,
        'in_progress' = 1,
        'completed' = 2,
        'failed' = 3
    ) DEFAULT 'pending',
    error_message Nullable(String),
    records_processed UInt64 DEFAULT 0,
    records_total UInt64 DEFAULT 0,
    last_updated DateTime DEFAULT now()
)
ENGINE = MergeTree()
ORDER BY (ingest_timestamp, ingest_id)
PARTITION BY toYYYYMM(ingest_timestamp);


-- =============================================================================
-- DOMAIN STATS DICTIONARY TABLE (LEGACY)
-- =============================================================================
-- Simple domain statistics table for quick lookups.
-- Note: For Common Crawl edge data, prefer cc_domain_stats_mv from cc_schema.sql

CREATE TABLE IF NOT EXISTS commoncrawl_domain_stats (
    domain String,
    crawl_date Date,
    total_urls UInt64 DEFAULT 0,
    total_outbound_links UInt64 DEFAULT 0,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (domain, crawl_date);


-- =============================================================================
-- COMMON CRAWL EDGE SCHEMA
-- =============================================================================
-- The main schema for Common Crawl edge storage is defined in cc_schema.sql.
-- ClickHouse automatically executes .sql files in alphabetical order,
-- so cc_schema.sql will be executed after this file.
--
-- Tables created by cc_schema.sql:
-- - cc_edges: Raw link edges (billions of rows)
-- - cc_refdomains_mv: Referring domains materialized view
-- - cc_anchors_mv: Anchor text distribution materialized view
-- - cc_domain_stats_mv: Domain-level statistics materialized view
-- - cc_snapshots: Snapshot registry table
-- - cc_top_refdomains: Helper view for top referring domains
-- - cc_top_anchors: Helper view for top anchor texts
-- - cc_domain_overview: Helper view for domain overview stats
