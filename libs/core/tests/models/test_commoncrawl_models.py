"""
Tests for Common Crawl infrastructure models.

Following TDD: These tests are written FIRST, then the implementation.

Tests cover:
- CommonCrawlSnapshot: Track Common Crawl snapshot ingestion
- CommonCrawlEdge: Raw backlink data from Common Crawl
- CommonCrawlRefDomain: Aggregated referring domain data
- CommonCrawlAnchor: Aggregated anchor text data

Note: Tests that require database operations are marked with pytest.mark.db
and require a PostgreSQL database to run (SQLite doesn't support JSONB/ARRAY).
"""

from datetime import UTC, date, datetime

from semrush_core.models.commoncrawl import (
    CommonCrawlAnchor,
    CommonCrawlEdge,
    CommonCrawlRefDomain,
    CommonCrawlSnapshot,
    SnapshotStatus,
)

# =============================================================================
# CommonCrawlSnapshot Tests
# =============================================================================


class TestCommonCrawlSnapshotModel:
    """Tests for the CommonCrawlSnapshot model."""

    def test_snapshot_has_required_fields(self):
        """CommonCrawlSnapshot should have all required fields."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.KNOWN.value,
        )

        assert snapshot.snapshot_id == "CC-MAIN-2025-05"
        assert snapshot.status == "known"

    def test_snapshot_status_enum_values(self):
        """SnapshotStatus enum should have expected values."""
        expected_statuses = ["known", "ingesting", "ingested", "failed"]
        actual_statuses = [s.value for s in SnapshotStatus]
        assert sorted(actual_statuses) == sorted(expected_statuses)

    def test_snapshot_has_date_range_fields(self):
        """CommonCrawlSnapshot should have date range fields."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.KNOWN.value,
            date_range_start=date(2025, 1, 1),
            date_range_end=date(2025, 1, 15),
        )

        assert snapshot.date_range_start == date(2025, 1, 1)
        assert snapshot.date_range_end == date(2025, 1, 15)

    def test_snapshot_has_spec_jsonb_field(self):
        """CommonCrawlSnapshot should have spec JSONB field."""
        spec = {
            "warc_paths": ["path1", "path2"],
            "segment_count": 100,
        }
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.KNOWN.value,
            spec=spec,
        )

        assert snapshot.spec["warc_paths"] == ["path1", "path2"]
        assert snapshot.spec["segment_count"] == 100

    def test_snapshot_has_count_fields(self):
        """CommonCrawlSnapshot should have total_records and edges_ingested fields."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.INGESTED.value,
            total_records=1000000000,
            edges_ingested=500000000,
        )

        assert snapshot.total_records == 1000000000
        assert snapshot.edges_ingested == 500000000

    def test_snapshot_has_timing_fields(self):
        """CommonCrawlSnapshot should have ingestion timing fields."""
        now = datetime.now(UTC)
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.INGESTING.value,
            ingestion_started_at=now,
        )

        assert snapshot.ingestion_started_at == now
        assert hasattr(snapshot, "ingestion_completed_at")
        assert hasattr(snapshot, "created_at")

    def test_snapshot_has_error_and_notes_fields(self):
        """CommonCrawlSnapshot should have error_message and notes fields."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.FAILED.value,
            error_message="Connection timeout to S3",
            notes="Retry scheduled for next maintenance window",
        )

        assert snapshot.error_message == "Connection timeout to S3"
        assert snapshot.notes == "Retry scheduled for next maintenance window"


