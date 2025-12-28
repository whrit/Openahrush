"""
Tests for rule evaluators.

Each test covers a specific SEO rule with various edge cases.
Tests are organized by severity level.
"""

from __future__ import annotations

import uuid

from semrush_workers.rules.models import CrawlPage, DiscoverySource, LinkEdge


# Helper to create test pages
def make_page(
    url: str = "https://example.com/page",
    status_code: int = 200,
    title: str | None = "Test Page Title",
    meta_description: str | None = "A test meta description for this page.",
    canonical_url: str | None = None,
    h1_tags: list[str] | None = None,
    word_count: int = 500,
    discovery_source: DiscoverySource = DiscoverySource.INTERNAL_LINK,
    redirect_chain: list[str] | None = None,
    mixed_content_urls: list[str] | None = None,
) -> CrawlPage:
    """Create a test page with default values."""
    return CrawlPage(
        id=uuid.uuid4(),
        crawl_run_id=uuid.uuid4(),
        url=url,
        status_code=status_code,
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        h1_tags=h1_tags or [],
        word_count=word_count,
        discovery_source=discovery_source,
        redirect_chain=redirect_chain or [],
        mixed_content_urls=mixed_content_urls or [],
    )


def make_edge(
    source_url: str = "https://example.com/page",
    target_url: str = "https://example.com/target",
    is_internal: bool = True,
    target_status_code: int | None = None,
) -> LinkEdge:
    """Create a test link edge with default values."""
    return LinkEdge(
        id=uuid.uuid4(),
        crawl_run_id=uuid.uuid4(),
        source_url=source_url,
        target_url=target_url,
        is_internal=is_internal,
        target_status_code=target_status_code,
    )


# =============================================================================
# Critical Severity Tests (severity=5)
# =============================================================================


class TestRuleServerError5xx:
    """Tests for rule_server_error_5xx."""

    def test_applies_to_500(self) -> None:
        """500 Internal Server Error should trigger the rule."""
        from semrush_workers.rules.evaluators import rule_server_error_5xx

        page = make_page(status_code=500)
        result = rule_server_error_5xx(page)

        assert result.applies is True
        assert result.confidence == 1.0
        assert result.evidence["status_code"] == 500

    def test_applies_to_502(self) -> None:
        """502 Bad Gateway should trigger the rule."""
        from semrush_workers.rules.evaluators import rule_server_error_5xx

        page = make_page(status_code=502)
        result = rule_server_error_5xx(page)

        assert result.applies is True
        assert result.evidence["status_code"] == 502

    def test_applies_to_503(self) -> None:
        """503 Service Unavailable should trigger the rule."""
        from semrush_workers.rules.evaluators import rule_server_error_5xx

        page = make_page(status_code=503)
        result = rule_server_error_5xx(page)

        assert result.applies is True

    def test_not_applies_to_200(self) -> None:
        """200 OK should not trigger the rule."""
        from semrush_workers.rules.evaluators import rule_server_error_5xx

        page = make_page(status_code=200)
        result = rule_server_error_5xx(page)

        assert result.applies is False
        assert result.confidence == 0.0

    def test_not_applies_to_404(self) -> None:
        """404 Not Found should not trigger the rule (that's 4xx)."""
        from semrush_workers.rules.evaluators import rule_server_error_5xx

        page = make_page(status_code=404)
        result = rule_server_error_5xx(page)

        assert result.applies is False


class TestRuleRedirectLoop:
    """Tests for rule_redirect_loop."""

    def test_applies_when_loop_detected(self) -> None:
        """Redirect chain containing the same URL twice should trigger."""
        from semrush_workers.rules.evaluators import rule_redirect_loop

        page = make_page(
            url="https://example.com/a",
            status_code=301,
            redirect_chain=[
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/a",  # Loop back to start
            ],
        )
        result = rule_redirect_loop(page)

        assert result.applies is True
        assert result.confidence == 1.0
        assert "loop_url" in result.evidence

    def test_not_applies_clean_chain(self) -> None:
        """Clean redirect chain should not trigger."""
        from semrush_workers.rules.evaluators import rule_redirect_loop

        page = make_page(
            url="https://example.com/a",
            status_code=301,
            redirect_chain=[
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
            ],
        )
        result = rule_redirect_loop(page)

        assert result.applies is False

    def test_not_applies_no_redirect(self) -> None:
        """Non-redirect page should not trigger."""
        from semrush_workers.rules.evaluators import rule_redirect_loop

        page = make_page(status_code=200, redirect_chain=[])
        result = rule_redirect_loop(page)

        assert result.applies is False


