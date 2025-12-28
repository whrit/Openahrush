"""
TDD tests for the issue regression detector.

Tests cover:
- Detecting regressions when new issues exceed threshold
- Categorizing new issues by type
- Severity determination based on issue count
- Edge cases
"""

from typing import Any

from semrush_workers.alerts.regression_detector import (
    RegressionDetector,
    RegressionResult,
)


class TestRegressionResultDataclass:
    """Tests for RegressionResult dataclass."""

    def test_severity_critical_for_many_issues(self) -> None:
        """Test severity is critical for >= 50 new issues."""
        result = RegressionResult(
            total_new_issues=50,
            issues_by_type={"missing_title": 30, "broken_links": 20},
        )
        assert result.severity == "critical"

    def test_severity_warn_for_moderate_issues(self) -> None:
        """Test severity is warn for 10-49 new issues."""
        result = RegressionResult(
            total_new_issues=25,
            issues_by_type={"missing_title": 15, "broken_links": 10},
        )
        assert result.severity == "warn"

    def test_severity_info_for_few_issues(self) -> None:
        """Test severity is info for < 10 new issues."""
        result = RegressionResult(
            total_new_issues=5,
            issues_by_type={"missing_title": 5},
        )
        assert result.severity == "info"


class TestRegressionDetector:
    """Tests for RegressionDetector."""

    def test_detect_regression_above_threshold(self) -> None:
        """Test detecting regression when new issues exceed threshold."""
        previous_issues = [
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
            {"issue_type_id": "missing_h1", "affected_url": "https://example.com/page2"},
        ]
        current_issues = [
            # Existing issues
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
            {"issue_type_id": "missing_h1", "affected_url": "https://example.com/page2"},
            # 15 new issues
            *[
                {"issue_type_id": "broken_link", "affected_url": f"https://example.com/new{i}"}
                for i in range(15)
            ],
        ]

        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression(previous_issues, current_issues)

        assert result is not None
        assert result.total_new_issues == 15
        assert result.issues_by_type["broken_link"] == 15

    def test_no_regression_below_threshold(self) -> None:
        """Test no regression when new issues below threshold."""
        previous_issues = [
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
        ]
        current_issues = [
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
            # 5 new issues - below threshold
            *[
                {"issue_type_id": "broken_link", "affected_url": f"https://example.com/new{i}"}
                for i in range(5)
            ],
        ]

        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression(previous_issues, current_issues)

        assert result is None

    def test_multiple_issue_types(self) -> None:
        """Test regression with multiple issue types."""
        previous_issues: list[dict[str, Any]] = []
        current_issues = [
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page2"},
            {"issue_type_id": "missing_h1", "affected_url": "https://example.com/page3"},
            {"issue_type_id": "broken_link", "affected_url": "https://example.com/page4"},
            {"issue_type_id": "broken_link", "affected_url": "https://example.com/page5"},
            {"issue_type_id": "broken_link", "affected_url": "https://example.com/page6"},
            # More issues to exceed threshold
            *[
                {"issue_type_id": "short_title", "affected_url": f"https://example.com/short{i}"}
                for i in range(10)
            ],
        ]

        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression(previous_issues, current_issues)

        assert result is not None
        assert result.issues_by_type["missing_title"] == 2
        assert result.issues_by_type["missing_h1"] == 1
        assert result.issues_by_type["broken_link"] == 3
        assert result.issues_by_type["short_title"] == 10
        assert result.total_new_issues == 16

    def test_empty_previous_issues(self) -> None:
        """Test when previous crawl had no issues."""
        previous_issues: list[dict[str, Any]] = []
        current_issues = [
            *[
                {"issue_type_id": "broken_link", "affected_url": f"https://example.com/new{i}"}
                for i in range(15)
            ],
        ]

        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression(previous_issues, current_issues)

        assert result is not None
        assert result.total_new_issues == 15

    def test_empty_current_issues(self) -> None:
        """Test when current crawl has no issues (improvement)."""
        previous_issues = [
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
            {"issue_type_id": "missing_h1", "affected_url": "https://example.com/page2"},
        ]
        current_issues: list[dict[str, Any]] = []

        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression(previous_issues, current_issues)

        assert result is None

    def test_both_empty(self) -> None:
        """Test when both crawls have no issues."""
        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression([], [])

        assert result is None

    def test_custom_threshold(self) -> None:
        """Test using a custom threshold."""
        issues = [
            {"issue_type_id": "broken_link", "affected_url": f"https://example.com/new{i}"}
            for i in range(5)
        ]

        # Default threshold (10) - no regression
        detector_high = RegressionDetector(threshold=10)
        assert detector_high.detect_regression([], issues) is None

        # Lower threshold (3) - regression detected
        detector_low = RegressionDetector(threshold=3)
        assert detector_low.detect_regression([], issues) is not None

    def test_to_alert_payload(self) -> None:
        """Test converting result to alert payload."""
        result = RegressionResult(
            total_new_issues=20,
            issues_by_type={"missing_title": 12, "broken_link": 8},
        )

        payload = result.to_alert_payload()

        assert payload["total_new_issues"] == 20
        assert payload["issues_by_type"] == {"missing_title": 12, "broken_link": 8}

    def test_issue_matching_by_key(self) -> None:
        """Test that issues are matched by (type_id, url) tuple."""
        previous_issues = [
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page1"},
        ]
        current_issues = [
            # Same type, different URL - new issue
            {"issue_type_id": "missing_title", "affected_url": "https://example.com/page2"},
            # Different type, same URL - new issue
            {"issue_type_id": "missing_h1", "affected_url": "https://example.com/page1"},
            # Add more to exceed threshold
            *[
                {"issue_type_id": "broken_link", "affected_url": f"https://example.com/new{i}"}
                for i in range(10)
            ],
        ]

        detector = RegressionDetector(threshold=10)
        result = detector.detect_regression(previous_issues, current_issues)

        assert result is not None
        # All 12 are new (the original issue is not in current)
        assert result.total_new_issues == 12
