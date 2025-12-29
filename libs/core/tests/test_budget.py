"""
Tests for resource budget enforcement.

Uses TDD approach - tests are written first to define expected behavior.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest


class TestProjectBudgetModel:
    """Tests for the ProjectBudget database model."""

    def test_model_has_required_fields(self) -> None:
        from semrush_core.budget.models import ProjectBudget

        # Check that the model has the required columns
        columns = {col.name for col in ProjectBudget.__table__.columns}

        assert "id" in columns
        assert "project_id" in columns
        assert "monthly_crawl_page_limit" in columns
        assert "monthly_export_limit" in columns
        assert "crawl_pages_used" in columns
        assert "exports_used" in columns
        assert "period_start" in columns
        assert "period_end" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_model_has_project_relationship(self) -> None:
        from semrush_core.budget.models import ProjectBudget

        # Check relationship exists
        assert hasattr(ProjectBudget, "project")

    def test_model_has_default_limits(self) -> None:
        from semrush_core.budget.models import DEFAULT_MONTHLY_CRAWL_PAGES, DEFAULT_MONTHLY_EXPORTS

        assert DEFAULT_MONTHLY_CRAWL_PAGES == 10000
        assert DEFAULT_MONTHLY_EXPORTS == 100


class TestBudgetService:
    """Tests for budget enforcement service."""

    @pytest.mark.asyncio
    async def test_get_or_create_budget_creates_new_budget(self) -> None:
        from semrush_core.budget.service import BudgetService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        budget = await service.get_or_create_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        # Should have added a new budget
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_budget_returns_existing(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        # Create existing budget with is_period_expired returning False
        existing_budget = MagicMock(spec=ProjectBudget)
        existing_budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        budget = await service.get_or_create_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        assert budget == existing_budget
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_crawl_budget_allows_when_under_limit(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_crawl_page_limit = 10000
        budget.crawl_pages_used = 5000
        budget.crawl_usage_percentage = 50.0
        budget.crawl_pages_remaining = 5000
        budget.is_at_crawl_limit = False
        budget.should_warn_crawl = False
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_crawl_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
            pages_needed=100,
        )

        assert result.allowed is True
        assert result.warning is False

    @pytest.mark.asyncio
    async def test_check_crawl_budget_warns_at_80_percent(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_crawl_page_limit = 10000
        budget.crawl_pages_used = 8000
        budget.crawl_usage_percentage = 80.0
        budget.crawl_pages_remaining = 2000
        budget.is_at_crawl_limit = False
        budget.should_warn_crawl = True
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_crawl_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
            pages_needed=100,
        )

        assert result.allowed is True
        assert result.warning is True
        assert result.usage_percentage == 80.0

    @pytest.mark.asyncio
    async def test_check_crawl_budget_blocks_at_100_percent(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_crawl_page_limit = 10000
        budget.crawl_pages_used = 10000
        budget.crawl_usage_percentage = 100.0
        budget.crawl_pages_remaining = 0
        budget.is_at_crawl_limit = True
        budget.should_warn_crawl = True
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_crawl_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
            pages_needed=100,
        )

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_check_crawl_budget_blocks_when_would_exceed(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_crawl_page_limit = 10000
        budget.crawl_pages_used = 9900  # Only 100 remaining
        budget.crawl_pages_remaining = 100
        budget.is_at_crawl_limit = False
        budget.should_warn_crawl = True
        budget.crawl_usage_percentage = 99.0
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_crawl_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
            pages_needed=200,  # Needs 200 but only 100 remaining
        )

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_check_export_budget_allows_when_under_limit(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_export_limit = 100
        budget.exports_used = 50
        budget.export_usage_percentage = 50.0
        budget.exports_remaining = 50
        budget.is_at_export_limit = False
        budget.should_warn_export = False
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_export_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        assert result.allowed is True
        assert result.warning is False

    @pytest.mark.asyncio
    async def test_check_export_budget_warns_at_80_percent(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_export_limit = 100
        budget.exports_used = 80
        budget.export_usage_percentage = 80.0
        budget.exports_remaining = 20
        budget.is_at_export_limit = False
        budget.should_warn_export = True
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_export_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        assert result.allowed is True
        assert result.warning is True

    @pytest.mark.asyncio
    async def test_check_export_budget_blocks_at_100_percent(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.monthly_export_limit = 100
        budget.exports_used = 100
        budget.export_usage_percentage = 100.0
        budget.exports_remaining = 0
        budget.is_at_export_limit = True
        budget.should_warn_export = True
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        result = await service.check_export_budget(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_increment_crawl_usage_updates_count(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.crawl_pages_used = 5000
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        await service.increment_crawl_usage(
            session=mock_session,
            project_id=uuid.uuid4(),
            pages_crawled=100,
        )

        assert budget.crawl_pages_used == 5100
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_increment_export_usage_updates_count(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.exports_used = 50
        budget.is_period_expired.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        await service.increment_export_usage(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        assert budget.exports_used == 51
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_reset_budget_for_new_period(self) -> None:
        from semrush_core.budget.models import ProjectBudget
        from semrush_core.budget.service import BudgetService

        budget = MagicMock(spec=ProjectBudget)
        budget.crawl_pages_used = 5000
        budget.exports_used = 50
        budget.is_period_expired.return_value = False
        budget.period_start = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = budget

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        service = BudgetService()
        await service.reset_budget_for_new_period(
            session=mock_session,
            project_id=uuid.uuid4(),
        )

        assert budget.crawl_pages_used == 0
        assert budget.exports_used == 0


class TestBudgetCheckResult:
    """Tests for BudgetCheckResult dataclass."""

    def test_allowed_true_when_under_limit(self) -> None:
        from semrush_core.budget.service import BudgetCheckResult

        result = BudgetCheckResult(
            allowed=True,
            warning=False,
            usage_percentage=50.0,
            remaining=5000,
            limit=10000,
        )

        assert result.allowed is True
        assert result.warning is False

    def test_warning_true_at_80_percent(self) -> None:
        from semrush_core.budget.service import BudgetCheckResult

        result = BudgetCheckResult(
            allowed=True,
            warning=True,
            usage_percentage=80.0,
            remaining=2000,
            limit=10000,
        )

        assert result.allowed is True
        assert result.warning is True
        assert result.usage_percentage == 80.0

    def test_allowed_false_at_100_percent(self) -> None:
        from semrush_core.budget.service import BudgetCheckResult

        result = BudgetCheckResult(
            allowed=False,
            warning=True,
            usage_percentage=100.0,
            remaining=0,
            limit=10000,
        )

        assert result.allowed is False

    def test_to_headers_returns_budget_headers(self) -> None:
        from semrush_core.budget.service import BudgetCheckResult

        result = BudgetCheckResult(
            allowed=True,
            warning=True,
            usage_percentage=85.0,
            remaining=1500,
            limit=10000,
        )

        headers = result.to_headers()

        assert headers["X-Budget-Limit"] == "10000"
        assert headers["X-Budget-Remaining"] == "1500"
        assert headers["X-Budget-Warning"] == "true"

    def test_to_headers_no_warning_when_under_threshold(self) -> None:
        from semrush_core.budget.service import BudgetCheckResult

        result = BudgetCheckResult(
            allowed=True,
            warning=False,
            usage_percentage=50.0,
            remaining=5000,
            limit=10000,
        )

        headers = result.to_headers()

        assert "X-Budget-Warning" not in headers


class TestBudgetDependency:
    """Tests for budget enforcement dependency."""

    @pytest.mark.asyncio
    async def test_dependency_checks_budget(self) -> None:
        from semrush_core.budget.dependency import check_crawl_budget_dependency
        from semrush_core.budget.service import BudgetCheckResult, BudgetService

        mock_service = AsyncMock(spec=BudgetService)
        mock_service.check_crawl_budget.return_value = BudgetCheckResult(
            allowed=True,
            warning=False,
            usage_percentage=50.0,
            remaining=5000,
            limit=10000,
        )

        result = await check_crawl_budget_dependency(
            project_id=uuid.uuid4(),
            pages_needed=100,
            budget_service=mock_service,
            session=AsyncMock(),
        )

        assert result.allowed is True
