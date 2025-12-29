"""
Budget enforcement service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_core.budget.models import (
    DEFAULT_MONTHLY_CRAWL_PAGES,
    DEFAULT_MONTHLY_EXPORTS,
    ProjectBudget,
)

if TYPE_CHECKING:
    pass


@dataclass
class BudgetCheckResult:
    """Result of a budget check."""

    allowed: bool
    warning: bool
    usage_percentage: float
    remaining: int
    limit: int
    message: str | None = None

    def to_headers(self) -> dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-Budget-Limit": str(self.limit),
            "X-Budget-Remaining": str(self.remaining),
        }
        if self.warning:
            headers["X-Budget-Warning"] = "true"
        return headers


class BudgetService:
    """
    Service for managing project budgets.

    Provides methods for:
    - Getting or creating project budgets
    - Checking budget availability
    - Incrementing usage
    - Resetting budgets for new periods
    """

    async def get_or_create_budget(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        crawl_limit: int = DEFAULT_MONTHLY_CRAWL_PAGES,
        export_limit: int = DEFAULT_MONTHLY_EXPORTS,
    ) -> ProjectBudget:
        """
        Get or create a budget for a project.

        If the budget period has expired, resets the usage counters.

        Args:
            session: Database session.
            project_id: The project ID.
            crawl_limit: Default crawl page limit.
            export_limit: Default export limit.

        Returns:
            ProjectBudget instance.
        """
        stmt = select(ProjectBudget).where(ProjectBudget.project_id == project_id)
        result = await session.execute(stmt)
        budget = result.scalar_one_or_none()

        if budget is None:
            # Create new budget
            now = datetime.now(UTC)
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate period end (first day of next month)
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)

            budget = ProjectBudget(
                project_id=project_id,
                monthly_crawl_page_limit=crawl_limit,
                monthly_export_limit=export_limit,
                crawl_pages_used=0,
                exports_used=0,
                period_start=period_start,
                period_end=period_end,
            )
            session.add(budget)
            await session.flush()
        elif budget.is_period_expired():
            # Reset for new period
            await self._reset_budget_period(budget)
            await session.flush()

        return budget

    async def _reset_budget_period(self, budget: ProjectBudget) -> None:
        """Reset budget for a new period."""
        now = datetime.now(UTC)
        budget.period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if budget.period_start.month == 12:
            budget.period_end = budget.period_start.replace(
                year=budget.period_start.year + 1, month=1
            )
        else:
            budget.period_end = budget.period_start.replace(month=budget.period_start.month + 1)
        budget.crawl_pages_used = 0
        budget.exports_used = 0

    async def check_crawl_budget(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        pages_needed: int = 1,
    ) -> BudgetCheckResult:
        """
        Check if a crawl is allowed within budget.

        Args:
            session: Database session.
            project_id: The project ID.
            pages_needed: Number of pages the crawl will process.

        Returns:
            BudgetCheckResult with allowed status and headers.
        """
        budget = await self.get_or_create_budget(session, project_id)

        remaining = budget.crawl_pages_remaining
        usage_pct = budget.crawl_usage_percentage
        warning = budget.should_warn_crawl

        # Check if already at limit
        if budget.is_at_crawl_limit:
            return BudgetCheckResult(
                allowed=False,
                warning=True,
                usage_percentage=usage_pct,
                remaining=0,
                limit=budget.monthly_crawl_page_limit,
                message="Monthly crawl page budget exhausted",
            )

        # Check if request would exceed limit
        if pages_needed > remaining:
            return BudgetCheckResult(
                allowed=False,
                warning=True,
                usage_percentage=usage_pct,
                remaining=remaining,
                limit=budget.monthly_crawl_page_limit,
                message=f"Requested {pages_needed} pages but only {remaining} remaining",
            )

        return BudgetCheckResult(
            allowed=True,
            warning=warning,
            usage_percentage=usage_pct,
            remaining=remaining,
            limit=budget.monthly_crawl_page_limit,
        )

    async def check_export_budget(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> BudgetCheckResult:
        """
        Check if an export is allowed within budget.

        Args:
            session: Database session.
            project_id: The project ID.

        Returns:
            BudgetCheckResult with allowed status and headers.
        """
        budget = await self.get_or_create_budget(session, project_id)

        remaining = budget.exports_remaining
        usage_pct = budget.export_usage_percentage
        warning = budget.should_warn_export

        if budget.is_at_export_limit:
            return BudgetCheckResult(
                allowed=False,
                warning=True,
                usage_percentage=usage_pct,
                remaining=0,
                limit=budget.monthly_export_limit,
                message="Monthly export budget exhausted",
            )

        return BudgetCheckResult(
            allowed=True,
            warning=warning,
            usage_percentage=usage_pct,
            remaining=remaining,
            limit=budget.monthly_export_limit,
        )

    async def increment_crawl_usage(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        pages_crawled: int,
    ) -> None:
        """
        Increment crawl page usage for a project.

        Args:
            session: Database session.
            project_id: The project ID.
            pages_crawled: Number of pages crawled.
        """
        budget = await self.get_or_create_budget(session, project_id)
        budget.crawl_pages_used += pages_crawled
        await session.flush()

    async def increment_export_usage(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> None:
        """
        Increment export usage for a project.

        Args:
            session: Database session.
            project_id: The project ID.
        """
        budget = await self.get_or_create_budget(session, project_id)
        budget.exports_used += 1
        await session.flush()

    async def reset_budget_for_new_period(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> None:
        """
        Manually reset budget for a new period.

        Args:
            session: Database session.
            project_id: The project ID.
        """
        budget = await self.get_or_create_budget(session, project_id)
        await self._reset_budget_period(budget)
        await session.flush()

    async def update_limits(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        crawl_limit: int | None = None,
        export_limit: int | None = None,
    ) -> ProjectBudget:
        """
        Update budget limits for a project.

        Args:
            session: Database session.
            project_id: The project ID.
            crawl_limit: New crawl page limit (optional).
            export_limit: New export limit (optional).

        Returns:
            Updated ProjectBudget.
        """
        budget = await self.get_or_create_budget(session, project_id)

        if crawl_limit is not None:
            budget.monthly_crawl_page_limit = crawl_limit
        if export_limit is not None:
            budget.monthly_export_limit = export_limit

        await session.flush()
        return budget