class TestRuleRedirectChainLong:
    """Tests for rule_redirect_chain_long."""

    def test_applies_chain_4_hops(self) -> None:
        """Redirect chain with 4 hops (>3) should trigger."""
        from semrush_workers.rules.evaluators import rule_redirect_chain_long

        page = make_page(
            status_code=301,
            redirect_chain=[
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
                "https://example.com/4",
                "https://example.com/final",
            ],
        )
        result = rule_redirect_chain_long(page)

        assert result.applies is True
        assert result.evidence["chain_length"] == 5
        assert result.evidence["max_allowed"] == 3

    def test_not_applies_chain_3_hops(self) -> None:
        """Redirect chain with exactly 3 hops should not trigger."""
        from semrush_workers.rules.evaluators import rule_redirect_chain_long

        page = make_page(
            status_code=301,
            redirect_chain=[
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/final",
            ],
        )
        result = rule_redirect_chain_long(page)

        assert result.applies is False

    def test_not_applies_no_redirect(self) -> None:
        """Non-redirect page should not trigger."""
        from semrush_workers.rules.evaluators import rule_redirect_chain_long

        page = make_page(status_code=200, redirect_chain=[])
        result = rule_redirect_chain_long(page)

        assert result.applies is False


class TestRuleBrokenInternalLink:
    """Tests for rule_broken_internal_link."""

    def test_applies_link_to_404(self) -> None:
        """Internal link to 404 page should trigger."""
        from semrush_workers.rules.evaluators import rule_broken_internal_link

        page = make_page(url="https://example.com/page")
        edges = [
            make_edge(
                source_url="https://example.com/page",
                target_url="https://example.com/broken",
                is_internal=True,
                target_status_code=404,
            )
        ]
        result = rule_broken_internal_link(page, edges)

        assert result.applies is True
        assert len(result.evidence["broken_links"]) == 1
        assert result.evidence["broken_links"][0]["target_url"] == "https://example.com/broken"

    def test_applies_link_to_500(self) -> None:
        """Internal link to 500 page should trigger."""
        from semrush_workers.rules.evaluators import rule_broken_internal_link

        page = make_page(url="https://example.com/page")
        edges = [
            make_edge(
                source_url="https://example.com/page",
                target_url="https://example.com/error",
                is_internal=True,
                target_status_code=500,
            )
        ]
        result = rule_broken_internal_link(page, edges)

        assert result.applies is True

    def test_not_applies_all_good_links(self) -> None:
        """All 200 links should not trigger."""
        from semrush_workers.rules.evaluators import rule_broken_internal_link

        page = make_page(url="https://example.com/page")
        edges = [
            make_edge(
                source_url="https://example.com/page",
                target_url="https://example.com/good",
                is_internal=True,
                target_status_code=200,
            )
        ]
        result = rule_broken_internal_link(page, edges)

        assert result.applies is False

    def test_not_applies_external_broken_link(self) -> None:
        """External broken links should not trigger (internal only)."""
        from semrush_workers.rules.evaluators import rule_broken_internal_link

        page = make_page(url="https://example.com/page")
        edges = [
            make_edge(
                source_url="https://example.com/page",
                target_url="https://external.com/broken",
                is_internal=False,
                target_status_code=404,
            )
        ]
        result = rule_broken_internal_link(page, edges)

        assert result.applies is False


# =============================================================================
# High Severity Tests (severity=4)
# =============================================================================


class TestRuleInternal4xx:
    """Tests for rule_internal_4xx."""

    def test_applies_to_404(self) -> None:
        """404 Not Found should trigger."""
        from semrush_workers.rules.evaluators import rule_internal_4xx

        page = make_page(status_code=404)
        result = rule_internal_4xx(page)

        assert result.applies is True
        assert result.evidence["status_code"] == 404

    def test_applies_to_403(self) -> None:
        """403 Forbidden should trigger."""
        from semrush_workers.rules.evaluators import rule_internal_4xx

        page = make_page(status_code=403)
        result = rule_internal_4xx(page)

        assert result.applies is True

    def test_not_applies_to_200(self) -> None:
        """200 OK should not trigger."""
        from semrush_workers.rules.evaluators import rule_internal_4xx

        page = make_page(status_code=200)
        result = rule_internal_4xx(page)

        assert result.applies is False

    def test_not_applies_to_500(self) -> None:
        """500 should not trigger (that's 5xx)."""
        from semrush_workers.rules.evaluators import rule_internal_4xx

        page = make_page(status_code=500)
        result = rule_internal_4xx(page)

        assert result.applies is False