class TestCommonCrawlSnapshotMethods:
    """Tests for CommonCrawlSnapshot helper methods."""

    def test_is_known_status(self):
        """is_known should return True for known status."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.KNOWN.value,
        )
        assert snapshot.is_known is True
        assert snapshot.is_ingesting is False

    def test_is_ingesting_status(self):
        """is_ingesting should return True for ingesting status."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.INGESTING.value,
        )
        assert snapshot.is_ingesting is True

    def test_is_ingested_status(self):
        """is_ingested should return True for ingested status."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.INGESTED.value,
        )
        assert snapshot.is_ingested is True

    def test_is_failed_status(self):
        """is_failed should return True for failed status."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.FAILED.value,
        )
        assert snapshot.is_failed is True

    def test_ingestion_progress(self):
        """ingestion_progress should calculate percentage correctly."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.INGESTING.value,
            total_records=1000,
            edges_ingested=250,
        )
        assert snapshot.ingestion_progress == 25.0

    def test_ingestion_progress_when_no_total(self):
        """ingestion_progress should return None when total_records is None."""
        snapshot = CommonCrawlSnapshot(
            snapshot_id="CC-MAIN-2025-05",
            status=SnapshotStatus.INGESTING.value,
        )
        assert snapshot.ingestion_progress is None


# =============================================================================
# CommonCrawlEdge Tests
# =============================================================================


class TestCommonCrawlEdgeModel:
    """Tests for the CommonCrawlEdge model."""

    def test_edge_has_required_fields(self):
        """CommonCrawlEdge should have all required fields."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/article",
            target_domain="target.com",
        )

        assert edge.snapshot_id == "CC-MAIN-2025-05"
        assert edge.source_url == "https://example.com/page"
        assert edge.source_domain == "example.com"
        assert edge.target_url == "https://target.com/article"
        assert edge.target_domain == "target.com"

    def test_edge_has_anchor_field(self):
        """CommonCrawlEdge should have anchor text field."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/article",
            target_domain="target.com",
            anchor="Read more about SEO",
        )

        assert edge.anchor == "Read more about SEO"

    def test_edge_has_rel_flags_array(self):
        """CommonCrawlEdge should have rel_flags array field."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/article",
            target_domain="target.com",
            rel_flags=["nofollow", "ugc"],
        )

        assert edge.rel_flags == ["nofollow", "ugc"]

    def test_edge_has_discovered_at_field(self):
        """CommonCrawlEdge should have discovered_at timestamp field."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/article",
            target_domain="target.com",
        )

        # discovered_at gets a server default, so check it exists as attribute
        assert hasattr(edge, "discovered_at")


class TestCommonCrawlEdgeMethods:
    """Tests for CommonCrawlEdge helper methods."""

    def test_is_nofollow_with_nofollow_flag(self):
        """is_nofollow should return True when rel_flags contains nofollow."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            rel_flags=["nofollow"],
        )
        assert edge.is_nofollow is True

    def test_is_nofollow_without_flag(self):
        """is_nofollow should return False when rel_flags is None or empty."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
        )
        assert edge.is_nofollow is False

    def test_is_dofollow(self):
        """is_dofollow should return True when no nofollow flag present."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            rel_flags=["ugc"],
        )
        assert edge.is_dofollow is True

    def test_is_ugc(self):
        """is_ugc should return True when rel_flags contains ugc."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            rel_flags=["ugc"],
        )
        assert edge.is_ugc is True

    def test_is_sponsored(self):
        """is_sponsored should return True when rel_flags contains sponsored."""
        edge = CommonCrawlEdge(
            snapshot_id="CC-MAIN-2025-05",
            source_url="https://example.com/",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            rel_flags=["sponsored"],
        )
        assert edge.is_sponsored is True


# =============================================================================
# CommonCrawlRefDomain Tests
# =============================================================================


class TestCommonCrawlRefDomainModel:
    """Tests for the CommonCrawlRefDomain model."""

    def test_refdomain_has_required_fields(self):
        """CommonCrawlRefDomain should have all required fields."""
        refdomain = CommonCrawlRefDomain(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            source_domain="referrer.com",
            backlink_count=15,
        )

        assert refdomain.snapshot_id == "CC-MAIN-2025-05"
        assert refdomain.target_domain == "mysite.com"
        assert refdomain.source_domain == "referrer.com"
        assert refdomain.backlink_count == 15

    def test_refdomain_has_first_seen_last_seen(self):
        """CommonCrawlRefDomain should have first_seen and last_seen fields."""
        now = datetime.now(UTC)
        refdomain = CommonCrawlRefDomain(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            source_domain="referrer.com",
            backlink_count=15,
            first_seen=now,
            last_seen=now,
        )

        assert refdomain.first_seen == now
        assert refdomain.last_seen == now


class TestCommonCrawlRefDomainMethods:
    """Tests for CommonCrawlRefDomain helper methods."""

    def test_is_active_when_seen_recently(self):
        """is_active should return True when last_seen is recent."""
        now = datetime.now(UTC)
        refdomain = CommonCrawlRefDomain(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            source_domain="referrer.com",
            backlink_count=15,
            first_seen=now,
            last_seen=now,
        )

        # is_active checks if last_seen is not None
        assert refdomain.is_active is True

    def test_is_active_when_last_seen_none(self):
        """is_active should return False when last_seen is None."""
        refdomain = CommonCrawlRefDomain(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            source_domain="referrer.com",
            backlink_count=15,
        )
        assert refdomain.is_active is False


# =============================================================================
# CommonCrawlAnchor Tests
# =============================================================================


class TestCommonCrawlAnchorModel:
    """Tests for the CommonCrawlAnchor model."""

    def test_anchor_has_required_fields(self):
        """CommonCrawlAnchor should have all required fields."""
        anchor = CommonCrawlAnchor(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            anchor="SEO tools",
            count=42,
        )

        assert anchor.snapshot_id == "CC-MAIN-2025-05"
        assert anchor.target_domain == "mysite.com"
        assert anchor.anchor == "SEO tools"
        assert anchor.count == 42


class TestCommonCrawlAnchorMethods:
    """Tests for CommonCrawlAnchor helper methods."""

    def test_anchor_length(self):
        """anchor_length should return the character count."""
        anchor = CommonCrawlAnchor(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            anchor="Click here for SEO tools",
            count=10,
        )
        assert anchor.anchor_length == len("Click here for SEO tools")

    def test_is_branded_anchor(self):
        """is_branded should return True if anchor contains domain name."""
        anchor = CommonCrawlAnchor(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            anchor="Visit mysite.com for more",
            count=10,
        )
        assert anchor.is_branded is True

    def test_is_not_branded_anchor(self):
        """is_branded should return False if anchor doesn't contain domain."""
        anchor = CommonCrawlAnchor(
            snapshot_id="CC-MAIN-2025-05",
            target_domain="mysite.com",
            anchor="Click here for SEO tools",
            count=10,
        )
        assert anchor.is_branded is False


