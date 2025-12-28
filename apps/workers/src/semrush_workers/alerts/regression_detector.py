"""
Issue regression detector.

Compares issue counts between crawls to detect
significant increases in issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegressionResult:
    """
    Result of regression detection.

    Attributes:
        total_new_issues: Total number of new issues.
        issues_by_type: Count of new issues grouped by type.
    """

    total_new_issues: int
    issues_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        """
        Determine severity based on issue count.

        Returns:
            'critical' for >= 50, 'warn' for >= 10, 'info' otherwise.
        """
        if self.total_new_issues >= 50:
            return "critical"
        if self.total_new_issues >= 10:
            return "warn"
        return "info"

    def to_alert_payload(self) -> dict[str, Any]:
        """
        Convert to alert payload format.

        Returns:
            Dictionary with regression details.
        """
        return {
            "total_new_issues": self.total_new_issues,
            "issues_by_type": self.issues_by_type,
        }


class RegressionDetector:
    """
    Detector for issue regressions between crawls.

    Compares issue sets between crawls to identify
    significant increases that may indicate problems.

    Attributes:
        threshold: Minimum new issues to trigger alert (default 10).
    """

    def __init__(self, threshold: int = 10) -> None:
        """
        Initialize the detector.

        Args:
            threshold: Minimum new issues to trigger alert.
        """
        self.threshold = threshold

    def detect_regression(
        self,
        previous_issues: list[dict[str, Any]],
        current_issues: list[dict[str, Any]],
    ) -> RegressionResult | None:
        """
        Detect regression between two crawl issue sets.

        Args:
            previous_issues: Issues from previous crawl.
                Each item should have 'issue_type_id' and 'affected_url'.
            current_issues: Issues from current crawl.
                Each item should have 'issue_type_id' and 'affected_url'.

        Returns:
            RegressionResult if regression detected, None otherwise.
        """
        # Build set of previous issue keys
        previous_keys = {
            (item.get("issue_type_id"), item.get("affected_url"))
            for item in previous_issues
        }

        # Find new issues (in current but not in previous)
        new_issues: list[dict[str, Any]] = []
        for item in current_issues:
            key = (item.get("issue_type_id"), item.get("affected_url"))
            if key not in previous_keys:
                new_issues.append(item)

        # Check if threshold exceeded
        if len(new_issues) < self.threshold:
            return None

        # Group by issue type
        issues_by_type: dict[str, int] = {}
        for item in new_issues:
            type_id = item.get("issue_type_id", "unknown")
            issues_by_type[type_id] = issues_by_type.get(type_id, 0) + 1

        return RegressionResult(
            total_new_issues=len(new_issues),
            issues_by_type=issues_by_type,
        )
