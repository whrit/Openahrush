"""
Diff engine for comparing issues between crawl runs.

Provides functionality to:
- Compare issues between two crawl runs
- Find new issues (added)
- Find resolved issues (removed)
- Find changed issues (severity/confidence changed)
"""

from semrush_workers.diff.diff_engine import (
    ChangedIssue,
    DiffEngine,
    DiffResult,
    IssueData,
)

__all__ = [
    "DiffEngine",
    "DiffResult",
    "IssueData",
    "ChangedIssue",
]