# =============================================================================
# Relationship Tests
# =============================================================================


class TestCommonCrawlRelationships:
    """Tests for model relationships - primarily documentation/design verification."""

    def test_edge_has_snapshot_relationship_attr(self):
        """CommonCrawlEdge should have snapshot relationship attribute."""
        assert hasattr(CommonCrawlEdge, "snapshot")

    def test_refdomain_has_snapshot_relationship_attr(self):
        """CommonCrawlRefDomain should have snapshot relationship attribute."""
        assert hasattr(CommonCrawlRefDomain, "snapshot")

    def test_anchor_has_snapshot_relationship_attr(self):
        """CommonCrawlAnchor should have snapshot relationship attribute."""
        assert hasattr(CommonCrawlAnchor, "snapshot")

    def test_snapshot_has_edges_relationship_attr(self):
        """CommonCrawlSnapshot should have edges relationship attribute."""
        assert hasattr(CommonCrawlSnapshot, "edges")

    def test_snapshot_has_refdomains_relationship_attr(self):
        """CommonCrawlSnapshot should have refdomains relationship attribute."""
        assert hasattr(CommonCrawlSnapshot, "refdomains")

    def test_snapshot_has_anchors_relationship_attr(self):
        """CommonCrawlSnapshot should have anchors relationship attribute."""
        assert hasattr(CommonCrawlSnapshot, "anchors")


# =============================================================================
# Table and Column Tests (Design Verification)
# =============================================================================


class TestCommonCrawlTableDesign:
    """Tests verifying table names and key design decisions."""

    def test_snapshot_table_name(self):
        """CommonCrawlSnapshot should use correct table name."""
        assert CommonCrawlSnapshot.__tablename__ == "commoncrawl_snapshots"

    def test_edge_table_name(self):
        """CommonCrawlEdge should use correct table name."""
        assert CommonCrawlEdge.__tablename__ == "commoncrawl_edges"

    def test_refdomain_table_name(self):
        """CommonCrawlRefDomain should use correct table name."""
        assert CommonCrawlRefDomain.__tablename__ == "commoncrawl_refdomains"

    def test_anchor_table_name(self):
        """CommonCrawlAnchor should use correct table name."""
        assert CommonCrawlAnchor.__tablename__ == "commoncrawl_anchors"
