"""
Tests for the Rules Engine.

Tests cover:
- Engine initialization with default and custom rules
- Page analysis with multiple rules
- Duplicate title detection
- Broken link detection
- Orphan page detection
- Event payload generation
"""

from __future__ import annotations

import uuid

from semrush_workers.rules.engine import AnalysisResult, RuleDefinition, RulesEngine
from semrush_workers.rules.models import (
    CrawlPage,
    DiscoverySource,
    IssueSeverity,
    LinkEdge,
)


def make_page(
    url: str = "https://example.com/page",
    status_code: int = 200,
    title: str | None = "Test Page Title That Is Long Enough",
    meta_description: str | None = "A test meta description that is long enough for the rules.",
    canonical_url: str | None = None,
    h1_tags: list[str] | None = None,
    word_count: int = 500,
    discovery_source: DiscoverySource = DiscoverySource.INTERNAL_LINK,
) -> CrawlPage:
    """Create a test page with default values."""
    return CrawlPage(
        id=uuid.uuid4(),
        crawl_run_id=uuid.uuid4(),
        url=url,
        status_code=status_code,
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url or url,  # Self-canonical by default
        h1_tags=h1_tags or ["Main Heading"],
        word_count=word_count,
        discovery_source=discovery_source,
    )


def make_edge(
    source_url: str = "https://example.com/page",
    target_url: str = "https://example.com/target",
    is_internal: bool = True,
    target_status_code: int | None = None,
) -> LinkEdge:
    """Create a test link edge."""
    return LinkEdge(
        id=uuid.uuid4(),
        crawl_run_id=uuid.uuid4(),
        source_url=source_url,
        target_url=target_url,
        is_internal=is_internal,
        target_status_code=target_status_code,
    )


class TestRulesEngineInitialization:
    """Tests for RulesEngine initialization."""

    def test_default_rules_loaded(self) -> None:
        """Engine loads default rules when none provided."""
        engine = RulesEngine()

        assert len(engine.rules) > 0
        rule_ids = [r.rule_id for r in engine.rules]
        assert "server_error_5xx" in rule_ids
        assert "missing_title" in rule_ids
        assert "thin_content" in rule_ids

    def test_custom_rules(self) -> None:
        """Engine uses custom rules when provided."""
        from semrush_workers.rules import evaluators

        custom_rules = [
            RuleDefinition(
                rule_id="test_rule",
                name="Test Rule",
                severity=IssueSeverity.LOW,
                evaluator=evaluators.rule_server_error_5xx,
            )
        ]
        engine = RulesEngine(rules=custom_rules)

        assert len(engine.rules) == 1
        assert engine.rules[0].rule_id == "test_rule"

    def test_enabled_rule_ids_filter(self) -> None:
        """Only specified rules are enabled."""
        engine = RulesEngine(enabled_rule_ids=["server_error_5xx", "missing_title"])

        enabled_rules = [r for r in engine.rules if r.enabled]
        assert len(enabled_rules) == 2
        assert all(r.rule_id in ["server_error_5xx", "missing_title"] for r in enabled_rules)


class TestRulesEngineAnalysis:
    """Tests for RulesEngine.analyze()."""

    def test_analyze_clean_page(self) -> None:
        """Clean page should have minimal issues."""
        engine = RulesEngine()
        crawl_run_id = uuid.uuid4()

        # Create a page that passes all rules
        page = make_page()

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=[page],
            site_domain="example.com",
            site_scheme="https",
        )

        # Should have very few issues (maybe thin content if word count low)
        assert result.pages_analyzed == 1
        assert result.duration_ms >= 0

    def test_analyze_page_with_5xx(self) -> None:
        """Page with 5xx should be detected."""
        engine = RulesEngine(enabled_rule_ids=["server_error_5xx"])
        crawl_run_id = uuid.uuid4()

        page = make_page(status_code=500)

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=[page],
        )

        assert result.issues_found == 1
        assert result.issues_by_type.get("server_error_5xx") == 1
        assert result.issues_by_severity.get(5) == 1

    def test_analyze_multiple_pages(self) -> None:
        """Multiple pages should all be analyzed."""
        engine = RulesEngine(enabled_rule_ids=["missing_title"])
        crawl_run_id = uuid.uuid4()

        pages = [
            make_page(url="https://example.com/1", title="Title 1 that is long enough"),
            make_page(url="https://example.com/2", title=None),  # Missing title
            make_page(url="https://example.com/3", title=""),  # Empty title
        ]

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=pages,
        )

        assert result.pages_analyzed == 3
        assert result.issues_by_type.get("missing_title") == 2


