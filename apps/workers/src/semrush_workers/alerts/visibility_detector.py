"""
Visibility drop detector for search traffic.

Compares recent 7 days vs previous 7 days to detect
significant visibility drops at query and page levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class VisibilityDrop:
    """
    Represents a detected visibility drop.

    Attributes:
        entity_type: Type of entity ('query' or 'page').
        entity_key: The query or page URL.
        previous_impressions: Impressions in previous period.
        current_impressions: Impressions in current period.
        drop_percentage: Percentage drop in impressions.
    """

    entity_type: str
    entity_key: str
    previous_impressions: int
    current_impressions: int
    drop_percentage: float

    @property
    def severity(self) -> str:
        """
        Determine severity based on magnitude.

        Returns:
            'critical' for >= 50% drop, 'warn' otherwise.
        """
        if self.drop_percentage >= 50.0:
            return "critical"
        return "warn"

    def to_alert_payload(self) -> dict[str, Any]:
        """
        Convert to alert payload format.

        Returns:
            Dictionary with drop details.
        """
        return {
            "previous_impressions": self.previous_impressions,
            "current_impressions": self.current_impressions,
            "drop_percentage": self.drop_percentage,
        }


class VisibilityDetector:
    """
    Detector for visibility drops in search traffic.

    Compares impressions between periods and flags
    significant drops above the configured threshold.

    Attributes:
        threshold_percent: Minimum drop percentage to trigger (default 30%).
    """

    def __init__(self, threshold_percent: float = 30.0) -> None:
        """
        Initialize the detector.

        Args:
            threshold_percent: Minimum drop percentage to trigger alert.
        """
        self.threshold_percent = threshold_percent

    def detect_query_drops(
        self,
        previous_data: list[dict[str, Any]],
        current_data: list[dict[str, Any]],
    ) -> list[VisibilityDrop]:
        """
        Detect visibility drops at the query level.

        Args:
            previous_data: Aggregated data for previous period.
                Each item should have 'query' and 'impressions'.
            current_data: Aggregated data for current period.
                Each item should have 'query' and 'impressions'.

        Returns:
            List of detected visibility drops.
        """
        return self._detect_drops(
            previous_data,
            current_data,
            key_field="query",
            entity_type="query",
        )

    def detect_page_drops(
        self,
        previous_data: list[dict[str, Any]],
        current_data: list[dict[str, Any]],
    ) -> list[VisibilityDrop]:
        """
        Detect visibility drops at the page level.

        Args:
            previous_data: Aggregated data for previous period.
                Each item should have 'page_url' and 'impressions'.
            current_data: Aggregated data for current period.
                Each item should have 'page_url' and 'impressions'.

        Returns:
            List of detected visibility drops.
        """
        return self._detect_drops(
            previous_data,
            current_data,
            key_field="page_url",
            entity_type="page",
        )

    def _detect_drops(
        self,
        previous_data: list[dict[str, Any]],
        current_data: list[dict[str, Any]],
        key_field: str,
        entity_type: str,
    ) -> list[VisibilityDrop]:
        """
        Internal method to detect drops for any entity type.

        Args:
            previous_data: Data for previous period.
            current_data: Data for current period.
            key_field: Field name to use as entity key.
            entity_type: Type of entity for results.

        Returns:
            List of detected visibility drops.
        """
        # Build index of previous impressions
        previous_index: dict[str, int] = {}
        for item in previous_data:
            key = item.get(key_field)
            if key is not None:
                previous_index[key] = (
                    previous_index.get(key, 0) + item.get("impressions", 0)
                )

        # Build index of current impressions
        current_index: dict[str, int] = {}
        for item in current_data:
            key = item.get(key_field)
            if key is not None:
                current_index[key] = (
                    current_index.get(key, 0) + item.get("impressions", 0)
                )

        drops: list[VisibilityDrop] = []

        # Check each entity from previous period
        for key, prev_impressions in previous_index.items():
            if prev_impressions <= 0:
                continue

            curr_impressions = current_index.get(key, 0)

            # Calculate drop percentage
            drop_pct = ((prev_impressions - curr_impressions) / prev_impressions) * 100

            # Check if drop exceeds threshold
            if drop_pct >= self.threshold_percent:
                drops.append(
                    VisibilityDrop(
                        entity_type=entity_type,
                        entity_key=key,
                        previous_impressions=prev_impressions,
                        current_impressions=curr_impressions,
                        drop_percentage=round(drop_pct, 1),
                    )
                )

        return drops

    def aggregate_by_key(
        self,
        data: list[dict[str, Any]],
        key_field: str,
    ) -> list[dict[str, Any]]:
        """
        Aggregate data by a key field.

        Sums impressions for each unique key value.

        Args:
            data: Raw data with multiple rows per key.
            key_field: Field to group by.

        Returns:
            Aggregated data with one row per key.
        """
        totals: dict[str, int] = {}

        for item in data:
            key = item.get(key_field)
            if key is not None:
                totals[key] = totals.get(key, 0) + item.get("impressions", 0)

        return [
            {key_field: key, "impressions": impressions}
            for key, impressions in totals.items()
        ]
