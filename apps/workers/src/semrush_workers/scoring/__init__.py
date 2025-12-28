"""
Scoring module for impact score computation.

Provides:
- Traffic weight calculation from search/analytics data
- Impact score computation for issues
"""

from semrush_workers.scoring.impact import compute_impact_scores
from semrush_workers.scoring.traffic_weight import (
    TrafficMetrics,
    compute_traffic_weight,
    get_traffic_weights_for_project,
    normalize_weight,
)

__all__ = [
    "TrafficMetrics",
    "compute_traffic_weight",
    "get_traffic_weights_for_project",
    "normalize_weight",
    "compute_impact_scores",
]
