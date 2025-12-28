"""
Traffic weight computation for impact scoring.

Queries search_fact_daily and analytics_fact_daily tables to compute
a normalized traffic weight (0-1) for each page URL.

Formula:
    raw_weight = impressions * 0.3 + clicks * 0.3 + sessions * 0.2 + conversions * 0.2
    normalized_weight = (raw_weight - min) / (max - min)

Falls back to 0.5 if no data exists for a page.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Weight coefficients for different metrics
WEIGHT_IMPRESSIONS = 0.3
WEIGHT_CLICKS = 0.3
WEIGHT_SESSIONS = 0.2
WEIGHT_CONVERSIONS = 0.2

# Default weight when no data exists
DEFAULT_WEIGHT = 0.5


@dataclass
class TrafficMetrics:
    """
    Aggregated traffic metrics for a page.

    Attributes:
        impressions: Search impressions from GSC/BWT.
        clicks: Search clicks from GSC/BWT.
        sessions: Sessions from GA4.
        conversions: Conversions from GA4.
    """

    impressions: int = 0
    clicks: int = 0
    sessions: int = 0
    conversions: int = 0


def normalize_weight(value: float, min_val: float, max_val: float) -> float:
    """
    Normalize a value to 0-1 scale.

    Args:
        value: Raw weight value.
        min_val: Minimum value in dataset.
        max_val: Maximum value in dataset.

    Returns:
        Normalized weight between 0 and 1.
    """
    if max_val == min_val:
        return 0.5

    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def compute_traffic_weight(metrics: TrafficMetrics) -> float:
    """
    Compute raw traffic weight from metrics.

    Formula:
        weight = impressions * 0.3 + clicks * 0.3 + sessions * 0.2 + conversions * 0.2

    Args:
        metrics: Aggregated traffic metrics.

    Returns:
        Raw (unnormalized) traffic weight.
    """
    return (
        metrics.impressions * WEIGHT_IMPRESSIONS
        + metrics.clicks * WEIGHT_CLICKS
        + metrics.sessions * WEIGHT_SESSIONS
        + metrics.conversions * WEIGHT_CONVERSIONS
    )


async def get_traffic_weights_for_project(
    session: AsyncSession,
    project_id: uuid.UUID,
    days: int = 28,
) -> dict[str, float]:
    """
    Get normalized traffic weights for all pages in a project.

    Queries both search_fact_daily and analytics_fact_daily tables
    for the last N days and computes normalized weights.

    Args:
        session: Database session.
        project_id: Project UUID.
        days: Number of days to aggregate (default 28).

    Returns:
        Dictionary mapping page_url to normalized weight (0-1).
        Empty dict if no data exists.
    """
    # Calculate date range
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days)

    # Aggregate metrics by page URL
    page_metrics: dict[str, TrafficMetrics] = {}

    # Query search_fact_daily for impressions and clicks
    search_query = text("""
        SELECT page_url, SUM(impressions) as total_impressions, SUM(clicks) as total_clicks
        FROM search_fact_daily
        WHERE project_id = :project_id
          AND date >= :start_date
          AND date <= :end_date
          AND page_url IS NOT NULL
        GROUP BY page_url
    """)

    search_result = await session.execute(
        search_query,
        {"project_id": project_id, "start_date": start_date, "end_date": end_date},
    )

    for row in search_result.fetchall():
        page_url = row[0]
        impressions = int(row[1] or 0)
        clicks = int(row[2] or 0)

        if page_url not in page_metrics:
            page_metrics[page_url] = TrafficMetrics()

        page_metrics[page_url].impressions = impressions
        page_metrics[page_url].clicks = clicks

    # Query analytics_fact_daily for sessions and conversions
    analytics_query = text("""
        SELECT page_url, SUM(sessions) as total_sessions, SUM(conversions) as total_conversions
        FROM analytics_fact_daily
        WHERE project_id = :project_id
          AND date >= :start_date
          AND date <= :end_date
          AND page_url IS NOT NULL
        GROUP BY page_url
    """)

    analytics_result = await session.execute(
        analytics_query,
        {"project_id": project_id, "start_date": start_date, "end_date": end_date},
    )

    for row in analytics_result.fetchall():
        page_url = row[0]
        sessions = int(row[1] or 0)
        conversions = int(row[2] or 0)

        if page_url not in page_metrics:
            page_metrics[page_url] = TrafficMetrics()

        page_metrics[page_url].sessions = sessions
        page_metrics[page_url].conversions = conversions

    # If no data, return empty dict
    if not page_metrics:
        return {}

    # Compute raw weights
    raw_weights: dict[str, float] = {}
    for url, metrics in page_metrics.items():
        raw_weights[url] = compute_traffic_weight(metrics)

    # Normalize weights
    if raw_weights:
        min_weight = min(raw_weights.values())
        max_weight = max(raw_weights.values())

        normalized_weights: dict[str, float] = {}
        for url, raw in raw_weights.items():
            normalized_weights[url] = normalize_weight(raw, min_weight, max_weight)

        return normalized_weights

    return {}


def get_default_weight() -> float:
    """
    Get the default weight for pages with no traffic data.

    Returns:
        Default weight (0.5).
    """
    return DEFAULT_WEIGHT
