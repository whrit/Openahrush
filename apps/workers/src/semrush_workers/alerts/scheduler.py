"""
Alert scheduler for running detection jobs.

Runs alert detection after:
- Daily integration sync
- Crawl completion

Queries active alert_rules per project and executes
the appropriate detector.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from semrush_workers.alerts.ctr_detector import CTRDetector
from semrush_workers.alerts.regression_detector import RegressionDetector
from semrush_workers.alerts.visibility_detector import VisibilityDetector

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


class AlertScheduler:
    """
    Scheduler for running alert detection jobs.

    Coordinates the execution of different detectors based on
    configured alert rules for each project.

    Attributes:
        db: Database session.
        redis: Redis client for event publishing.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
    ) -> None:
        """
        Initialize the scheduler.

        Args:
            db: Database session.
            redis: Redis client.
        """
        self._db = db
        self._redis = redis

    async def run_for_project(
        self,
        project_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Run all enabled alert rules for a project.

        Args:
            project_id: Project UUID.

        Returns:
            List of created alerts.
        """
        from semrush_core.models import AlertRule

        # Get enabled rules for project
        result = await self._db.execute(
            select(AlertRule).where(
                AlertRule.project_id == project_id,
                AlertRule.is_enabled == True,  # noqa: E712
            )
        )
        rules = result.scalars().all()

        created_alerts: list[dict[str, Any]] = []

        for rule in rules:
            alerts = await self._run_rule(rule)
            created_alerts.extend(alerts)

        return created_alerts

    async def run_after_crawl(
        self,
        project_id: uuid.UUID,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Run alert detection after a crawl completes.

        Primarily runs regression detection.

        Args:
            project_id: Project UUID.
            crawl_run_id: Completed crawl run UUID.

        Returns:
            List of created alerts.
        """
        from semrush_core.models import AlertRule

        # Get regression rules for project
        result = await self._db.execute(
            select(AlertRule).where(
                AlertRule.project_id == project_id,
                AlertRule.is_enabled == True,  # noqa: E712
                AlertRule.rule_type == "regression",
            )
        )
        rules = result.scalars().all()

        created_alerts: list[dict[str, Any]] = []

        for rule in rules:
            alerts = await self._run_regression_check(rule, crawl_run_id)
            created_alerts.extend(alerts)

        return created_alerts

    async def run_after_sync(
        self,
        project_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Run alert detection after integration sync.

        Runs visibility drop and CTR opportunity detection.

        Args:
            project_id: Project UUID.

        Returns:
            List of created alerts.
        """
        from semrush_core.models import AlertRule

        # Get visibility and CTR rules for project
        result = await self._db.execute(
            select(AlertRule).where(
                AlertRule.project_id == project_id,
                AlertRule.is_enabled == True,  # noqa: E712
                AlertRule.rule_type.in_(["visibility_drop", "ctr_opportunity"]),
            )
        )
        rules = result.scalars().all()

        created_alerts: list[dict[str, Any]] = []

        for rule in rules:
            alerts = await self._run_rule(rule)
            created_alerts.extend(alerts)

        return created_alerts

    async def _run_rule(
        self,
        rule: Any,
    ) -> list[dict[str, Any]]:
        """
        Run a specific alert rule.

        Args:
            rule: AlertRule model instance.

        Returns:
            List of created alerts.
        """
        if rule.rule_type == "visibility_drop":
            return await self._run_visibility_check(rule)
        elif rule.rule_type == "ctr_opportunity":
            return await self._run_ctr_check(rule)
        elif rule.rule_type == "regression":
            # Regression is run separately after crawl
            return []
        else:
            return []

    async def _run_visibility_check(
        self,
        rule: Any,
    ) -> list[dict[str, Any]]:
        """
        Run visibility drop detection.

        Args:
            rule: AlertRule for visibility drop.

        Returns:
            List of created alerts.
        """
        # Get config
        threshold = rule.config.get("threshold", 30.0)

        # Get search data for comparison
        previous_data = await self._get_search_data(
            project_id=rule.project_id,
            days_ago_start=14,
            days_ago_end=7,
        )
        current_data = await self._get_search_data(
            project_id=rule.project_id,
            days_ago_start=7,
            days_ago_end=0,
        )

        # Run detector
        detector = VisibilityDetector(threshold_percent=threshold)

        # Aggregate data
        previous_query_data = detector.aggregate_by_key(previous_data, "query")
        current_query_data = detector.aggregate_by_key(current_data, "query")

        query_drops = detector.detect_query_drops(previous_query_data, current_query_data)

        # Aggregate by page
        previous_page_data = detector.aggregate_by_key(previous_data, "page_url")
        current_page_data = detector.aggregate_by_key(current_data, "page_url")

        page_drops = detector.detect_page_drops(previous_page_data, current_page_data)

        created_alerts: list[dict[str, Any]] = []

        # Store alerts for drops
        for drop in query_drops:
            alert = await self._store_alert(
                project_id=rule.project_id,
                alert_rule_id=rule.id,
                kind="visibility_drop",
                entity_type=drop.entity_type,
                entity_key=drop.entity_key,
                severity=drop.severity,
                payload=drop.to_alert_payload(),
            )
            created_alerts.append(alert)

        for drop in page_drops:
            alert = await self._store_alert(
                project_id=rule.project_id,
                alert_rule_id=rule.id,
                kind="visibility_drop",
                entity_type=drop.entity_type,
                entity_key=drop.entity_key,
                severity=drop.severity,
                payload=drop.to_alert_payload(),
            )
            created_alerts.append(alert)

        return created_alerts

    async def _run_ctr_check(
        self,
        rule: Any,
    ) -> list[dict[str, Any]]:
        """
        Run CTR opportunity detection.

        Args:
            rule: AlertRule for CTR opportunity.

        Returns:
            List of created alerts.
        """
        # Get config
        min_impressions = rule.config.get("min_impressions", 100)

        # Get recent search data
        search_data = await self._get_search_data_with_ctr(
            project_id=rule.project_id,
            days_ago=7,
        )

        # Run detector
        detector = CTRDetector(min_impressions=min_impressions)
        opportunities = detector.detect_opportunities(search_data)

        created_alerts: list[dict[str, Any]] = []

        for opportunity in opportunities:
            alert = await self._store_alert(
                project_id=rule.project_id,
                alert_rule_id=rule.id,
                kind="ctr_opportunity",
                entity_type="query",
                entity_key=opportunity.query,
                severity=opportunity.severity,
                payload=opportunity.to_alert_payload(),
            )
            created_alerts.append(alert)

        return created_alerts

    async def _run_regression_check(
        self,
        rule: Any,
        crawl_run_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run regression detection.

        Args:
            rule: AlertRule for regression.
            crawl_run_id: Current crawl run UUID.

        Returns:
            List of created alerts.
        """
        if crawl_run_id is None:
            return []

        # Get config
        threshold = rule.config.get("threshold", 10)

        # Get issues from current and previous crawl
        current_issues = await self._get_crawl_issues(crawl_run_id)
        previous_issues = await self._get_previous_crawl_issues(
            project_id=rule.project_id,
            current_crawl_id=crawl_run_id,
        )

        # Run detector
        detector = RegressionDetector(threshold=threshold)
        result = detector.detect_regression(previous_issues, current_issues)

        if result is None:
            return []

        # Store alert
        alert = await self._store_alert(
            project_id=rule.project_id,
            alert_rule_id=rule.id,
            kind="regression",
            entity_type="project",
            entity_key=str(rule.project_id),
            severity=result.severity,
            payload=result.to_alert_payload(),
        )

        return [alert]

    async def _get_search_data(
        self,
        project_id: uuid.UUID,
        days_ago_start: int,
        days_ago_end: int,
    ) -> list[dict[str, Any]]:
        """
        Get search data for a date range.

        Args:
            project_id: Project UUID.
            days_ago_start: Start of range (days ago).
            days_ago_end: End of range (days ago).

        Returns:
            List of search data rows.
        """
        from semrush_core.models import SearchFactDaily

        today = date.today()
        start_date = today - timedelta(days=days_ago_start)
        end_date = today - timedelta(days=days_ago_end)

        result = await self._db.execute(
            select(SearchFactDaily).where(
                SearchFactDaily.project_id == project_id,
                SearchFactDaily.date >= start_date,
                SearchFactDaily.date < end_date,
            )
        )
        rows = result.scalars().all()

        return [
            {
                "query": row.query,
                "page_url": row.page_url,
                "impressions": row.impressions,
            }
            for row in rows
        ]

    async def _get_search_data_with_ctr(
        self,
        project_id: uuid.UUID,
        days_ago: int,
    ) -> list[dict[str, Any]]:
        """
        Get search data with CTR and position for recent period.

        Args:
            project_id: Project UUID.
            days_ago: How many days back to look.

        Returns:
            List of search data rows with CTR.
        """
        from semrush_core.models import SearchFactDaily

        today = date.today()
        start_date = today - timedelta(days=days_ago)

        result = await self._db.execute(
            select(SearchFactDaily).where(
                SearchFactDaily.project_id == project_id,
                SearchFactDaily.date >= start_date,
            )
        )
        rows = result.scalars().all()

        return [
            {
                "query": row.query,
                "page_url": row.page_url,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "ctr": float(row.ctr) * 100 if row.ctr else 0.0,
                "position": float(row.avg_position) if row.avg_position else 0.0,
            }
            for row in rows
        ]

    async def _get_crawl_issues(
        self,
        crawl_run_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Get issues for a crawl run.

        Args:
            crawl_run_id: Crawl run UUID.

        Returns:
            List of issue data.
        """
        from semrush_core.models import IssueInstance

        result = await self._db.execute(
            select(IssueInstance).where(IssueInstance.crawl_run_id == crawl_run_id)
        )
        issues = result.scalars().all()

        return [
            {
                "issue_type_id": issue.issue_type_id,
                "affected_url": issue.affected_url,
            }
            for issue in issues
        ]

    async def _get_previous_crawl_issues(
        self,
        project_id: uuid.UUID,
        current_crawl_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """
        Get issues from the previous crawl run.

        Args:
            project_id: Project UUID.
            current_crawl_id: Current crawl run UUID.

        Returns:
            List of issue data from previous crawl.
        """
        from semrush_core.models import CrawlRun

        # Find the previous completed crawl
        result = await self._db.execute(
            select(CrawlRun)
            .where(
                CrawlRun.project_id == project_id,
                CrawlRun.id != current_crawl_id,
                CrawlRun.status == "completed",
            )
            .order_by(CrawlRun.created_at.desc())
            .limit(1)
        )
        previous_crawl = result.scalar_one_or_none()

        if previous_crawl is None:
            return []

        return await self._get_crawl_issues(previous_crawl.id)

    async def _store_alert(
        self,
        project_id: uuid.UUID,
        alert_rule_id: uuid.UUID,
        kind: str,
        entity_type: str,
        entity_key: str,
        severity: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Store an alert in the database and emit event.

        Args:
            project_id: Project UUID.
            alert_rule_id: Alert rule UUID.
            kind: Alert kind.
            entity_type: Entity type.
            entity_key: Entity key.
            severity: Alert severity.
            payload: Alert payload.

        Returns:
            Created alert data.
        """
        from semrush_core.models import Alert

        alert = Alert(
            project_id=project_id,
            alert_rule_id=alert_rule_id,
            kind=kind,
            entity_type=entity_type,
            entity_key=entity_key,
            severity=severity,
            payload=payload,
        )

        self._db.add(alert)
        await self._db.commit()

        # Emit event
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "alert.fired",
            "occurred_at": datetime.now(UTC).isoformat(),
            "project_id": str(project_id),
            "payload": {
                "alert_id": str(alert.id),
                "kind": kind,
                "severity": severity,
                "entity_type": entity_type,
                "entity_key": entity_key,
            },
        }

        await self._redis.publish("openahrush:events", json.dumps(event))

        return {
            "id": str(alert.id),
            "kind": kind,
            "severity": severity,
            "entity_type": entity_type,
            "entity_key": entity_key,
        }
