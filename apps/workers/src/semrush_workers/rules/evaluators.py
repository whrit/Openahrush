"""
Rule evaluators for detecting SEO issues.

Each rule function takes a CrawlPage and returns a RuleResult
indicating whether the rule applies and with what confidence.

Rules are organized by severity:
- Critical (5): Server errors, redirect loops, broken internals
- High (4): 4xx pages, missing titles, canonical issues
- Medium (3): Title/meta length, H1 issues, HTTPS problems
- Low (2): Thin content, orphan pages
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from semrush_workers.rules.models import CrawlPage, LinkEdge


@dataclass
class RuleResult:
    """
    Result of evaluating a rule against a page.

    Attributes:
        applies: Whether the rule detected an issue.
        confidence: Confidence score (0.0 to 1.0).
        evidence: Additional data about the issue.
    """

    applies: bool
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison (remove trailing slash, lowercase)."""
    return url.lower().rstrip("/")


def _extract_domain(url: str) -> str:
    """Extract domain from URL, handling www prefix."""
    if "://" in url:
        url = url.split("://", 1)[1]
    if "/" in url:
        url = url.split("/", 1)[0]
    domain = url.lower()
    # Normalize www prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


# =============================================================================
# Critical Severity Rules (5)
# =============================================================================


def rule_server_error_5xx(page: CrawlPage) -> RuleResult:
    """Detect pages returning 5xx server errors."""
    if page.is_server_error():
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"status_code": page.status_code, "url": page.url},
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_redirect_loop(page: CrawlPage) -> RuleResult:
    """Detect redirect loops where a URL appears multiple times in the chain."""
    if not page.redirect_chain or len(page.redirect_chain) < 2:
        return RuleResult(applies=False, confidence=0.0)

    seen: set[str] = set()
    for url in page.redirect_chain:
        normalized = _normalize_url(url)
        if normalized in seen:
            return RuleResult(
                applies=True,
                confidence=1.0,
                evidence={"loop_url": url, "chain": page.redirect_chain},
            )
        seen.add(normalized)
    return RuleResult(applies=False, confidence=0.0)


def rule_redirect_chain_long(page: CrawlPage, max_hops: int = 3) -> RuleResult:
    """Detect redirect chains longer than max_hops (default 3)."""
    chain_length = len(page.redirect_chain)
    if chain_length > max_hops:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "chain_length": chain_length,
                "max_allowed": max_hops,
                "redirect_chain": page.redirect_chain,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_broken_internal_link(page: CrawlPage, edges: list[LinkEdge]) -> RuleResult:
    """
    Detect internal links from this page that point to 4xx/5xx pages.

    Args:
        page: The crawled page to evaluate.
        edges: List of link edges from this page.

    Returns:
        RuleResult with applies=True if broken internal links found.
    """
    broken_links: list[dict[str, Any]] = []

    for edge in edges:
        # Only check internal links from this page
        if not edge.is_internal:
            continue
        if _normalize_url(edge.source_url) != _normalize_url(page.url):
            continue
        if edge.target_status_code is None:
            continue

        # Check for 4xx or 5xx status
        if edge.target_status_code >= 400:
            broken_links.append({
                "target_url": edge.target_url,
                "status_code": edge.target_status_code,
                "anchor_text": edge.anchor_text,
            })

    if broken_links:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"broken_links": broken_links, "count": len(broken_links)},
        )
    return RuleResult(applies=False, confidence=0.0)


# =============================================================================
# High Severity Rules (4)
# =============================================================================


def rule_internal_4xx(page: CrawlPage) -> RuleResult:
    """Detect pages returning 4xx client errors."""
    if page.is_client_error():
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"status_code": page.status_code, "url": page.url},
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_missing_title(page: CrawlPage) -> RuleResult:
    """Detect pages with missing title tag."""
    if not page.title or not page.title.strip():
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"url": page.url},
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_duplicate_title(page: CrawlPage, other_pages: list[CrawlPage]) -> RuleResult:
    """
    Detect pages with duplicate title tags.

    Args:
        page: The crawled page to evaluate.
        other_pages: Other pages in the crawl run to compare against.

    Returns:
        RuleResult with applies=True if duplicate titles found.
    """
    if not page.title or not page.title.strip():
        return RuleResult(applies=False, confidence=0.0)

    duplicate_urls: list[str] = []
    page_title_normalized = page.title.strip().lower()

    for other in other_pages:
        if other.id == page.id:
            continue
        if other.title and other.title.strip().lower() == page_title_normalized:
            duplicate_urls.append(other.url)

    if duplicate_urls:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "title": page.title,
                "duplicate_urls": duplicate_urls,
                "duplicate_count": len(duplicate_urls),
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_canonical_wrong_domain(page: CrawlPage, site_domain: str) -> RuleResult:
    """
    Detect pages with canonical URLs pointing to a different domain.

    Args:
        page: The crawled page to evaluate.
        site_domain: The expected domain for the site.

    Returns:
        RuleResult with applies=True if canonical points elsewhere.
    """
    if not page.canonical_url:
        return RuleResult(applies=False, confidence=0.0)

    canonical_domain = _extract_domain(page.canonical_url)
    normalized_site_domain = _extract_domain(site_domain)

    if canonical_domain != normalized_site_domain:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "canonical_url": page.canonical_url,
                "canonical_domain": canonical_domain,
                "site_domain": normalized_site_domain,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_missing_self_canonical(page: CrawlPage) -> RuleResult:
    """
    Detect pages missing a self-referencing canonical tag.

    Args:
        page: The crawled page to evaluate.

    Returns:
        RuleResult with applies=True if canonical is missing or not self-referencing.
    """
    if not page.canonical_url:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"url": page.url, "reason": "missing"},
        )

    # Compare normalized URLs (handle trailing slash differences)
    page_normalized = _normalize_url(page.url)
    canonical_normalized = _normalize_url(page.canonical_url)

    if page_normalized != canonical_normalized:
        return RuleResult(
            applies=True,
            confidence=0.9,
            evidence={
                "url": page.url,
                "canonical_url": page.canonical_url,
                "reason": "not_self_referencing",
            },
        )
    return RuleResult(applies=False, confidence=0.0)


