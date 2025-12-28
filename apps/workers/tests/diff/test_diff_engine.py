"""
TDD tests for the diff engine.

Tests cover:
- Finding new issues (in B, not in A)
- Finding resolved issues (in A, not in B)
- Finding changed issues (severity/confidence changed)
- Edge cases (empty runs, identical runs)
"""

import uuid
from decimal import Decimal

from semrush_workers.diff.diff_engine import (
    DiffEngine,
    DiffResult,
    IssueData,
)


class TestIssueData:
    """Tests for IssueData dataclass."""

    def test_issue_key_tuple(self) -> None:
        """Test that issue_key returns the correct tuple."""
        issue = IssueData(
            id=uuid.uuid4(),
            issue_type_id="missing_title",
            affected_url="https://example.com/page1",
            severity="critical",
            confidence=Decimal("0.95"),
        )
        assert issue.issue_key == ("missing_title", "https://example.com/page1")

    def test_issue_data_defaults(self) -> None:
        """Test default values for optional fields."""
        issue = IssueData(
            id=uuid.uuid4(),
            issue_type_id="missing_h1",
            affected_url="https://example.com/",
            severity="warning",
        )
        assert issue.confidence is None
        assert issue.message is None


class TestDiffEngine:
    """Tests for DiffEngine."""

    def test_find_new_issues(self) -> None:
        """Test finding issues that exist in B but not in A."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
        ]
        issues_b = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_h1",
                affected_url="https://example.com/page2",
                severity="warning",
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.added) == 1
        assert result.added[0].issue_type_id == "missing_h1"
        assert result.added[0].affected_url == "https://example.com/page2"

    def test_find_resolved_issues(self) -> None:
        """Test finding issues that exist in A but not in B."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_h1",
                affected_url="https://example.com/page2",
                severity="warning",
            ),
        ]
        issues_b = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.resolved) == 1
        assert result.resolved[0].issue_type_id == "missing_h1"
        assert result.resolved[0].affected_url == "https://example.com/page2"

    def test_find_changed_severity(self) -> None:
        """Test finding issues where severity changed."""
        issue_id_a = uuid.uuid4()
        issue_id_b = uuid.uuid4()

        issues_a = [
            IssueData(
                id=issue_id_a,
                issue_type_id="short_title",
                affected_url="https://example.com/page1",
                severity="warning",
                confidence=Decimal("0.90"),
            ),
        ]
        issues_b = [
            IssueData(
                id=issue_id_b,
                issue_type_id="short_title",
                affected_url="https://example.com/page1",
                severity="critical",
                confidence=Decimal("0.90"),
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.changed) == 1
        assert result.changed[0].before.severity == "warning"
        assert result.changed[0].after.severity == "critical"
        assert result.changed[0].severity_changed is True
        assert result.changed[0].confidence_changed is False

    def test_find_changed_confidence(self) -> None:
        """Test finding issues where confidence changed."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="duplicate_content",
                affected_url="https://example.com/page1",
                severity="warning",
                confidence=Decimal("0.70"),
            ),
        ]
        issues_b = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="duplicate_content",
                affected_url="https://example.com/page1",
                severity="warning",
                confidence=Decimal("0.95"),
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.changed) == 1
        assert result.changed[0].before.confidence == Decimal("0.70")
        assert result.changed[0].after.confidence == Decimal("0.95")
        assert result.changed[0].severity_changed is False
        assert result.changed[0].confidence_changed is True

    def test_unchanged_issues_not_in_result(self) -> None:
        """Test that unchanged issues are not in any result list."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
                confidence=Decimal("0.95"),
            ),
        ]
        issues_b = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
                confidence=Decimal("0.95"),
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.added) == 0
        assert len(result.resolved) == 0
        assert len(result.changed) == 0

    def test_empty_crawl_a(self) -> None:
        """Test diffing when crawl A is empty."""
        issues_a: list[IssueData] = []
        issues_b = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.added) == 1
        assert len(result.resolved) == 0

    def test_empty_crawl_b(self) -> None:
        """Test diffing when crawl B is empty (all issues resolved)."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
        ]
        issues_b: list[IssueData] = []

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.added) == 0
        assert len(result.resolved) == 1

    def test_both_empty(self) -> None:
        """Test diffing when both crawls are empty."""
        issues_a: list[IssueData] = []
        issues_b: list[IssueData] = []

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.added) == 0
        assert len(result.resolved) == 0
        assert len(result.changed) == 0

    def test_complex_diff_scenario(self) -> None:
        """Test a complex scenario with adds, removes, and changes."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_h1",
                affected_url="https://example.com/page2",
                severity="warning",
            ),
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="short_description",
                affected_url="https://example.com/page3",
                severity="info",
                confidence=Decimal("0.80"),
            ),
        ]
        issues_b = [
            # page1 issue resolved
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_h1",
                affected_url="https://example.com/page2",
                severity="warning",
            ),
            # page3 severity changed from info to warning
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="short_description",
                affected_url="https://example.com/page3",
                severity="warning",
                confidence=Decimal("0.80"),
            ),
            # new issue on page4
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="broken_link",
                affected_url="https://example.com/page4",
                severity="critical",
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        assert len(result.added) == 1
        assert result.added[0].issue_type_id == "broken_link"

        assert len(result.resolved) == 1
        assert result.resolved[0].issue_type_id == "missing_title"

        assert len(result.changed) == 1
        assert result.changed[0].before.severity == "info"
        assert result.changed[0].after.severity == "warning"

    def test_same_type_different_urls_are_different_issues(self) -> None:
        """Test that same issue type on different URLs are treated as different issues."""
        issues_a = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page1",
                severity="critical",
            ),
        ]
        issues_b = [
            IssueData(
                id=uuid.uuid4(),
                issue_type_id="missing_title",
                affected_url="https://example.com/page2",
                severity="critical",
            ),
        ]

        engine = DiffEngine()
        result = engine.compute_diff(issues_a, issues_b)

        # page1 issue resolved, page2 issue is new
        assert len(result.added) == 1
        assert result.added[0].affected_url == "https://example.com/page2"
        assert len(result.resolved) == 1
        assert result.resolved[0].affected_url == "https://example.com/page1"


class TestDiffResult:
    """Tests for DiffResult dataclass."""

    def test_total_changes_count(self) -> None:
        """Test the total_changes property."""
        result = DiffResult(
            added=[
                IssueData(
                    id=uuid.uuid4(),
                    issue_type_id="a",
                    affected_url="u1",
                    severity="info",
                ),
            ],
            resolved=[
                IssueData(
                    id=uuid.uuid4(),
                    issue_type_id="b",
                    affected_url="u2",
                    severity="warning",
                ),
                IssueData(
                    id=uuid.uuid4(),
                    issue_type_id="c",
                    affected_url="u3",
                    severity="critical",
                ),
            ],
            changed=[],
        )

        assert result.total_changes == 3

    def test_has_changes(self) -> None:
        """Test the has_changes property."""
        empty_result = DiffResult(added=[], resolved=[], changed=[])
        assert empty_result.has_changes is False

        result_with_added = DiffResult(
            added=[
                IssueData(
                    id=uuid.uuid4(),
                    issue_type_id="a",
                    affected_url="u",
                    severity="info",
                ),
            ],
            resolved=[],
            changed=[],
        )
        assert result_with_added.has_changes is True
