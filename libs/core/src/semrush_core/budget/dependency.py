"""
FastAPI dependencies for budget enforcement.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from semrush_core.budget.service import BudgetCheckResult, BudgetService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def check_crawl_budget_dependency(
    project_id: uuid.UUID,
    pages_needed: int,
    budget_service: BudgetService,
    session: AsyncSession,
) -> BudgetCheckResult:
    """
    FastAPI dependency for checking crawl budget.

    Args:
        project_id: The project ID.
        pages_needed: Number of pages the crawl will process.
        budget_service: Budget service instance.
        session: Database session.

    Returns:
        BudgetCheckResult with allowed status.
    """
    return await budget_service.check_crawl_budget(
        session=session,
        project_id=project_id,
        pages_needed=pages_needed,
    )


async def check_export_budget_dependency(
    project_id: uuid.UUID,
    budget_service: BudgetService,
    session: AsyncSession,
) -> BudgetCheckResult:
    """
    FastAPI dependency for checking export budget.

    Args:
        project_id: The project ID.
        budget_service: Budget service instance.
        session: Database session.

    Returns:
        BudgetCheckResult with allowed status.
    """
    return await budget_service.check_export_budget(
        session=session,
        project_id=project_id,
    )