# =============================================================================
# Medium Severity Rules (3)
# =============================================================================


def rule_title_too_long(page: CrawlPage, max_length: int = 60) -> RuleResult:
    """Detect titles longer than max_length (default 60) characters."""
    if not page.title:
        return RuleResult(applies=False, confidence=0.0)

    title_length = len(page.title)
    if title_length > max_length:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "title": page.title,
                "title_length": title_length,
                "max_length": max_length,
                "excess": title_length - max_length,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_title_too_short(page: CrawlPage, min_length: int = 30) -> RuleResult:
    """Detect titles shorter than min_length (default 30) characters."""
    if not page.title:
        return RuleResult(applies=False, confidence=0.0)

    title_length = len(page.title)
    if title_length < min_length:
        return RuleResult(
            applies=True,
            confidence=0.8,
            evidence={
                "title": page.title,
                "title_length": title_length,
                "min_length": min_length,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_meta_description_too_long(page: CrawlPage, max_length: int = 160) -> RuleResult:
    """Detect meta descriptions longer than max_length (default 160) characters."""
    if not page.meta_description:
        return RuleResult(applies=False, confidence=0.0)

    desc_length = len(page.meta_description)
    if desc_length > max_length:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "description": page.meta_description[:100] + "..."
                if len(page.meta_description) > 100
                else page.meta_description,
                "description_length": desc_length,
                "max_length": max_length,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_meta_description_too_short(page: CrawlPage, min_length: int = 50) -> RuleResult:
    """Detect meta descriptions shorter than min_length (default 50) characters."""
    if not page.meta_description:
        return RuleResult(applies=False, confidence=0.0)

    desc_length = len(page.meta_description)
    if desc_length < min_length:
        return RuleResult(
            applies=True,
            confidence=0.8,
            evidence={
                "description": page.meta_description,
                "description_length": desc_length,
                "min_length": min_length,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_missing_meta_description(page: CrawlPage) -> RuleResult:
    """Detect pages with missing meta description."""
    if not page.meta_description or not page.meta_description.strip():
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"url": page.url},
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_missing_h1(page: CrawlPage) -> RuleResult:
    """Detect pages with no H1 tag."""
    if not page.h1_tags:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"url": page.url},
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_multiple_h1(page: CrawlPage) -> RuleResult:
    """Detect pages with multiple H1 tags."""
    if len(page.h1_tags) > 1:
        return RuleResult(
            applies=True,
            confidence=0.8,
            evidence={
                "h1_count": len(page.h1_tags),
                "h1_tags": page.h1_tags,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_non_https(page: CrawlPage, site_scheme: str) -> RuleResult:
    """Detect HTTP pages when the site should be HTTPS."""
    if site_scheme.lower() == "https" and page.scheme == "http":
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "url": page.url,
                "page_scheme": page.scheme,
                "site_scheme": site_scheme,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_mixed_content(page: CrawlPage) -> RuleResult:
    """Detect HTTPS pages with HTTP resources (mixed content)."""
    # Only relevant for HTTPS pages
    if page.scheme != "https":
        return RuleResult(applies=False, confidence=0.0)

    if page.mixed_content_urls:
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={
                "url": page.url,
                "mixed_content_count": len(page.mixed_content_urls),
                "mixed_content_urls": page.mixed_content_urls[:10],
            },
        )
    return RuleResult(applies=False, confidence=0.0)


# =============================================================================
# Low Severity Rules (2)
# =============================================================================


def rule_thin_content(page: CrawlPage, min_words: int = 300) -> RuleResult:
    """Detect pages with thin content (low word count)."""
    if page.word_count < min_words:
        return RuleResult(
            applies=True,
            confidence=0.7,
            evidence={
                "url": page.url,
                "word_count": page.word_count,
                "min_words": min_words,
            },
        )
    return RuleResult(applies=False, confidence=0.0)


def rule_orphan_page(page: CrawlPage, edges: list[LinkEdge]) -> RuleResult:
    """
    Detect pages discovered via sitemap but not internally linked.

    Args:
        page: The crawled page to evaluate.
        edges: List of all link edges pointing to pages in the crawl.

    Returns:
        RuleResult with applies=True if page is orphaned.
    """
    from semrush_workers.rules.models import DiscoverySource

    # Only check pages discovered via sitemap
    if page.discovery_source != DiscoverySource.SITEMAP:
        return RuleResult(applies=False, confidence=0.0)

    # Check if any internal link points to this page
    page_normalized = _normalize_url(page.url)
    for edge in edges:
        if not edge.is_internal:
            continue
        if _normalize_url(edge.target_url) == page_normalized:
            return RuleResult(applies=False, confidence=0.0)

    return RuleResult(
        applies=True,
        confidence=0.9,
        evidence={
            "url": page.url,
            "discovery_source": page.discovery_source.value,
        },
    )