class TestRuleMissingTitle:
    """Tests for rule_missing_title."""

    def test_applies_no_title(self) -> None:
        """Page with no title should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_title

        page = make_page(title=None)
        result = rule_missing_title(page)

        assert result.applies is True
        assert result.confidence == 1.0

    def test_applies_empty_title(self) -> None:
        """Page with empty title should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_title

        page = make_page(title="")
        result = rule_missing_title(page)

        assert result.applies is True

    def test_applies_whitespace_title(self) -> None:
        """Page with whitespace-only title should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_title

        page = make_page(title="   ")
        result = rule_missing_title(page)

        assert result.applies is True

    def test_not_applies_valid_title(self) -> None:
        """Page with valid title should not trigger."""
        from semrush_workers.rules.evaluators import rule_missing_title

        page = make_page(title="Valid Page Title")
        result = rule_missing_title(page)

        assert result.applies is False


class TestRuleDuplicateTitle:
    """Tests for rule_duplicate_title."""

    def test_applies_duplicate_found(self) -> None:
        """Page with duplicate title should trigger."""
        from semrush_workers.rules.evaluators import rule_duplicate_title

        page = make_page(url="https://example.com/page1", title="Duplicate Title")
        other_pages = [
            make_page(url="https://example.com/page2", title="Duplicate Title"),
            make_page(url="https://example.com/page3", title="Unique Title"),
        ]
        result = rule_duplicate_title(page, other_pages)

        assert result.applies is True
        assert "https://example.com/page2" in result.evidence["duplicate_urls"]

    def test_not_applies_unique_title(self) -> None:
        """Page with unique title should not trigger."""
        from semrush_workers.rules.evaluators import rule_duplicate_title

        page = make_page(url="https://example.com/page1", title="Unique Title")
        other_pages = [
            make_page(url="https://example.com/page2", title="Different Title"),
        ]
        result = rule_duplicate_title(page, other_pages)

        assert result.applies is False

    def test_not_applies_empty_titles(self) -> None:
        """Empty titles should not be considered duplicates."""
        from semrush_workers.rules.evaluators import rule_duplicate_title

        page = make_page(title=None)
        other_pages = [make_page(title=None)]
        result = rule_duplicate_title(page, other_pages)

        assert result.applies is False


class TestRuleCanonicalWrongDomain:
    """Tests for rule_canonical_wrong_domain."""

    def test_applies_different_domain(self) -> None:
        """Canonical pointing to different domain should trigger."""
        from semrush_workers.rules.evaluators import rule_canonical_wrong_domain

        page = make_page(
            url="https://example.com/page", canonical_url="https://other-domain.com/page"
        )
        result = rule_canonical_wrong_domain(page, "example.com")

        assert result.applies is True
        assert result.evidence["canonical_domain"] == "other-domain.com"
        assert result.evidence["site_domain"] == "example.com"

    def test_not_applies_same_domain(self) -> None:
        """Canonical on same domain should not trigger."""
        from semrush_workers.rules.evaluators import rule_canonical_wrong_domain

        page = make_page(
            url="https://example.com/page", canonical_url="https://example.com/canonical"
        )
        result = rule_canonical_wrong_domain(page, "example.com")

        assert result.applies is False

    def test_not_applies_no_canonical(self) -> None:
        """No canonical should not trigger."""
        from semrush_workers.rules.evaluators import rule_canonical_wrong_domain

        page = make_page(url="https://example.com/page", canonical_url=None)
        result = rule_canonical_wrong_domain(page, "example.com")

        assert result.applies is False

    def test_handles_www_subdomain(self) -> None:
        """www subdomain should be treated as same domain."""
        from semrush_workers.rules.evaluators import rule_canonical_wrong_domain

        page = make_page(
            url="https://example.com/page", canonical_url="https://www.example.com/page"
        )
        result = rule_canonical_wrong_domain(page, "example.com")

        # www.example.com should be considered same as example.com
        assert result.applies is False


class TestRuleMissingSelfCanonical:
    """Tests for rule_missing_self_canonical."""

    def test_applies_no_canonical(self) -> None:
        """Page with no canonical should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_self_canonical

        page = make_page(url="https://example.com/page", canonical_url=None)
        result = rule_missing_self_canonical(page)

        assert result.applies is True
        assert result.evidence["reason"] == "missing"

    def test_applies_non_self_canonical(self) -> None:
        """Page with canonical pointing elsewhere should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_self_canonical

        page = make_page(
            url="https://example.com/page", canonical_url="https://example.com/other"
        )
        result = rule_missing_self_canonical(page)

        assert result.applies is True
        assert result.evidence["reason"] == "not_self_referencing"

    def test_not_applies_self_canonical(self) -> None:
        """Page with self-referencing canonical should not trigger."""
        from semrush_workers.rules.evaluators import rule_missing_self_canonical

        page = make_page(
            url="https://example.com/page", canonical_url="https://example.com/page"
        )
        result = rule_missing_self_canonical(page)

        assert result.applies is False

    def test_handles_trailing_slash(self) -> None:
        """Trailing slash differences should still match."""
        from semrush_workers.rules.evaluators import rule_missing_self_canonical

        page = make_page(
            url="https://example.com/page/", canonical_url="https://example.com/page"
        )
        result = rule_missing_self_canonical(page)

        # Should be considered self-referencing despite trailing slash
        assert result.applies is False


# =============================================================================
# Medium Severity Tests (severity=3)
# =============================================================================


class TestRuleTitleTooLong:
    """Tests for rule_title_too_long."""

    def test_applies_over_60_chars(self) -> None:
        """Title over 60 characters should trigger."""
        from semrush_workers.rules.evaluators import rule_title_too_long

        long_title = "A" * 65
        page = make_page(title=long_title)
        result = rule_title_too_long(page)

        assert result.applies is True
        assert result.evidence["title_length"] == 65
        assert result.evidence["max_length"] == 60

    def test_not_applies_exactly_60_chars(self) -> None:
        """Title exactly 60 characters should not trigger."""
        from semrush_workers.rules.evaluators import rule_title_too_long

        page = make_page(title="A" * 60)
        result = rule_title_too_long(page)

        assert result.applies is False

    def test_not_applies_short_title(self) -> None:
        """Short title should not trigger."""
        from semrush_workers.rules.evaluators import rule_title_too_long

        page = make_page(title="Short Title")
        result = rule_title_too_long(page)

        assert result.applies is False


class TestRuleTitleTooShort:
    """Tests for rule_title_too_short."""

    def test_applies_under_30_chars(self) -> None:
        """Title under 30 characters should trigger."""
        from semrush_workers.rules.evaluators import rule_title_too_short

        page = make_page(title="Short")
        result = rule_title_too_short(page)

        assert result.applies is True
        assert result.evidence["title_length"] == 5
        assert result.evidence["min_length"] == 30

    def test_not_applies_exactly_30_chars(self) -> None:
        """Title exactly 30 characters should not trigger."""
        from semrush_workers.rules.evaluators import rule_title_too_short

        page = make_page(title="A" * 30)
        result = rule_title_too_short(page)

        assert result.applies is False

    def test_not_applies_long_title(self) -> None:
        """Long title should not trigger."""
        from semrush_workers.rules.evaluators import rule_title_too_short

        page = make_page(title="This is a sufficiently long page title")
        result = rule_title_too_short(page)

        assert result.applies is False

    def test_not_applies_no_title(self) -> None:
        """No title should not trigger (that's missing_title rule)."""
        from semrush_workers.rules.evaluators import rule_title_too_short

        page = make_page(title=None)
        result = rule_title_too_short(page)

        assert result.applies is False


class TestRuleMetaDescriptionTooLong:
    """Tests for rule_meta_description_too_long."""

    def test_applies_over_160_chars(self) -> None:
        """Meta description over 160 characters should trigger."""
        from semrush_workers.rules.evaluators import rule_meta_description_too_long

        long_desc = "A" * 165
        page = make_page(meta_description=long_desc)
        result = rule_meta_description_too_long(page)

        assert result.applies is True
        assert result.evidence["description_length"] == 165

    def test_not_applies_exactly_160_chars(self) -> None:
        """Meta description exactly 160 characters should not trigger."""
        from semrush_workers.rules.evaluators import rule_meta_description_too_long

        page = make_page(meta_description="A" * 160)
        result = rule_meta_description_too_long(page)

        assert result.applies is False


class TestRuleMetaDescriptionTooShort:
    """Tests for rule_meta_description_too_short."""

    def test_applies_under_50_chars(self) -> None:
        """Meta description under 50 characters should trigger."""
        from semrush_workers.rules.evaluators import rule_meta_description_too_short

        page = make_page(meta_description="Too short")
        result = rule_meta_description_too_short(page)

        assert result.applies is True
        assert result.evidence["description_length"] == 9

    def test_not_applies_exactly_50_chars(self) -> None:
        """Meta description exactly 50 characters should not trigger."""
        from semrush_workers.rules.evaluators import rule_meta_description_too_short

        page = make_page(meta_description="A" * 50)
        result = rule_meta_description_too_short(page)

        assert result.applies is False

    def test_not_applies_no_description(self) -> None:
        """No description should not trigger (that's missing_meta rule)."""
        from semrush_workers.rules.evaluators import rule_meta_description_too_short

        page = make_page(meta_description=None)
        result = rule_meta_description_too_short(page)

        assert result.applies is False


class TestRuleMissingMetaDescription:
    """Tests for rule_missing_meta_description."""

    def test_applies_no_description(self) -> None:
        """Page with no meta description should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_meta_description

        page = make_page(meta_description=None)
        result = rule_missing_meta_description(page)

        assert result.applies is True

    def test_applies_empty_description(self) -> None:
        """Page with empty meta description should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_meta_description

        page = make_page(meta_description="")
        result = rule_missing_meta_description(page)

        assert result.applies is True

    def test_not_applies_valid_description(self) -> None:
        """Page with valid meta description should not trigger."""
        from semrush_workers.rules.evaluators import rule_missing_meta_description

        page = make_page(meta_description="A valid meta description.")
        result = rule_missing_meta_description(page)

        assert result.applies is False


class TestRuleMissingH1:
    """Tests for rule_missing_h1."""

    def test_applies_no_h1(self) -> None:
        """Page with no H1 should trigger."""
        from semrush_workers.rules.evaluators import rule_missing_h1

        page = make_page(h1_tags=[])
        result = rule_missing_h1(page)

        assert result.applies is True

    def test_not_applies_has_h1(self) -> None:
        """Page with H1 should not trigger."""
        from semrush_workers.rules.evaluators import rule_missing_h1

        page = make_page(h1_tags=["Main Heading"])
        result = rule_missing_h1(page)

        assert result.applies is False


class TestRuleMultipleH1:
    """Tests for rule_multiple_h1."""

    def test_applies_two_h1s(self) -> None:
        """Page with 2 H1s should trigger."""
        from semrush_workers.rules.evaluators import rule_multiple_h1

        page = make_page(h1_tags=["First Heading", "Second Heading"])
        result = rule_multiple_h1(page)

        assert result.applies is True
        assert result.evidence["h1_count"] == 2

    def test_not_applies_one_h1(self) -> None:
        """Page with 1 H1 should not trigger."""
        from semrush_workers.rules.evaluators import rule_multiple_h1

        page = make_page(h1_tags=["Only Heading"])
        result = rule_multiple_h1(page)

        assert result.applies is False

    def test_not_applies_no_h1(self) -> None:
        """Page with no H1 should not trigger (that's missing_h1 rule)."""
        from semrush_workers.rules.evaluators import rule_multiple_h1

        page = make_page(h1_tags=[])
        result = rule_multiple_h1(page)

        assert result.applies is False


class TestRuleNonHttps:
    """Tests for rule_non_https."""

    def test_applies_http_when_site_is_https(self) -> None:
        """HTTP page on HTTPS site should trigger."""
        from semrush_workers.rules.evaluators import rule_non_https

        page = make_page(url="http://example.com/page")
        result = rule_non_https(page, "https")

        assert result.applies is True
        assert result.evidence["page_scheme"] == "http"
        assert result.evidence["site_scheme"] == "https"

    def test_not_applies_https_page(self) -> None:
        """HTTPS page should not trigger."""
        from semrush_workers.rules.evaluators import rule_non_https

        page = make_page(url="https://example.com/page")
        result = rule_non_https(page, "https")

        assert result.applies is False

    def test_not_applies_http_site(self) -> None:
        """HTTP page on HTTP site should not trigger."""
        from semrush_workers.rules.evaluators import rule_non_https

        page = make_page(url="http://example.com/page")
        result = rule_non_https(page, "http")

        assert result.applies is False


class TestRuleMixedContent:
    """Tests for rule_mixed_content."""

    def test_applies_has_http_resources(self) -> None:
        """HTTPS page with HTTP resources should trigger."""
        from semrush_workers.rules.evaluators import rule_mixed_content

        page = make_page(
            url="https://example.com/page",
            mixed_content_urls=["http://cdn.example.com/image.jpg"],
        )
        result = rule_mixed_content(page)

        assert result.applies is True
        assert result.evidence["mixed_content_count"] == 1

    def test_not_applies_no_mixed_content(self) -> None:
        """HTTPS page with no HTTP resources should not trigger."""
        from semrush_workers.rules.evaluators import rule_mixed_content

        page = make_page(url="https://example.com/page", mixed_content_urls=[])
        result = rule_mixed_content(page)

        assert result.applies is False

    def test_not_applies_http_page(self) -> None:
        """HTTP page should not trigger (no mixed content issue on HTTP)."""
        from semrush_workers.rules.evaluators import rule_mixed_content

        page = make_page(
            url="http://example.com/page",
            mixed_content_urls=["http://cdn.example.com/image.jpg"],
        )
        result = rule_mixed_content(page)

        assert result.applies is False


# =============================================================================
# Low Severity Tests (severity=2)
# =============================================================================


class TestRuleThinContent:
    """Tests for rule_thin_content."""

    def test_applies_below_threshold(self) -> None:
        """Page with word count below threshold should trigger."""
        from semrush_workers.rules.evaluators import rule_thin_content

        page = make_page(word_count=100)
        result = rule_thin_content(page, min_words=300)

        assert result.applies is True
        assert result.evidence["word_count"] == 100
        assert result.evidence["min_words"] == 300

    def test_not_applies_above_threshold(self) -> None:
        """Page with word count above threshold should not trigger."""
        from semrush_workers.rules.evaluators import rule_thin_content

        page = make_page(word_count=500)
        result = rule_thin_content(page, min_words=300)

        assert result.applies is False

    def test_not_applies_exactly_threshold(self) -> None:
        """Page with word count exactly at threshold should not trigger."""
        from semrush_workers.rules.evaluators import rule_thin_content

        page = make_page(word_count=300)
        result = rule_thin_content(page, min_words=300)

        assert result.applies is False

    def test_custom_threshold(self) -> None:
        """Custom word threshold should be respected."""
        from semrush_workers.rules.evaluators import rule_thin_content

        page = make_page(word_count=400)
        result = rule_thin_content(page, min_words=500)

        assert result.applies is True


class TestRuleOrphanPage:
    """Tests for rule_orphan_page."""

    def test_applies_sitemap_no_links(self) -> None:
        """Sitemap page with no internal links should trigger."""
        from semrush_workers.rules.evaluators import rule_orphan_page

        page = make_page(
            url="https://example.com/orphan",
            discovery_source=DiscoverySource.SITEMAP,
        )
        edges: list[LinkEdge] = []  # No links pointing to this page
        result = rule_orphan_page(page, edges)

        assert result.applies is True
        assert result.evidence["discovery_source"] == "sitemap"

    def test_not_applies_has_internal_links(self) -> None:
        """Page with internal links should not trigger."""
        from semrush_workers.rules.evaluators import rule_orphan_page

        page = make_page(
            url="https://example.com/linked",
            discovery_source=DiscoverySource.SITEMAP,
        )
        edges = [
            make_edge(
                source_url="https://example.com/other",
                target_url="https://example.com/linked",
                is_internal=True,
            )
        ]
        result = rule_orphan_page(page, edges)

        assert result.applies is False

    def test_not_applies_not_from_sitemap(self) -> None:
        """Page not from sitemap should not trigger."""
        from semrush_workers.rules.evaluators import rule_orphan_page

        page = make_page(
            url="https://example.com/page",
            discovery_source=DiscoverySource.INTERNAL_LINK,
        )
        edges: list[LinkEdge] = []
        result = rule_orphan_page(page, edges)

        assert result.applies is False

    def test_ignores_external_links(self) -> None:
        """External links should not prevent orphan detection."""
        from semrush_workers.rules.evaluators import rule_orphan_page

        page = make_page(
            url="https://example.com/orphan",
            discovery_source=DiscoverySource.SITEMAP,
        )
        edges = [
            make_edge(
                source_url="https://external.com/page",
                target_url="https://example.com/orphan",
                is_internal=False,
            )
        ]
        result = rule_orphan_page(page, edges)

        assert result.applies is True
