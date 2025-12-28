"""
Tests for crawl infrastructure models.

Following TDD: These tests are written FIRST, then the implementation.

Tests cover:
- CrawlRun: Track crawl jobs
- CrawlPage: Per-page crawl results
- LinkEdge: Internal link graph
- IssueType: Issue taxonomy (seeded)
- IssueInstance: Per-page issues

Note: Tests that require database operations are marked with pytest.mark.db
and require a PostgreSQL database to run (SQLite doesn't support JSONB/ARRAY).
"""

import uuid
from decimal import Decimal

from semrush_core.models.crawl_page import CrawlPage, RenderMode
from semrush_core.models.crawl_run import CrawlRun, CrawlStatus
from semrush_core.models.issue_instance import IssueInstance
from semrush_core.models.issue_type import IssueCategory, IssueType
from semrush_core.models.link_edge import LinkEdge, LinkType

# =============================================================================
# CrawlRun Tests
# =============================================================================

class TestCrawlRunModel:
    """Tests for the CrawlRun model."""

    def test_crawl_run_has_required_fields(self):
        """CrawlRun should have all required fields."""
        project_id = uuid.uuid4()
        crawl_run = CrawlRun(
            project_id=project_id,
            config_snapshot={"max_pages": 100, "render_budget": 50},
            status=CrawlStatus.QUEUED.value,
        )

        assert crawl_run.project_id == project_id
        assert crawl_run.status == CrawlStatus.QUEUED.value
        assert crawl_run.config_snapshot == {"max_pages": 100, "render_budget": 50}

    def test_crawl_run_status_column_default(self):
        """CrawlRun status column should have 'queued' as default (DB-level)."""
        # Note: The default is applied at DB level (server_default in migration)
        # In-memory objects won't have this default automatically applied
        # This test verifies the column exists and the enum is valid
        assert CrawlStatus.QUEUED.value == "queued"
        assert hasattr(CrawlRun, "status")

    def test_crawl_run_accepts_site_id(self):
        """CrawlRun should accept an optional site_id."""
        site_id = uuid.uuid4()
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            site_id=site_id,
            config_snapshot={},
        )
        assert crawl_run.site_id == site_id

    def test_crawl_run_status_enum_values(self):
        """CrawlStatus enum should have all expected values."""
        expected_statuses = [
            "queued", "running", "html_complete", "selecting_js",
            "rendering_js", "analyzing", "completed", "failed"
        ]
        actual_statuses = [s.value for s in CrawlStatus]
        assert sorted(actual_statuses) == sorted(expected_statuses)

    def test_crawl_run_has_timing_fields(self):
        """CrawlRun should have timestamp tracking fields."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
        )

        # Verify fields exist (initially None)
        assert hasattr(crawl_run, "started_at")
        assert hasattr(crawl_run, "html_completed_at")
        assert hasattr(crawl_run, "js_completed_at")
        assert hasattr(crawl_run, "completed_at")
        assert hasattr(crawl_run, "created_at")

    def test_crawl_run_stats_defaults_to_none(self):
        """CrawlRun stats should default to None."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
        )
        assert crawl_run.stats is None

    def test_crawl_run_has_error_message_field(self):
        """CrawlRun should have an error_message field."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
            error_message="Test error",
        )
        assert crawl_run.error_message == "Test error"

    def test_crawl_run_config_snapshot_stores_dict(self):
        """CrawlRun config_snapshot should store dict data."""
        config = {
            "max_pages": 1000,
            "render_budget": 100,
            "crawl_settings": {
                "respect_robots": True,
                "user_agent": "Openahrush/1.0",
            },
            "rules": [
                {"type": "exclude", "pattern": "/admin/*"},
            ],
        }
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot=config,
        )
        assert crawl_run.config_snapshot["max_pages"] == 1000
        assert crawl_run.config_snapshot["crawl_settings"]["respect_robots"] is True


class TestCrawlRunMethods:
    """Tests for CrawlRun helper methods."""

    def test_is_active_for_queued_status(self):
        """is_active should return True for queued status."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
            status=CrawlStatus.QUEUED.value,
        )
        assert crawl_run.is_active is True

    def test_is_active_for_running_status(self):
        """is_active should return True for running status."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
            status=CrawlStatus.RUNNING.value,
        )
        assert crawl_run.is_active is True

    def test_is_active_for_completed_status(self):
        """is_active should return False for completed status."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
            status=CrawlStatus.COMPLETED.value,
        )
        assert crawl_run.is_active is False

    def test_is_completed_for_completed_status(self):
        """is_completed should return True for completed status."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
            status=CrawlStatus.COMPLETED.value,
        )
        assert crawl_run.is_completed is True

    def test_is_failed_for_failed_status(self):
        """is_failed should return True for failed status."""
        crawl_run = CrawlRun(
            project_id=uuid.uuid4(),
            config_snapshot={},
            status=CrawlStatus.FAILED.value,
        )
        assert crawl_run.is_failed is True


# =============================================================================
# CrawlPage Tests
# =============================================================================

class TestCrawlPageModel:
    """Tests for the CrawlPage model."""

    def test_crawl_page_has_required_fields(self):
        """CrawlPage should have all required fields."""
        crawl_run_id = uuid.uuid4()
        page = CrawlPage(
            crawl_run_id=crawl_run_id,
            url="https://example.com/page",
        )

        assert page.crawl_run_id == crawl_run_id
        assert page.url == "https://example.com/page"

    def test_crawl_page_has_response_fields(self):
        """CrawlPage should have HTTP response fields."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            status_code=200,
            content_type="text/html",
            response_time_ms=150,
        )

        assert page.status_code == 200
        assert page.content_type == "text/html"
        assert page.response_time_ms == 150

    def test_crawl_page_has_final_url(self):
        """CrawlPage should track final URL after redirects."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/old",
            final_url="https://example.com/new",
        )
        assert page.final_url == "https://example.com/new"

    def test_crawl_page_render_mode_enum(self):
        """RenderMode enum should have expected values."""
        assert RenderMode.HTML.value == "html"
        assert RenderMode.JS.value == "js"

    def test_crawl_page_has_extracted_seo_fields(self):
        """CrawlPage should have SEO-related extracted fields."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            title="Test Page Title",
            meta_description="This is a test description",
            canonical_url="https://example.com/",
            meta_robots="index, follow",
            h1_count=1,
            first_h1="Welcome to Test",
            word_count=500,
            text_length=2500,
        )

        assert page.title == "Test Page Title"
        assert page.meta_description == "This is a test description"
        assert page.canonical_url == "https://example.com/"
        assert page.meta_robots == "index, follow"
        assert page.h1_count == 1
        assert page.first_h1 == "Welcome to Test"
        assert page.word_count == 500
        assert page.text_length == 2500

    def test_crawl_page_has_hash_fields(self):
        """CrawlPage should have content hash fields."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            html_hash="abc123hash",
            rendered_hash="def456hash",
            content_hash="ghi789hash",
        )

        assert page.html_hash == "abc123hash"
        assert page.rendered_hash == "def456hash"
        assert page.content_hash == "ghi789hash"

    def test_crawl_page_has_artifact_keys(self):
        """CrawlPage should have S3/MinIO artifact keys."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            html_artifact_key="crawls/123/pages/456/html.gz",
            rendered_artifact_key="crawls/123/pages/456/rendered.gz",
        )

        assert page.html_artifact_key == "crawls/123/pages/456/html.gz"
        assert page.rendered_artifact_key == "crawls/123/pages/456/rendered.gz"

    def test_crawl_page_has_render_tracking(self):
        """CrawlPage should track rendering status."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            was_rendered=True,
            render_trigger="content_hash_mismatch",
            render_mode=RenderMode.JS.value,
        )

        assert page.was_rendered is True
        assert page.render_trigger == "content_hash_mismatch"
        assert page.render_mode == "js"


class TestCrawlPageMethods:
    """Tests for CrawlPage helper methods."""

    def test_is_success_for_200_status(self):
        """is_success should return True for 200 status codes."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            status_code=200,
        )
        assert page.is_success is True

    def test_is_success_for_201_status(self):
        """is_success should return True for 2xx status codes."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            status_code=201,
        )
        assert page.is_success is True

    def test_is_redirect_for_301_status(self):
        """is_redirect should return True for 3xx status codes."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/old",
            status_code=301,
        )
        assert page.is_redirect is True

    def test_is_client_error_for_404_status(self):
        """is_client_error should return True for 4xx status codes."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/missing",
            status_code=404,
        )
        assert page.is_client_error is True

    def test_is_server_error_for_500_status(self):
        """is_server_error should return True for 5xx status codes."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/error",
            status_code=500,
        )
        assert page.is_server_error is True

    def test_was_js_rendered_when_mode_is_js(self):
        """was_js_rendered should return True when render_mode is 'js'."""
        page = CrawlPage(
            crawl_run_id=uuid.uuid4(),
            url="https://example.com/",
            render_mode=RenderMode.JS.value,
        )
        assert page.was_js_rendered is True


