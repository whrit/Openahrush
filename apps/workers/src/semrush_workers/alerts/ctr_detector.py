"""
CTR opportunity detector for search queries.

Identifies high-impression queries with CTR below expected
based on their search position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Expected CTR curve based on position
# Based on industry averages
EXPECTED_CTR_CURVE = {
    1: 30.0,  # Position 1: ~30% CTR
    2: 15.0,  # Position 2: ~15% CTR
    3: 10.0,  # Position 3: ~10% CTR
    4: 7.0,   # Position 4: ~7% CTR
    5: 5.0,   # Position 5: ~5% CTR
    6: 4.0,   # Position 6: ~4% CTR
    7: 3.5,   # Position 7: ~3.5% CTR
    8: 3.0,   # Position 8: ~3% CTR
    9: 2.5,   # Position 9: ~2.5% CTR
    10: 2.0,  # Position 10: ~2% CTR
}


@dataclass
class CTROpportunity:
    """
    Represents a CTR improvement opportunity.

    Attributes:
        query: The search query.
        page_url: URL of the ranking page.
        impressions: Number of impressions.
        clicks: Number of clicks.
        actual_ctr: Actual CTR percentage.
        expected_ctr: Expected CTR based on position.
        position: Average search position.
    """

    query: str
    page_url: str
    impressions: int
    clicks: int
    actual_ctr: float
    expected_ctr: float
    position: float

    @property
    def ctr_gap(self) -> float:
        """
        Calculate the CTR gap.

        Returns:
            Difference between expected and actual CTR.
        """
        return round(self.expected_ctr - self.actual_ctr, 1)

    @property
    def potential_clicks(self) -> int:
        """
        Calculate potential additional clicks.

        Returns:
            Number of clicks that could be gained.
        """
        return int((self.ctr_gap / 100) * self.impressions)

    @property
    def severity(self) -> str:
        """
        Get alert severity.

        CTR opportunities are always info-level.

        Returns:
            'info' severity level.
        """
        return "info"

    def to_alert_payload(self) -> dict[str, Any]:
        """
        Convert to alert payload format.

        Returns:
            Dictionary with opportunity details.
        """
        return {
            "impressions": self.impressions,
            "clicks": self.clicks,
            "actual_ctr": self.actual_ctr,
            "expected_ctr": self.expected_ctr,
            "position": self.position,
            "ctr_gap": self.ctr_gap,
            "potential_clicks": self.potential_clicks,
        }


class CTRDetector:
    """
    Detector for CTR improvement opportunities.

    Identifies queries where actual CTR is significantly
    below expected CTR based on position.

    Attributes:
        min_impressions: Minimum impressions to consider (default 100).
        ctr_gap_threshold: Minimum CTR gap to flag (default 5%).
    """

    def __init__(
        self,
        min_impressions: int = 100,
        ctr_gap_threshold: float = 5.0,
    ) -> None:
        """
        Initialize the detector.

        Args:
            min_impressions: Minimum impressions to consider.
            ctr_gap_threshold: Minimum CTR gap to flag opportunity.
        """
        self.min_impressions = min_impressions
        self.ctr_gap_threshold = ctr_gap_threshold

    def get_expected_ctr(self, position: float) -> float:
        """
        Get expected CTR based on position.

        Uses a lookup table with interpolation for
        fractional positions.

        Args:
            position: Average search position.

        Returns:
            Expected CTR percentage.
        """
        if position <= 0:
            return 0.0

        # For positions beyond 10, use a low baseline
        if position > 10:
            return max(1.0, 2.0 - (position - 10) * 0.1)

        # Get the position as integer for lookup
        pos_floor = int(position)
        pos_ceil = pos_floor + 1

        # Get CTR values for interpolation
        ctr_floor = EXPECTED_CTR_CURVE.get(pos_floor, 2.0)
        ctr_ceil = EXPECTED_CTR_CURVE.get(pos_ceil, 2.0)

        # Linear interpolation
        fraction = position - pos_floor
        expected = ctr_floor + (ctr_ceil - ctr_floor) * fraction

        return round(expected, 1)

    def detect_opportunities(
        self,
        data: list[dict[str, Any]],
    ) -> list[CTROpportunity]:
        """
        Detect CTR improvement opportunities.

        Args:
            data: List of query data with keys:
                - query: Search query
                - page_url: Ranking page URL
                - impressions: Number of impressions
                - clicks: Number of clicks
                - ctr: CTR percentage
                - position: Average position

        Returns:
            List of detected opportunities.
        """
        opportunities: list[CTROpportunity] = []

        for item in data:
            impressions = item.get("impressions", 0)

            # Filter low-volume queries
            if impressions < self.min_impressions:
                continue

            position = item.get("position", 0)
            if position <= 0:
                continue

            actual_ctr = item.get("ctr", 0)
            expected_ctr = self.get_expected_ctr(position)

            # Check if there's a significant gap
            ctr_gap = expected_ctr - actual_ctr

            if ctr_gap >= self.ctr_gap_threshold:
                opportunities.append(
                    CTROpportunity(
                        query=item.get("query", ""),
                        page_url=item.get("page_url", ""),
                        impressions=impressions,
                        clicks=item.get("clicks", 0),
                        actual_ctr=actual_ctr,
                        expected_ctr=expected_ctr,
                        position=position,
                    )
                )

        # Sort by potential clicks (highest first)
        opportunities.sort(key=lambda o: o.potential_clicks, reverse=True)

        return opportunities
