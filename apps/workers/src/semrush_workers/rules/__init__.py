"""
Rules Engine for SEO site audits.

This module provides:
- Rule evaluators for detecting SEO issues
- RulesEngine for orchestrating rule evaluation
- Broken link and orphan page detection utilities

Rules are organized by severity:
- Critical (5): Server errors, redirect loops, broken internals
- High (4): 4xx pages, missing titles, canonical issues
- Medium (3): Title/meta length, H1 issues, HTTPS problems
- Low (2): Thin content, orphan pages
"""

from semrush_workers.rules.broken_links import (
    BrokenLinkSummary,
    detect_broken_links,
    get_broken_link_sources,
)
from semrush_workers.rules.engine import AnalysisResult, RuleDefinition, RulesEngine
from semrush_workers.rules.evaluators import (
    RuleResult,
    rule_broken_internal_link,
    rule_canonical_wrong_domain,
    rule_duplicate_title,
    rule_internal_4xx,
    rule_meta_description_too_long,
    rule_meta_description_too_short,
    rule_missing_h1,
    rule_missing_meta_description,
    rule_missing_self_canonical,
    rule_missing_title,
    rule_mixed_content,
    rule_multiple_h1,
    rule_non_https,
    rule_orphan_page,
    rule_redirect_chain_long,
    rule_redirect_loop,
    rule_server_error_5xx,
    rule_thin_content,
    rule_title_too_long,
    rule_title_too_short,
)
from semrush_workers.rules.models import (
    CrawlPage,
    DiscoverySource,
    IssueInstance,
    IssueSeverity,
    LinkEdge,
)
from semrush_workers.rules.orphan_pages import (
    OrphanPageSummary,
    detect_orphan_pages,
    get_internal_links_to_page,
)

__all__ = [
    # Models
    "CrawlPage",
    "DiscoverySource",
    "IssueInstance",
    "IssueSeverity",
    "LinkEdge",
    # Rule results
    "RuleResult",
    # Rule evaluators - Critical
    "rule_server_error_5xx",
    "rule_redirect_loop",
    "rule_redirect_chain_long",
    "rule_broken_internal_link",
    # Rule evaluators - High
    "rule_internal_4xx",
    "rule_missing_title",
    "rule_duplicate_title",
    "rule_canonical_wrong_domain",
    "rule_missing_self_canonical",
    # Rule evaluators - Medium
    "rule_title_too_long",
    "rule_title_too_short",
    "rule_meta_description_too_long",
    "rule_meta_description_too_short",
    "rule_missing_meta_description",
    "rule_missing_h1",
    "rule_multiple_h1",
    "rule_non_https",
    "rule_mixed_content",
    # Rule evaluators - Low
    "rule_thin_content",
    "rule_orphan_page",
    # Engine
    "RulesEngine",
    "RuleDefinition",
    "AnalysisResult",
    # Broken links
    "detect_broken_links",
    "get_broken_link_sources",
    "BrokenLinkSummary",
    # Orphan pages
    "detect_orphan_pages",
    "get_internal_links_to_page",
    "OrphanPageSummary",
]