# =============================================================================
# LinkEdge Tests
# =============================================================================

class TestLinkEdgeModel:
    """Tests for the LinkEdge model."""

    def test_link_edge_has_required_fields(self):
        """LinkEdge should have all required fields."""
        crawl_run_id = uuid.uuid4()
        edge = LinkEdge(
            crawl_run_id=crawl_run_id,
            source_url="https://example.com/page1",
            target_url="https://example.com/page2",
            is_internal=True,
        )

        assert edge.crawl_run_id == crawl_run_id
        assert edge.source_url == "https://example.com/page1"
        assert edge.target_url == "https://example.com/page2"
        assert edge.is_internal is True

    def test_link_edge_has_anchor_text(self):
        """LinkEdge should store anchor text."""
        edge = LinkEdge(
            crawl_run_id=uuid.uuid4(),
            source_url="https://example.com/page1",
            target_url="https://example.com/page2",
            is_internal=True,
            anchor_text="Click here for more",
        )
        assert edge.anchor_text == "Click here for more"

    def test_link_type_enum_values(self):
        """LinkType enum should have expected values."""
        expected_types = ["a", "canonical", "redirect", "img", "script"]
        actual_types = [t.value for t in LinkType]
        assert sorted(actual_types) == sorted(expected_types)

    def test_link_edge_has_link_type(self):
        """LinkEdge should have link_type field."""
        edge = LinkEdge(
            crawl_run_id=uuid.uuid4(),
            source_url="https://example.com/",
            target_url="https://example.com/canonical",
            is_internal=True,
            link_type=LinkType.CANONICAL.value,
        )
        assert edge.link_type == "canonical"

    def test_link_edge_has_rel_flags(self):
        """LinkEdge should have rel_flags array."""
        edge = LinkEdge(
            crawl_run_id=uuid.uuid4(),
            source_url="https://example.com/",
            target_url="https://external.com/",
            is_internal=False,
            rel_flags=["nofollow", "noopener"],
        )
        assert edge.rel_flags == ["nofollow", "noopener"]

    def test_link_edge_has_broken_link_tracking(self):
        """LinkEdge should track broken links."""
        edge = LinkEdge(
            crawl_run_id=uuid.uuid4(),
            source_url="https://example.com/page",
            target_url="https://example.com/missing",
            is_internal=True,
            is_broken=True,
            target_status_code=404,
        )

        assert edge.is_broken is True
        assert edge.target_status_code == 404