class TestDuplicateTitleDetection:
    """Tests for duplicate title detection."""

    def test_detect_duplicate_titles(self) -> None:
        """Duplicate titles should be detected."""
        engine = RulesEngine(enabled_rule_ids=[])  # Disable all page rules
        crawl_run_id = uuid.uuid4()

        pages = [
            make_page(url="https://example.com/1", title="Duplicate Title"),
            make_page(url="https://example.com/2", title="Duplicate Title"),
            make_page(url="https://example.com/3", title="Unique Title"),
        ]

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=pages,
        )

        assert result.issues_by_type.get("duplicate_title") == 2

    def test_no_duplicates_with_unique_titles(self) -> None:
        """Unique titles should not trigger duplicate detection."""
        engine = RulesEngine(enabled_rule_ids=[])
        crawl_run_id = uuid.uuid4()

        pages = [
            make_page(url="https://example.com/1", title="Title One"),
            make_page(url="https://example.com/2", title="Title Two"),
        ]

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=pages,
        )

        assert result.issues_by_type.get("duplicate_title", 0) == 0


class TestBrokenLinkDetection:
    """Tests for broken link detection in engine."""

    def test_detect_broken_internal_links(self) -> None:
        """Broken internal links should be detected."""
        engine = RulesEngine(enabled_rule_ids=[])
        crawl_run_id = uuid.uuid4()

        edges = [
            make_edge(
                source_url="https://example.com/page",
                target_url="https://example.com/broken",
                is_internal=True,
                target_status_code=404,
            ),
            make_edge(
                source_url="https://example.com/page",
                target_url="https://example.com/good",
                is_internal=True,
                target_status_code=200,
            ),
        ]

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=[],
            edges=edges,
        )

        assert result.issues_by_type.get("broken_internal_link") == 1

    def test_broken_links_deduplicated(self) -> None:
        """Multiple edges to same broken target should create one issue."""
        engine = RulesEngine(enabled_rule_ids=[])
        crawl_run_id = uuid.uuid4()

        edges = [
            make_edge(
                source_url="https://example.com/page1",
                target_url="https://example.com/broken",
                is_internal=True,
                target_status_code=404,
            ),
            make_edge(
                source_url="https://example.com/page2",
                target_url="https://example.com/broken",
                is_internal=True,
                target_status_code=404,
            ),
        ]

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=[],
            edges=edges,
        )

        assert result.issues_by_type.get("broken_internal_link") == 1


class TestOrphanPageDetection:
    """Tests for orphan page detection in engine."""

    def test_detect_orphan_pages(self) -> None:
        """Sitemap pages without internal links should be detected."""
        engine = RulesEngine(enabled_rule_ids=[])
        crawl_run_id = uuid.uuid4()

        pages = [
            make_page(
                url="https://example.com/orphan",
                discovery_source=DiscoverySource.SITEMAP,
            ),
        ]
        edges: list[LinkEdge] = []  # No links to the page

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=pages,
            edges=edges,
        )

        assert result.issues_by_type.get("orphan_page") == 1

    def test_no_orphan_when_linked(self) -> None:
        """Sitemap page with internal link should not be orphan."""
        engine = RulesEngine(enabled_rule_ids=[])
        crawl_run_id = uuid.uuid4()

        pages = [
            make_page(
                url="https://example.com/linked",
                discovery_source=DiscoverySource.SITEMAP,
            ),
        ]
        edges = [
            make_edge(
                source_url="https://example.com/home",
                target_url="https://example.com/linked",
                is_internal=True,
            ),
        ]

        _issues, result = engine.analyze(
            crawl_run_id=crawl_run_id,
            pages=pages,
            edges=edges,
        )

        assert result.issues_by_type.get("orphan_page", 0) == 0


class TestEventPayload:
    """Tests for event payload generation."""

    def test_event_payload_structure(self) -> None:
        """Event payload should have correct structure."""
        engine = RulesEngine()
        crawl_run_id = uuid.uuid4()
        project_id = uuid.uuid4()
        result = AnalysisResult(
            issues_found=5,
            issues_by_severity={4: 2, 3: 3},
            issues_by_type={"missing_title": 2, "title_too_short": 3},
            pages_analyzed=10,
            duration_ms=100,
        )

        payload = engine.get_event_payload(
            crawl_run_id=crawl_run_id,
            project_id=project_id,
            result=result,
        )

        assert payload["event_type"] == "rules.completed"
        assert payload["project_id"] == str(project_id)
        assert "event_id" in payload
        assert "occurred_at" in payload
        assert "trace_id" in payload
        assert payload["payload"]["crawl_run_id"] == str(crawl_run_id)
        assert payload["payload"]["issues_found"] == 5


class TestAnalysisResult:
    """Tests for AnalysisResult."""

    def test_to_dict(self) -> None:
        """AnalysisResult should serialize to dict."""
        result = AnalysisResult(
            issues_found=10,
            issues_by_severity={5: 2, 4: 3, 3: 5},
            issues_by_type={"missing_title": 3, "server_error_5xx": 2},
            pages_analyzed=100,
            duration_ms=500,
        )

        d = result.to_dict()

        assert d["issues_found"] == 10
        assert d["pages_analyzed"] == 100
        assert d["duration_ms"] == 500
        assert d["issues_by_severity"] == {5: 2, 4: 3, 3: 5}
