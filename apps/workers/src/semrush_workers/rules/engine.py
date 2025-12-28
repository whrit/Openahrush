"""
Rules Engine for orchestrating SEO rule evaluation.

The RulesEngine:
- Loads all enabled rules
- Evaluates each rule against crawl pages
- Creates issue instances for detected problems
- Handles cross-page analysis (duplicates, orphans, broken links)
- Emits 'rules.completed' event when done
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from semrush_workers.rules.evaluators import RuleResult
from semrush_workers.rules.models import (
    CrawlPage,
    DiscoverySource,
    IssueInstance,
    IssueSeverity,
    LinkEdge,
)


@dataclass
class RuleDefinition:
    """
    Definition of a rule to be evaluated.

    Attributes:
        rule_id: Unique rule identifier.
        name: Human-readable name.
        severity: Issue severity if rule matches.
        evaluator: Function that evaluates the rule.
        enabled: Whether the rule is active.
    """

    rule_id: str
    name: str
    severity: IssueSeverity
    evaluator: Callable[..., RuleResult]
    enabled: bool = True


@dataclass
class AnalysisResult:
    """
    Result of running the rules engine on a crawl.

    Attributes:
        issues_found: Total number of issues detected.
        issues_by_severity: Count of issues per severity level.
        issues_by_type: Count of issues per rule ID.
        pages_analyzed: Number of pages analyzed.
        duration_ms: Time taken to run analysis.
    """

    issues_found: int = 0
    issues_by_severity: dict[int, int] = field(default_factory=dict)
    issues_by_type: dict[str, int] = field(default_factory=dict)
    pages_analyzed: int = 0
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issues_found": self.issues_found,
            "issues_by_severity": self.issues_by_severity,
            "issues_by_type": self.issues_by_type,
            "pages_analyzed": self.pages_analyzed,
            "duration_ms": self.duration_ms,
        }


class RulesEngine:
    """
    Engine for running SEO rules against crawled pages.

    Orchestrates rule evaluation and issue creation. Supports:
    - Individual page rules (status codes, title, meta, etc.)
    - Cross-page analysis (duplicate titles)
    - Link-level analysis (broken links, orphan pages)

    Example:
        engine = RulesEngine()
        issues, result = engine.analyze(
            crawl_run_id=run_id,
            pages=pages,
            edges=edges,
            site_domain="example.com",
            site_scheme="https",
        )
    """

    def __init__(
        self,
        rules: list[RuleDefinition] | None = None,
        enabled_rule_ids: list[str] | None = None,
    ) -> None:
        """
        Initialize the rules engine.

        Args:
            rules: List of rule definitions to evaluate.
                   If None, default rules are loaded.
            enabled_rule_ids: Optional list of rule IDs to enable.
                              If None, all rules are enabled.
        """
        self.rules = rules or self._get_default_rules()

        # Filter to only enabled rules if specified
        if enabled_rule_ids is not None:
            for rule in self.rules:
                rule.enabled = rule.rule_id in enabled_rule_ids

    def _get_default_rules(self) -> list[RuleDefinition]:
        """Get the default set of SEO rules."""
        from semrush_workers.rules import evaluators

        return [
            # Critical (severity=5)
            RuleDefinition(
                rule_id="server_error_5xx",
                name="Server Error (5xx)",
                severity=IssueSeverity.CRITICAL,
                evaluator=evaluators.rule_server_error_5xx,
            ),
            RuleDefinition(
                rule_id="redirect_loop",
                name="Redirect Loop",
                severity=IssueSeverity.CRITICAL,
                evaluator=evaluators.rule_redirect_loop,
            ),
            RuleDefinition(
                rule_id="redirect_chain_long",
                name="Long Redirect Chain (>3 hops)",
                severity=IssueSeverity.CRITICAL,
                evaluator=evaluators.rule_redirect_chain_long,
            ),
            # High (severity=4)
            RuleDefinition(
                rule_id="internal_4xx",
                name="Internal 4xx Error",
                severity=IssueSeverity.HIGH,
                evaluator=evaluators.rule_internal_4xx,
            ),
            RuleDefinition(
                rule_id="missing_title",
                name="Missing Title Tag",
                severity=IssueSeverity.HIGH,
                evaluator=evaluators.rule_missing_title,
            ),
            RuleDefinition(
                rule_id="missing_self_canonical",
                name="Missing Self-Referencing Canonical",
                severity=IssueSeverity.HIGH,
                evaluator=evaluators.rule_missing_self_canonical,
            ),
            # Medium (severity=3)
            RuleDefinition(
                rule_id="title_too_long",
                name="Title Too Long (>60 chars)",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_title_too_long,
            ),
            RuleDefinition(
                rule_id="title_too_short",
                name="Title Too Short (<30 chars)",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_title_too_short,
            ),
            RuleDefinition(
                rule_id="meta_description_too_long",
                name="Meta Description Too Long (>160 chars)",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_meta_description_too_long,
            ),
            RuleDefinition(
                rule_id="meta_description_too_short",
                name="Meta Description Too Short (<50 chars)",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_meta_description_too_short,
            ),
            RuleDefinition(
                rule_id="missing_meta_description",
                name="Missing Meta Description",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_missing_meta_description,
            ),
            RuleDefinition(
                rule_id="missing_h1",
                name="Missing H1 Tag",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_missing_h1,
            ),
            RuleDefinition(
                rule_id="multiple_h1",
                name="Multiple H1 Tags",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_multiple_h1,
            ),
            RuleDefinition(
                rule_id="mixed_content",
                name="Mixed Content (HTTP resources on HTTPS page)",
                severity=IssueSeverity.MEDIUM,
                evaluator=evaluators.rule_mixed_content,
            ),
            # Low (severity=2)
            RuleDefinition(
                rule_id="thin_content",
                name="Thin Content (<300 words)",
                severity=IssueSeverity.LOW,
                evaluator=evaluators.rule_thin_content,
            ),
        ]

    def analyze(
        self,
        crawl_run_id: uuid.UUID,
        pages: list[CrawlPage],
        edges: list[LinkEdge] | None = None,
        site_domain: str = "",
        site_scheme: str = "https",
    ) -> tuple[list[IssueInstance], AnalysisResult]:
        """
        Run full analysis on crawl data.

        This is the main entry point for the rules engine. It:
        1. Evaluates individual page rules
        2. Detects duplicate titles
        3. Detects broken internal links
        4. Detects orphan pages

        Args:
            crawl_run_id: ID of the crawl run being analyzed.
            pages: List of crawl pages to analyze.
            edges: List of link edges (optional, needed for broken link detection).
            site_domain: Domain of the site being analyzed.
            site_scheme: URL scheme ('http' or 'https').

        Returns:
            Tuple of (list of issues, analysis result).
        """
        start = time.monotonic()
        edges = edges or []
        all_issues: list[IssueInstance] = []

        # 1. Individual page rules
        for page in pages:
            page_issues = self._analyze_page(
                page=page,
                crawl_run_id=crawl_run_id,
                all_pages=pages,
                edges=edges,
                site_domain=site_domain,
                site_scheme=site_scheme,
            )
            all_issues.extend(page_issues)

        # 2. Cross-page analysis: duplicate titles
        all_issues.extend(self._detect_duplicate_titles(pages, crawl_run_id))

        # 3. Link-level analysis: broken internal links
        all_issues.extend(self._detect_broken_links(edges, crawl_run_id))

        # 4. Link-level analysis: orphan pages
        all_issues.extend(self._detect_orphan_pages(pages, edges, crawl_run_id))

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Build result summary
        result = AnalysisResult(
            issues_found=len(all_issues),
            issues_by_severity={},
            issues_by_type={},
            pages_analyzed=len(pages),
            duration_ms=elapsed_ms,
        )

        for issue in all_issues:
            sev = issue.severity.value
            result.issues_by_severity[sev] = result.issues_by_severity.get(sev, 0) + 1
            result.issues_by_type[issue.issue_type_id] = (
                result.issues_by_type.get(issue.issue_type_id, 0) + 1
            )

        return all_issues, result

    def _analyze_page(
        self,
        page: CrawlPage,
        crawl_run_id: uuid.UUID,
        all_pages: list[CrawlPage],
        edges: list[LinkEdge],
        site_domain: str,
        site_scheme: str,
    ) -> list[IssueInstance]:
        """
        Analyze a single page against all enabled rules.

        Args:
            page: The crawl page to analyze.
            crawl_run_id: ID of the current crawl run.
            all_pages: All pages in the crawl (for cross-page rules).
            edges: Link edges for the crawl.
            site_domain: Domain of the site.
            site_scheme: URL scheme of the site.

        Returns:
            List of detected issues for this page.
        """
        from semrush_workers.rules import evaluators

        issues: list[IssueInstance] = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                # Determine which arguments the evaluator needs
                rule_id = rule.rule_id
                if rule_id == "canonical_wrong_domain":
                    result = evaluators.rule_canonical_wrong_domain(page, site_domain)
                elif rule_id == "non_https":
                    result = evaluators.rule_non_https(page, site_scheme)
                else:
                    result = rule.evaluator(page)

                if result.applies:
                    issue = IssueInstance(
                        id=uuid.uuid4(),
                        crawl_run_id=crawl_run_id,
                        crawl_page_id=page.id,
                        issue_type_id=rule.rule_id,
                        affected_url=page.url,
                        severity=rule.severity,
                        confidence=result.confidence,
                        evidence=result.evidence,
                        created_at=datetime.now(UTC),
                    )
                    issues.append(issue)
            except Exception:
                # Log and continue on rule errors
                pass

        return issues

    def _detect_duplicate_titles(
        self,
        pages: list[CrawlPage],
        crawl_run_id: uuid.UUID,
    ) -> list[IssueInstance]:
        """
        Detect pages with duplicate titles.

        Args:
            pages: List of crawl pages.
            crawl_run_id: ID of the current crawl run.

        Returns:
            List of duplicate title issues.
        """
        issues: list[IssueInstance] = []
        title_to_pages: dict[str, list[CrawlPage]] = {}

        for page in pages:
            if page.title and page.title.strip():
                normalized = page.title.strip().lower()
                if normalized not in title_to_pages:
                    title_to_pages[normalized] = []
                title_to_pages[normalized].append(page)

        for _title, dup_pages in title_to_pages.items():
            if len(dup_pages) > 1:
                for page in dup_pages:
                    issue = IssueInstance(
                        id=uuid.uuid4(),
                        crawl_run_id=crawl_run_id,
                        crawl_page_id=page.id,
                        issue_type_id="duplicate_title",
                        affected_url=page.url,
                        severity=IssueSeverity.HIGH,
                        confidence=1.0,
                        evidence={
                            "title": page.title,
                            "duplicate_count": len(dup_pages),
                            "duplicate_urls": [p.url for p in dup_pages if p.url != page.url],
                        },
                        created_at=datetime.now(UTC),
                    )
                    issues.append(issue)

        return issues

    def _detect_broken_links(
        self,
        edges: list[LinkEdge],
        crawl_run_id: uuid.UUID,
    ) -> list[IssueInstance]:
        """
        Detect broken internal links.

        Creates issues for unique broken target URLs only (not duplicate edges).

        Args:
            edges: List of link edges from the crawl.
            crawl_run_id: ID of the current crawl run.

        Returns:
            List of broken link issues.
        """
        issues: list[IssueInstance] = []
        seen_targets: set[str] = set()

        for edge in edges:
            if not edge.is_internal:
                continue
            if edge.target_status_code is None:
                continue
            if edge.target_status_code >= 400:
                # Only report unique broken targets once
                target_normalized = edge.target_url.lower().rstrip("/")
                if target_normalized not in seen_targets:
                    seen_targets.add(target_normalized)
                    issue = IssueInstance(
                        id=uuid.uuid4(),
                        crawl_run_id=crawl_run_id,
                        crawl_page_id=None,  # Link-level issue
                        issue_type_id="broken_internal_link",
                        affected_url=edge.target_url,
                        severity=IssueSeverity.CRITICAL,
                        confidence=1.0,
                        evidence={
                            "source_url": edge.source_url,
                            "target_url": edge.target_url,
                            "status_code": edge.target_status_code,
                        },
                        created_at=datetime.now(UTC),
                    )
                    issues.append(issue)

        return issues

    def _detect_orphan_pages(
        self,
        pages: list[CrawlPage],
        edges: list[LinkEdge],
        crawl_run_id: uuid.UUID,
    ) -> list[IssueInstance]:
        """
        Detect orphan pages (in sitemap but not internally linked).

        Args:
            pages: List of crawl pages.
            edges: List of link edges.
            crawl_run_id: ID of the current crawl run.

        Returns:
            List of orphan page issues.
        """
        issues: list[IssueInstance] = []

        # Build set of internally linked URLs (normalized)
        linked_urls: set[str] = set()
        for edge in edges:
            if edge.is_internal:
                linked_urls.add(edge.target_url.lower().rstrip("/"))

        # Find sitemap pages not internally linked
        for page in pages:
            if page.discovery_source == DiscoverySource.SITEMAP:
                page_normalized = page.url.lower().rstrip("/")
                if page_normalized not in linked_urls:
                    issue = IssueInstance(
                        id=uuid.uuid4(),
                        crawl_run_id=crawl_run_id,
                        crawl_page_id=page.id,
                        issue_type_id="orphan_page",
                        affected_url=page.url,
                        severity=IssueSeverity.LOW,
                        confidence=0.9,
                        evidence={
                            "discovery_source": page.discovery_source.value,
                            "internal_links_to_page": 0,
                        },
                        created_at=datetime.now(UTC),
                    )
                    issues.append(issue)

        return issues

    def get_event_payload(
        self,
        crawl_run_id: uuid.UUID,
        project_id: uuid.UUID,
        result: AnalysisResult,
    ) -> dict[str, Any]:
        """
        Build the 'rules.completed' event payload.

        Args:
            crawl_run_id: ID of the crawl run.
            project_id: ID of the project.
            result: Analysis result.

        Returns:
            Event payload dictionary.
        """
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "rules.completed",
            "occurred_at": datetime.now(UTC).isoformat(),
            "project_id": str(project_id),
            "trace_id": str(uuid.uuid4()),
            "payload": {
                "crawl_run_id": str(crawl_run_id),
                "issues_found": result.issues_found,
                "issues_by_severity": result.issues_by_severity,
                "issues_by_type": result.issues_by_type,
                "pages_analyzed": result.pages_analyzed,
                "duration_ms": result.duration_ms,
            },
        }