class TestLinkEdgeMethods:
    """Tests for LinkEdge helper methods."""

    def test_is_nofollow(self):
        """is_nofollow should check rel_flags for nofollow."""
        edge = LinkEdge(
            crawl_run_id=uuid.uuid4(),
            source_url="https://example.com/",
            target_url="https://external.com/",
            is_internal=False,
            rel_flags=["nofollow"],
        )
        assert edge.is_nofollow is True

    def test_is_dofollow_when_no_flags(self):
        """is_dofollow should return True when no rel_flags."""
        edge = LinkEdge(
            crawl_run_id=uuid.uuid4(),
            source_url="https://example.com/a",
            target_url="https://example.com/b",
            is_internal=True,
        )
        assert edge.is_dofollow is True


# =============================================================================
# IssueType Tests
# =============================================================================

class TestIssueTypeModel:
    """Tests for the IssueType model."""

    def test_issue_type_has_required_fields(self):
        """IssueType should have all required fields."""
        issue_type = IssueType(
            id="missing_title",
            category=IssueCategory.CONTENT.value,
            severity=3,
            name="Missing Title Tag",
            description="Page is missing a <title> tag",
            recommendation="Add a descriptive title tag between 50-60 characters",
        )

        assert issue_type.id == "missing_title"
        assert issue_type.category == "content"
        assert issue_type.severity == 3
        assert issue_type.name == "Missing Title Tag"

    def test_issue_category_enum_values(self):
        """IssueCategory enum should have expected values."""
        expected_categories = ["content", "technical", "links", "indexability"]
        actual_categories = [c.value for c in IssueCategory]
        assert sorted(actual_categories) == sorted(expected_categories)

    def test_issue_type_severity_properties(self):
        """IssueType severity properties should work correctly."""
        critical = IssueType(id="c", category="technical", severity=5, name="C")
        high = IssueType(id="h", category="technical", severity=4, name="H")
        medium = IssueType(id="m", category="technical", severity=3, name="M")
        low = IssueType(id="l", category="technical", severity=2, name="L")
        info = IssueType(id="i", category="technical", severity=1, name="I")

        assert critical.is_critical is True
        assert high.is_high is True
        assert medium.is_medium is True
        assert low.is_low is True
        assert info.is_info is True


