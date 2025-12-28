"""
Impact score computation for SEO issues.

Computes impact_score = severity * confidence * traffic_weight
for all issue instances in a crawl run.

Handles pages without traffic data gracefully by using a default weight.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from semrush_workers.rules.models import IssueInstance, IssueSeverity
from semrush_workers.scoring.traffic_weight import (
    DEFAULT_WEIGHT,
    get_traffic_weights_for_project,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def normalize_url(url: str) -> str:
    """
    Normalize a URL for matching.

    - Removes trailing slashes
    - Lowercases scheme and host (preserves path case)

    Args:
        url: URL to normalize.

    Returns:
        Normalized URL string.
    """
    parsed = urlparse(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove trailing slash from path
    path = parsed.path.rstrip("/") if parsed.path != "/" else ""

    # Reconstruct URL
    normalized = f"{scheme}://{netloc}{path}"

    # Add query string if present
    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def compute_impact_score(
    severity: IssueSeverity,
    confidence: float,
    traffic_weight: float | None,
) -> float:
    """
    Compute impact score for a single issue.

    Formula: impact_score = severity * confidence * traffic_weight

    Args:
        severity: Issue severity level (2-5).
        confidence: Confidence score (0.0-1.0).
        traffic_weight: Traffic weight (0.0-1.0), or None for default.

    Returns:
        Computed impact score.
    """
    weight = traffic_weight if traffic_weight is not None else DEFAULT_WEIGHT
    return severity.value * confidence * weight


async def compute_impact_scores(
    session: AsyncSession,
    crawl_run_id: uuid.UUID,
    project_id: uuid.UUID,
    issues: list[IssueInstance],
) -> list[IssueInstance]:
    """
    Compute and assign impact scores to all issues.

    Queries traffic data for the project and computes scores
    for each issue based on the formula:

        impact_score = severity * confidence * traffic_weight

    Args:
        session: Database session.
        crawl_run_id: ID of the crawl run.
        project_id: ID of the project.
        issues: List of issue instances to score.

    Returns:
        List of issues with impact_score populated.
    """
    if not issues:
        return []

    # Get traffic weights for all pages in the project
    traffic_weights = await get_traffic_weights_for_project(
        session, project_id, days=28
    )

    # Compute impact scores for each issue
    for issue in issues:
        normalized_url = normalize_url(issue.affected_url)

        # Get traffic weight, falling back to default
        weight = traffic_weights.get(normalized_url)
        if weight is None:
            # Try without normalization as fallback
            weight = traffic_weights.get(issue.affected_url, DEFAULT_WEIGHT)

        issue.impact_score = compute_impact_score(
            severity=issue.severity,
            confidence=issue.confidence,
            traffic_weight=weight,
        )

    return issues


async def update_issue_impact_scores(
    session: AsyncSession,
    crawl_run_id: uuid.UUID,
    project_id: uuid.UUID,
) -> int:
    """
    Update impact scores for all issues in a crawl run.

    Queries issues from the database, computes scores, and updates them.

    Args:
        session: Database session.
        crawl_run_id: ID of the crawl run.
        project_id: ID of the project.

    Returns:
        Number of issues updated.
    """
    from sqlalchemy import text

    # Get traffic weights
    traffic_weights = await get_traffic_weights_for_project(
        session, project_id, days=28
    )

    # Query issues for this crawl run
    query = text("""
        SELECT
            ii.id,
            ii.affected_url,
            it.severity,
            ii.confidence
        FROM issue_instances ii
        JOIN issue_types it ON ii.issue_type_id = it.id
        WHERE ii.crawl_run_id = :crawl_run_id
    """)

    result = await session.execute(query, {"crawl_run_id": crawl_run_id})
    rows = result.fetchall()

    if not rows:
        return 0

    # Compute and update scores
    updates = []
    for row in rows:
        issue_id = row[0]
        affected_url = row[1]
        severity = row[2]
        confidence = row[3]

        # Get traffic weight
        normalized_url = normalize_url(affected_url)
        weight = traffic_weights.get(normalized_url)
        if weight is None:
            weight = traffic_weights.get(affected_url, DEFAULT_WEIGHT)

        # Compute score
        impact_score = severity * confidence * weight
        updates.append((impact_score, issue_id))

    # Batch update
    if updates:
        update_query = text("""
            UPDATE issue_instances
            SET impact_score = :impact_score
            WHERE id = :issue_id
        """)

        for impact_score, issue_id in updates:
            await session.execute(
                update_query,
                {"impact_score": impact_score, "issue_id": issue_id},
            )

    return len(updates)
