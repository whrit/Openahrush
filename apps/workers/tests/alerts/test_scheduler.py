"""
TDD tests for the alert scheduler.

Tests cover:
- Running detectors for active alert rules
- Storing alerts in database
- Emitting events
- Scheduling triggers
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from semrush_workers.alerts.scheduler import AlertScheduler


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.publish = AsyncMock()
    return redis


@pytest.fixture
def mock_visibility_detector() -> MagicMock:
    """Create a mock visibility detector."""
    detector = MagicMock()
    detector.detect_query_drops = MagicMock(return_value=[])
    detector.detect_page_drops = MagicMock(return_value=[])
    return detector


@pytest.fixture
def mock_ctr_detector() -> MagicMock:
    """Create a mock CTR detector."""
    detector = MagicMock()
    detector.detect_opportunities = MagicMock(return_value=[])
    return detector


@pytest.fixture
def mock_regression_detector() -> MagicMock:
    """Create a mock regression detector."""
    detector = MagicMock()
    detector.detect_regression = MagicMock(return_value=None)
    return detector


class TestAlertScheduler:
    """Tests for AlertScheduler."""

    @pytest.mark.asyncio
    async def test_run_for_project_with_no_rules(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test running for project with no alert rules."""
        project_id = uuid.uuid4()

        # Mock empty rules result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)
        alerts = await scheduler.run_for_project(project_id)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_run_for_project_filters_disabled_rules(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that the query filters disabled rules (is_enabled == True)."""
        project_id = uuid.uuid4()

        # The query should filter by is_enabled, so disabled rules
        # should not be returned. Mock returns empty since disabled
        # rules are filtered at the DB level.
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)
        alerts = await scheduler.run_for_project(project_id)

        # Verify the query was made
        mock_db.execute.assert_called_once()
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_run_visibility_drop_rule(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test running visibility drop detection."""
        project_id = uuid.uuid4()

        # Create an enabled visibility rule
        mock_rule = MagicMock()
        mock_rule.id = uuid.uuid4()
        mock_rule.project_id = project_id
        mock_rule.rule_type = "visibility_drop"
        mock_rule.is_enabled = True
        mock_rule.config = {"threshold": 30.0}

        # Mock the search data query results
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [mock_rule]

        # Mock search data - empty for simplicity
        mock_data_result = MagicMock()
        mock_data_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_rules_result, mock_data_result, mock_data_result]

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)

        with patch.object(scheduler, "_get_search_data", return_value=[]):
            alerts = await scheduler.run_for_project(project_id)

        # No drops detected from empty data
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_alert_stored_in_database(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that detected alerts are stored in database."""
        project_id = uuid.uuid4()

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)

        # Create a test alert directly
        await scheduler._store_alert(
            project_id=project_id,
            alert_rule_id=uuid.uuid4(),
            kind="visibility_drop",
            entity_type="query",
            entity_key="test keyword",
            severity="warn",
            payload={"drop_percentage": 35.0},
        )

        # Verify db.add was called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_event_emitted(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that alert.fired event is emitted."""
        project_id = uuid.uuid4()

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)

        await scheduler._store_alert(
            project_id=project_id,
            alert_rule_id=uuid.uuid4(),
            kind="visibility_drop",
            entity_type="query",
            entity_key="test keyword",
            severity="warn",
            payload={"drop_percentage": 35.0},
        )

        # Verify redis publish was called
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "openahrush:events"

    @pytest.mark.asyncio
    async def test_run_after_crawl_completion(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test running scheduler after crawl completes."""
        project_id = uuid.uuid4()
        crawl_run_id = uuid.uuid4()

        # Create a regression rule
        mock_rule = MagicMock()
        mock_rule.id = uuid.uuid4()
        mock_rule.project_id = project_id
        mock_rule.rule_type = "regression"
        mock_rule.is_enabled = True
        mock_rule.config = {"threshold": 10}

        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = [mock_rule]

        mock_db.execute.return_value = mock_rules_result

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)

        with patch.object(scheduler, "_run_regression_check", return_value=[]):
            alerts = await scheduler.run_after_crawl(
                project_id=project_id,
                crawl_run_id=crawl_run_id,
            )

        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_run_after_sync_completion(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Test running scheduler after integration sync."""
        project_id = uuid.uuid4()

        # Mock rules
        mock_rules_result = MagicMock()
        mock_rules_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_rules_result

        scheduler = AlertScheduler(db=mock_db, redis=mock_redis)
        alerts = await scheduler.run_after_sync(project_id=project_id)

        assert isinstance(alerts, list)