# =============================================================================
# IssueInstance Tests
# =============================================================================

class TestIssueInstanceModel:
    """Tests for the IssueInstance model."""

    def test_issue_instance_has_required_fields(self):
        """IssueInstance should have all required fields."""
        crawl_run_id = uuid.uuid4()
        crawl_page_id = uuid.uuid4()
        issue = IssueInstance(
            crawl_run_id=crawl_run_id,
            crawl_page_id=crawl_page_id,
            issue_type_id="missing_title",
            affected_url="https://example.com/page",
        )

        assert issue.crawl_run_id == crawl_run_id
        assert issue.crawl_page_id == crawl_page_id
        assert issue.issue_type_id == "missing_title"
        assert issue.affected_url == "https://example.com/page"

    def test_issue_instance_has_confidence_score(self):
        """IssueInstance should have confidence score."""
        issue = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="duplicate_title",
            affected_url="https://example.com/",
            confidence=Decimal("0.950"),
        )
        assert issue.confidence == Decimal("0.950")

    def test_issue_instance_has_impact_score(self):
        """IssueInstance should have impact score."""
        issue = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="missing_meta_description",
            affected_url="https://example.com/",
            impact_score=Decimal("75.50"),
        )
        assert issue.impact_score == Decimal("75.50")

    def test_issue_instance_has_evidence_dict(self):
        """IssueInstance should store evidence as dict."""
        evidence = {
            "current_title": "Home",
            "title_length": 4,
            "recommended_min": 30,
            "recommended_max": 60,
        }
        issue = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="short_title",
            affected_url="https://example.com/",
            evidence=evidence,
        )
        assert issue.evidence["current_title"] == "Home"
        assert issue.evidence["title_length"] == 4

    def test_issue_instance_is_high_confidence(self):
        """is_high_confidence should return True for >= 0.9."""
        high = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="test",
            affected_url="https://example.com/",
            confidence=Decimal("0.950"),
        )
        low = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="test",
            affected_url="https://example.com/",
            confidence=Decimal("0.500"),
        )

        assert high.is_high_confidence is True
        assert low.is_high_confidence is False

    def test_issue_instance_is_high_impact(self):
        """is_high_impact should return True for >= 75."""
        high = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="test",
            affected_url="https://example.com/",
            impact_score=Decimal("80.00"),
        )
        low = IssueInstance(
            crawl_run_id=uuid.uuid4(),
            crawl_page_id=uuid.uuid4(),
            issue_type_id="test",
            affected_url="https://example.com/",
            impact_score=Decimal("50.00"),
        )

        assert high.is_high_impact is True
        assert low.is_high_impact is False


# =============================================================================
# Relationship Tests (require real FK in PostgreSQL)
# =============================================================================

class TestModelRelationships:
    """Tests for model relationships - primarily documentation/design verification."""

    def test_crawl_run_pages_relationship_defined(self):
        """CrawlRun should have pages relationship."""
        assert hasattr(CrawlRun, "pages")

    def test_crawl_run_link_edges_relationship_defined(self):
        """CrawlRun should have link_edges relationship."""
        assert hasattr(CrawlRun, "link_edges")

    def test_crawl_run_issue_instances_relationship_defined(self):
        """CrawlRun should have issue_instances relationship."""
        assert hasattr(CrawlRun, "issue_instances")

    def test_crawl_page_crawl_run_relationship_defined(self):
        """CrawlPage should have crawl_run relationship."""
        assert hasattr(CrawlPage, "crawl_run")

    def test_crawl_page_issues_relationship_defined(self):
        """CrawlPage should have issues relationship."""
        assert hasattr(CrawlPage, "issues")

    def test_link_edge_crawl_run_relationship_defined(self):
        """LinkEdge should have crawl_run relationship."""
        assert hasattr(LinkEdge, "crawl_run")

    def test_issue_instance_issue_type_relationship_defined(self):
        """IssueInstance should have issue_type relationship."""
        assert hasattr(IssueInstance, "issue_type")

    def test_issue_instance_crawl_page_relationship_defined(self):
        """IssueInstance should have crawl_page relationship."""
        assert hasattr(IssueInstance, "crawl_page")
