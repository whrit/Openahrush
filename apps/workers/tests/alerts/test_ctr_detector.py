"""
TDD tests for the CTR opportunity detector.

Tests cover:
- Detecting queries with CTR below expected curve
- Position-based expected CTR calculation
- High-impression filtering
- Edge cases
"""



from semrush_workers.alerts.ctr_detector import (
    CTRDetector,
    CTROpportunity,
)


class TestCTROpportunityDataclass:
    """Tests for CTROpportunity dataclass."""

    def test_ctr_gap_calculation(self) -> None:
        """Test CTR gap is calculated correctly."""
        opportunity = CTROpportunity(
            query="example keyword",
            page_url="https://example.com/page",
            impressions=1000,
            clicks=50,
            actual_ctr=5.0,
            expected_ctr=30.0,
            position=1.0,
        )
        assert opportunity.ctr_gap == 25.0

    def test_potential_clicks_calculation(self) -> None:
        """Test potential clicks is calculated correctly."""
        opportunity = CTROpportunity(
            query="example keyword",
            page_url="https://example.com/page",
            impressions=1000,
            clicks=50,
            actual_ctr=5.0,
            expected_ctr=30.0,
            position=1.0,
        )
        # Expected: (30% - 5%) * 1000 = 250 potential clicks
        assert opportunity.potential_clicks == 250

    def test_severity_is_info(self) -> None:
        """Test that CTR opportunities have info severity."""
        opportunity = CTROpportunity(
            query="example keyword",
            page_url="https://example.com/page",
            impressions=1000,
            clicks=50,
            actual_ctr=5.0,
            expected_ctr=30.0,
            position=1.0,
        )
        assert opportunity.severity == "info"


class TestCTRDetector:
    """Tests for CTRDetector."""

    def test_expected_ctr_position_1(self) -> None:
        """Test expected CTR for position 1 is ~30%."""
        detector = CTRDetector()
        expected = detector.get_expected_ctr(1.0)
        assert abs(expected - 30.0) < 5.0  # Allow some margin

    def test_expected_ctr_position_2(self) -> None:
        """Test expected CTR for position 2 is ~15%."""
        detector = CTRDetector()
        expected = detector.get_expected_ctr(2.0)
        assert abs(expected - 15.0) < 5.0

    def test_expected_ctr_position_3(self) -> None:
        """Test expected CTR for position 3 is ~10%."""
        detector = CTRDetector()
        expected = detector.get_expected_ctr(3.0)
        assert abs(expected - 10.0) < 3.0

    def test_expected_ctr_positions_4_to_10(self) -> None:
        """Test expected CTR for positions 4-10 is ~5%."""
        detector = CTRDetector()
        for pos in [4.0, 5.0, 7.0, 10.0]:
            expected = detector.get_expected_ctr(pos)
            assert expected <= 10.0
            assert expected >= 2.0

    def test_expected_ctr_beyond_10(self) -> None:
        """Test expected CTR for positions beyond 10 is low."""
        detector = CTRDetector()
        expected = detector.get_expected_ctr(15.0)
        assert expected <= 3.0

    def test_detect_opportunity_low_ctr(self) -> None:
        """Test detecting a query with CTR below expected."""
        data = [
            {
                "query": "example keyword",
                "page_url": "https://example.com/page",
                "impressions": 1000,
                "clicks": 50,
                "ctr": 5.0,  # 5% actual
                "position": 1.5,  # Should expect ~25%
            }
        ]

        detector = CTRDetector(min_impressions=100)
        opportunities = detector.detect_opportunities(data)

        assert len(opportunities) == 1
        assert opportunities[0].query == "example keyword"
        assert opportunities[0].ctr_gap > 15.0

    def test_no_opportunity_when_ctr_is_good(self) -> None:
        """Test that good CTR is not flagged."""
        data = [
            {
                "query": "example keyword",
                "page_url": "https://example.com/page",
                "impressions": 1000,
                "clicks": 280,
                "ctr": 28.0,  # 28% actual
                "position": 1.0,  # Expects ~30%
            }
        ]

        detector = CTRDetector(min_impressions=100)
        opportunities = detector.detect_opportunities(data)

        assert len(opportunities) == 0

    def test_filter_low_impressions(self) -> None:
        """Test that low impression queries are filtered out."""
        data = [
            {
                "query": "low volume keyword",
                "page_url": "https://example.com/page",
                "impressions": 50,  # Below threshold
                "clicks": 1,
                "ctr": 2.0,
                "position": 1.0,
            }
        ]

        detector = CTRDetector(min_impressions=100)
        opportunities = detector.detect_opportunities(data)

        assert len(opportunities) == 0

    def test_multiple_opportunities(self) -> None:
        """Test detecting multiple CTR opportunities."""
        data = [
            {
                "query": "keyword1",
                "page_url": "https://example.com/page1",
                "impressions": 1000,
                "clicks": 50,
                "ctr": 5.0,
                "position": 1.0,  # Expects 30%, has 5% = opportunity
            },
            {
                "query": "keyword2",
                "page_url": "https://example.com/page2",
                "impressions": 800,
                "clicks": 200,
                "ctr": 25.0,
                "position": 1.5,  # Expects ~25%, has 25% = no opportunity
            },
            {
                "query": "keyword3",
                "page_url": "https://example.com/page3",
                "impressions": 500,
                "clicks": 15,
                "ctr": 3.0,
                "position": 3.0,  # Expects ~10%, has 3% = opportunity
            },
        ]

        detector = CTRDetector(min_impressions=100)
        opportunities = detector.detect_opportunities(data)

        assert len(opportunities) == 2
        queries = {o.query for o in opportunities}
        assert "keyword1" in queries
        assert "keyword3" in queries

    def test_empty_data(self) -> None:
        """Test handling of empty data."""
        detector = CTRDetector()
        opportunities = detector.detect_opportunities([])
        assert len(opportunities) == 0

    def test_custom_min_impressions(self) -> None:
        """Test using custom minimum impressions threshold."""
        data = [
            {
                "query": "keyword",
                "page_url": "https://example.com/page",
                "impressions": 75,
                "clicks": 3,
                "ctr": 4.0,
                "position": 1.0,
            }
        ]

        # Default threshold (100) - filtered out
        detector_high = CTRDetector(min_impressions=100)
        assert len(detector_high.detect_opportunities(data)) == 0

        # Lower threshold (50) - detected
        detector_low = CTRDetector(min_impressions=50)
        assert len(detector_low.detect_opportunities(data)) == 1

    def test_to_alert_payload(self) -> None:
        """Test converting opportunity to alert payload."""
        opportunity = CTROpportunity(
            query="example keyword",
            page_url="https://example.com/page",
            impressions=1000,
            clicks=50,
            actual_ctr=5.0,
            expected_ctr=30.0,
            position=1.0,
        )

        payload = opportunity.to_alert_payload()

        assert payload["impressions"] == 1000
        assert payload["clicks"] == 50
        assert payload["actual_ctr"] == 5.0
        assert payload["expected_ctr"] == 30.0
        assert payload["position"] == 1.0
        assert payload["ctr_gap"] == 25.0
        assert payload["potential_clicks"] == 250
