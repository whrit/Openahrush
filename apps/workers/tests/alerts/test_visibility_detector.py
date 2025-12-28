"""
TDD tests for the visibility drop detector.

Tests cover:
- Detecting visibility drops at query and page level
- Threshold-based triggering
- Severity determination based on magnitude
- Edge cases (empty data, no drops)
"""

from datetime import date, timedelta
from typing import Any

from semrush_workers.alerts.visibility_detector import (
    VisibilityDetector,
    VisibilityDrop,
)


class TestVisibilityDropDataclass:
    """Tests for VisibilityDrop dataclass."""

    def test_severity_critical_for_large_drop(self) -> None:
        """Test that severity is critical for >= 50% drop."""
        drop = VisibilityDrop(
            entity_type="query",
            entity_key="example keyword",
            previous_impressions=1000,
            current_impressions=400,
            drop_percentage=60.0,
        )
        assert drop.severity == "critical"

    def test_severity_warn_for_moderate_drop(self) -> None:
        """Test that severity is warn for < 50% drop."""
        drop = VisibilityDrop(
            entity_type="query",
            entity_key="example keyword",
            previous_impressions=1000,
            current_impressions=650,
            drop_percentage=35.0,
        )
        assert drop.severity == "warn"


class TestVisibilityDetector:
    """Tests for VisibilityDetector."""

    def test_detect_query_level_drop(self) -> None:
        """Test detecting visibility drops at query level."""
        # Previous period: 1000 impressions
        # Current period: 500 impressions (50% drop)
        previous_data = [
            {
                "query": "example keyword",
                "impressions": 1000,
            }
        ]
        current_data = [
            {
                "query": "example keyword",
                "impressions": 500,
            }
        ]

        detector = VisibilityDetector(threshold_percent=30.0)
        drops = detector.detect_query_drops(previous_data, current_data)

        assert len(drops) == 1
        assert drops[0].entity_type == "query"
        assert drops[0].entity_key == "example keyword"
        assert drops[0].drop_percentage == 50.0
        assert drops[0].severity == "critical"

    def test_detect_page_level_drop(self) -> None:
        """Test detecting visibility drops at page level."""
        previous_data = [
            {
                "page_url": "https://example.com/page1",
                "impressions": 2000,
            }
        ]
        current_data = [
            {
                "page_url": "https://example.com/page1",
                "impressions": 1200,
            }
        ]

        detector = VisibilityDetector(threshold_percent=30.0)
        drops = detector.detect_page_drops(previous_data, current_data)

        assert len(drops) == 1
        assert drops[0].entity_type == "page"
        assert drops[0].entity_key == "https://example.com/page1"
        assert drops[0].drop_percentage == 40.0
        assert drops[0].severity == "warn"

    def test_no_drop_below_threshold(self) -> None:
        """Test that drops below threshold are not detected."""
        previous_data = [{"query": "keyword", "impressions": 1000}]
        current_data = [{"query": "keyword", "impressions": 800}]  # 20% drop

        detector = VisibilityDetector(threshold_percent=30.0)
        drops = detector.detect_query_drops(previous_data, current_data)

        assert len(drops) == 0

    def test_no_drop_when_impressions_increase(self) -> None:
        """Test that increases are not flagged as drops."""
        previous_data = [{"query": "keyword", "impressions": 500}]
        current_data = [{"query": "keyword", "impressions": 800}]

        detector = VisibilityDetector(threshold_percent=30.0)
        drops = detector.detect_query_drops(previous_data, current_data)

        assert len(drops) == 0

    def test_empty_previous_data(self) -> None:
        """Test handling of empty previous data."""
        previous_data: list[dict[str, Any]] = []
        current_data = [{"query": "keyword", "impressions": 1000}]

        detector = VisibilityDetector()
        drops = detector.detect_query_drops(previous_data, current_data)

        assert len(drops) == 0

    def test_empty_current_data(self) -> None:
        """Test handling when query disappears entirely."""
        previous_data = [{"query": "keyword", "impressions": 1000}]
        current_data: list[dict[str, Any]] = []

        detector = VisibilityDetector()
        drops = detector.detect_query_drops(previous_data, current_data)

        # Query disappeared = 100% drop
        assert len(drops) == 1
        assert drops[0].drop_percentage == 100.0
        assert drops[0].severity == "critical"

    def test_multiple_drops(self) -> None:
        """Test detecting multiple drops at once."""
        previous_data = [
            {"query": "keyword1", "impressions": 1000},
            {"query": "keyword2", "impressions": 500},
            {"query": "keyword3", "impressions": 200},
        ]
        current_data = [
            {"query": "keyword1", "impressions": 600},  # 40% drop
            {"query": "keyword2", "impressions": 450},  # 10% drop - below threshold
            {"query": "keyword3", "impressions": 100},  # 50% drop
        ]

        detector = VisibilityDetector(threshold_percent=30.0)
        drops = detector.detect_query_drops(previous_data, current_data)

        assert len(drops) == 2
        keywords_with_drops = {d.entity_key for d in drops}
        assert "keyword1" in keywords_with_drops
        assert "keyword3" in keywords_with_drops

    def test_custom_threshold(self) -> None:
        """Test using a custom threshold."""
        previous_data = [{"query": "keyword", "impressions": 1000}]
        current_data = [{"query": "keyword", "impressions": 850}]  # 15% drop

        # Default threshold (30%) - no drop detected
        detector_high = VisibilityDetector(threshold_percent=30.0)
        assert len(detector_high.detect_query_drops(previous_data, current_data)) == 0

        # Lower threshold (10%) - drop detected
        detector_low = VisibilityDetector(threshold_percent=10.0)
        assert len(detector_low.detect_query_drops(previous_data, current_data)) == 1

    def test_compare_periods_with_dates(self) -> None:
        """Test comparing data across date ranges."""
        today = date.today()
        week_ago = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)

        # Data for date ranges
        previous_period_data = [
            {"query": "keyword", "date": str(two_weeks_ago), "impressions": 200},
            {"query": "keyword", "date": str(two_weeks_ago + timedelta(days=1)), "impressions": 180},
        ]
        current_period_data = [
            {"query": "keyword", "date": str(week_ago), "impressions": 100},
            {"query": "keyword", "date": str(week_ago + timedelta(days=1)), "impressions": 80},
        ]

        # Aggregate by query
        detector = VisibilityDetector(threshold_percent=30.0)
        drops = detector.detect_query_drops(
            detector.aggregate_by_key(previous_period_data, "query"),
            detector.aggregate_by_key(current_period_data, "query"),
        )

        # Previous: 380 impressions, Current: 180 impressions = ~52% drop
        assert len(drops) == 1
        assert drops[0].drop_percentage > 50.0

    def test_to_alert_payload(self) -> None:
        """Test converting drop to alert payload."""
        drop = VisibilityDrop(
            entity_type="query",
            entity_key="example keyword",
            previous_impressions=1000,
            current_impressions=500,
            drop_percentage=50.0,
        )

        payload = drop.to_alert_payload()

        assert payload["previous_impressions"] == 1000
        assert payload["current_impressions"] == 500
        assert payload["drop_percentage"] == 50.0
