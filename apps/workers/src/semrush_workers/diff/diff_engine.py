"""
Diff engine for comparing issues between crawl runs.

Compares issues from two crawl runs to find:
- New issues (in B, not in A)
- Resolved issues (in A, not in B)
- Changed issues (severity or confidence changed)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class IssueData:
    """
    Lightweight issue representation for diffing.

    Uses (issue_type_id, affected_url) as the unique key for matching.

    Attributes:
        id: UUID of the issue instance.
        issue_type_id: Type identifier (e.g., 'missing_title').
        affected_url: URL where the issue was found.
        severity: Issue severity level.
        confidence: Optional confidence score.
        message: Optional human-readable message.
    """

    id: uuid.UUID
    issue_type_id: str
    affected_url: str
    severity: str
    confidence: Decimal | None = None
    message: str | None = None

    @property
    def issue_key(self) -> tuple[str, str]:
        """
        Get the unique key for matching issues.

        Returns:
            Tuple of (issue_type_id, affected_url).
        """
        return (self.issue_type_id, self.affected_url)


@dataclass
class ChangedIssue:
    """
    Represents an issue that changed between crawls.

    Attributes:
        before: Issue state in the first crawl.
        after: Issue state in the second crawl.
        severity_changed: Whether severity changed.
        confidence_changed: Whether confidence changed.
    """

    before: IssueData
    after: IssueData
    severity_changed: bool = False
    confidence_changed: bool = False


@dataclass
class DiffResult:
    """
    Result of comparing issues between two crawls.

    Attributes:
        added: Issues that are new in the second crawl.
        resolved: Issues that were fixed (not in second crawl).
        changed: Issues where severity or confidence changed.
    """

    added: list[IssueData] = field(default_factory=list)
    resolved: list[IssueData] = field(default_factory=list)
    changed: list[ChangedIssue] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Get total number of changes."""
        return len(self.added) + len(self.resolved) + len(self.changed)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return self.total_changes > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "added": [
                {
                    "id": str(i.id),
                    "issue_type_id": i.issue_type_id,
                    "affected_url": i.affected_url,
                    "severity": i.severity,
                    "confidence": float(i.confidence) if i.confidence else None,
                    "message": i.message,
                }
                for i in self.added
            ],
            "resolved": [
                {
                    "id": str(i.id),
                    "issue_type_id": i.issue_type_id,
                    "affected_url": i.affected_url,
                    "severity": i.severity,
                    "confidence": float(i.confidence) if i.confidence else None,
                    "message": i.message,
                }
                for i in self.resolved
            ],
            "changed": [
                {
                    "before": {
                        "id": str(c.before.id),
                        "issue_type_id": c.before.issue_type_id,
                        "affected_url": c.before.affected_url,
                        "severity": c.before.severity,
                        "confidence": float(c.before.confidence)
                        if c.before.confidence
                        else None,
                    },
                    "after": {
                        "id": str(c.after.id),
                        "issue_type_id": c.after.issue_type_id,
                        "affected_url": c.after.affected_url,
                        "severity": c.after.severity,
                        "confidence": float(c.after.confidence)
                        if c.after.confidence
                        else None,
                    },
                    "severity_changed": c.severity_changed,
                    "confidence_changed": c.confidence_changed,
                }
                for c in self.changed
            ],
            "summary": {
                "added_count": len(self.added),
                "resolved_count": len(self.resolved),
                "changed_count": len(self.changed),
                "total_changes": self.total_changes,
            },
        }


class DiffEngine:
    """
    Engine for computing diffs between crawl run issues.

    Matches issues by their (issue_type_id, affected_url) tuple
    and identifies:
    - New issues (in B but not A)
    - Resolved issues (in A but not B)
    - Changed issues (same key but different severity/confidence)
    """

    def compute_diff(
        self,
        issues_a: list[IssueData],
        issues_b: list[IssueData],
    ) -> DiffResult:
        """
        Compute the diff between two sets of issues.

        Args:
            issues_a: Issues from the first (older) crawl run.
            issues_b: Issues from the second (newer) crawl run.

        Returns:
            DiffResult with added, resolved, and changed issues.
        """
        # Build index by issue key for both sets
        index_a = {issue.issue_key: issue for issue in issues_a}
        index_b = {issue.issue_key: issue for issue in issues_b}

        keys_a = set(index_a.keys())
        keys_b = set(index_b.keys())

        # Find added issues (in B but not A)
        added_keys = keys_b - keys_a
        added = [index_b[key] for key in added_keys]

        # Find resolved issues (in A but not B)
        resolved_keys = keys_a - keys_b
        resolved = [index_a[key] for key in resolved_keys]

        # Find changed issues (same key but different attributes)
        common_keys = keys_a & keys_b
        changed: list[ChangedIssue] = []

        for key in common_keys:
            issue_a = index_a[key]
            issue_b = index_b[key]

            severity_changed = issue_a.severity != issue_b.severity
            confidence_changed = issue_a.confidence != issue_b.confidence

            if severity_changed or confidence_changed:
                changed.append(
                    ChangedIssue(
                        before=issue_a,
                        after=issue_b,
                        severity_changed=severity_changed,
                        confidence_changed=confidence_changed,
                    )
                )

        return DiffResult(
            added=added,
            resolved=resolved,
            changed=changed,
        )
