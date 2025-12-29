"""
Audit logging service.

Provides a service layer for creating audit log entries with
convenience methods for common security-sensitive operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from semrush_core.audit.models import AuditAction, AuditLog


class AuditService:
    """
    Service for creating and querying audit log entries.

    This service is intentionally append-only - there are no update or delete
    methods to maintain audit log integrity.

    Usage:
        service = AuditService(db_session)
        await service.log_login_success(user_id, ip_address, user_agent)
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the audit service.

        Args:
            session: SQLAlchemy async session for database operations.
        """
        self._session = session

    async def log(
        self,
        action: AuditAction | str,
        *,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Create a generic audit log entry.

        Args:
            action: The action being logged (AuditAction enum or string).
            user_id: UUID of the user performing the action.
            resource_type: Type of resource affected.
            resource_id: UUID of the affected resource.
            details: Additional action-specific details.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        # Convert enum to string value
        action_str = action.value if isinstance(action, AuditAction) else action

        log_entry = AuditLog(
            user_id=user_id,
            action=action_str,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._session.add(log_entry)
        return log_entry

    # =========================================================================
    # Authentication Logging
    # =========================================================================

    async def log_login_success(
        self,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log a successful login attempt.

        Args:
            user_id: UUID of the authenticated user.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.LOGIN_SUCCESS,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_login_failed(
        self,
        email: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        """
        Log a failed login attempt.

        Args:
            email: Email address used in the login attempt.
            ip_address: Client IP address.
            user_agent: Client user agent string.
            reason: Reason for the failure (e.g., "Invalid password").

        Returns:
            The created AuditLog entry.
        """
        # Note: user_id is None because we don't have a valid user
        return await self.log(
            action=AuditAction.LOGIN_FAILED,
            user_id=None,
            resource_type="user",
            details={
                "email": email,
                "reason": reason or "Authentication failed",
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_logout(
        self,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log a user logout.

        Args:
            user_id: UUID of the logging out user.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.LOGOUT,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # Integration Logging
    # =========================================================================

    async def log_integration_connect(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
        provider: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log an integration connection (OAuth).

        Args:
            user_id: UUID of the user connecting the integration.
            integration_id: UUID of the integration account.
            provider: Provider name (e.g., "google", "microsoft").
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.INTEGRATION_CONNECT,
            user_id=user_id,
            resource_type="integration",
            resource_id=integration_id,
            details={"provider": provider},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_integration_disconnect(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
        provider: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log an integration disconnection.

        Args:
            user_id: UUID of the user disconnecting the integration.
            integration_id: UUID of the integration account.
            provider: Provider name (e.g., "google", "microsoft").
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.INTEGRATION_DISCONNECT,
            user_id=user_id,
            resource_type="integration",
            resource_id=integration_id,
            details={"provider": provider},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # Project Logging
    # =========================================================================

    async def log_project_create(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        project_name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log project creation.

        Args:
            user_id: UUID of the user creating the project.
            project_id: UUID of the created project.
            project_name: Name of the created project.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.PROJECT_CREATE,
            user_id=user_id,
            resource_type="project",
            resource_id=project_id,
            details={"name": project_name},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_project_update(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        changes: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log project update.

        Args:
            user_id: UUID of the user updating the project.
            project_id: UUID of the updated project.
            changes: Dictionary of changes made.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.PROJECT_UPDATE,
            user_id=user_id,
            resource_type="project",
            resource_id=project_id,
            details={"changes": changes},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_project_delete(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        project_name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log project deletion.

        Args:
            user_id: UUID of the user deleting the project.
            project_id: UUID of the deleted project.
            project_name: Name of the deleted project.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.PROJECT_DELETE,
            user_id=user_id,
            resource_type="project",
            resource_id=project_id,
            details={"name": project_name},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # Export Logging
    # =========================================================================

    async def log_export_create(
        self,
        user_id: uuid.UUID,
        export_id: uuid.UUID,
        export_format: str,
        resource_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log export creation.

        Args:
            user_id: UUID of the user creating the export.
            export_id: UUID of the created export.
            export_format: Format of the export (csv, json, pdf).
            resource_type: Type of resource being exported.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.EXPORT_CREATE,
            user_id=user_id,
            resource_type="export",
            resource_id=export_id,
            details={
                "format": export_format,
                "resource": resource_type,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_export_download(
        self,
        user_id: uuid.UUID,
        export_id: uuid.UUID,
        export_format: str,
        resource_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log export download.

        Args:
            user_id: UUID of the user downloading the export.
            export_id: UUID of the downloaded export.
            export_format: Format of the export (csv, json, pdf).
            resource_type: Type of resource in the export.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.EXPORT_DOWNLOAD,
            user_id=user_id,
            resource_type="export",
            resource_id=export_id,
            details={
                "format": export_format,
                "resource": resource_type,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # Webhook Logging
    # =========================================================================

    async def log_webhook_create(
        self,
        user_id: uuid.UUID,
        webhook_id: uuid.UUID,
        project_id: uuid.UUID,
        webhook_url: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log webhook creation.

        Note: Webhook secrets are intentionally NOT logged for security.

        Args:
            user_id: UUID of the user creating the webhook.
            webhook_id: UUID of the created webhook.
            project_id: UUID of the project the webhook belongs to.
            webhook_url: URL of the webhook endpoint.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.WEBHOOK_CREATE,
            user_id=user_id,
            resource_type="webhook",
            resource_id=webhook_id,
            details={
                "url": webhook_url,
                "project_id": str(project_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_webhook_update(
        self,
        user_id: uuid.UUID,
        webhook_id: uuid.UUID,
        changes: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log webhook update.

        Note: Secret changes are logged as "secret_changed: true" without the value.

        Args:
            user_id: UUID of the user updating the webhook.
            webhook_id: UUID of the updated webhook.
            changes: Dictionary of changes made.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        # Sanitize changes to avoid logging secrets
        safe_changes = {}
        for key, value in changes.items():
            if "secret" in key.lower():
                safe_changes["secret_changed"] = True
            else:
                safe_changes[key] = value

        return await self.log(
            action=AuditAction.WEBHOOK_UPDATE,
            user_id=user_id,
            resource_type="webhook",
            resource_id=webhook_id,
            details={"changes": safe_changes},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_webhook_delete(
        self,
        user_id: uuid.UUID,
        webhook_id: uuid.UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Log webhook deletion.

        Args:
            user_id: UUID of the user deleting the webhook.
            webhook_id: UUID of the deleted webhook.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            The created AuditLog entry.
        """
        return await self.log(
            action=AuditAction.WEBHOOK_DELETE,
            user_id=user_id,
            resource_type="webhook",
            resource_id=webhook_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_logs_by_user(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific user.

        Args:
            user_id: UUID of the user.
            limit: Maximum number of logs to return.
            offset: Number of logs to skip.

        Returns:
            List of AuditLog entries.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_logs_by_action(
        self,
        action: AuditAction | str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific action type.

        Args:
            action: Action type to filter by.
            limit: Maximum number of logs to return.
            offset: Number of logs to skip.

        Returns:
            List of AuditLog entries.
        """
        action_str = action.value if isinstance(action, AuditAction) else action
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action_str)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_logs_by_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific resource.

        Args:
            resource_type: Type of resource.
            resource_id: Optional UUID of the specific resource.
            limit: Maximum number of logs to return.
            offset: Number of logs to skip.

        Returns:
            List of AuditLog entries.
        """
        stmt = select(AuditLog).where(AuditLog.resource_type == resource_type)

        if resource_id is not None:
            stmt = stmt.where(AuditLog.resource_id == resource_id)

        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_logs(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """
        Get audit logs with optional date filtering.

        Args:
            from_date: Start of date range (inclusive).
            to_date: End of date range (inclusive).
            limit: Maximum number of logs to return.
            offset: Number of logs to skip.

        Returns:
            List of AuditLog entries.
        """
        stmt = select(AuditLog)

        if from_date is not None:
            stmt = stmt.where(AuditLog.created_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(AuditLog.created_at <= to_date)

        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_login_attempts(
        self,
        email: str,
        limit: int = 10,
    ) -> list[AuditLog]:
        """
        Get recent login attempts (success and failed) for an email.

        Useful for security monitoring and rate limiting.

        Args:
            email: Email address to search for.
            limit: Maximum number of logs to return.

        Returns:
            List of AuditLog entries for login attempts.
        """
        login_actions = [
            AuditAction.LOGIN_SUCCESS.value,
            AuditAction.LOGIN_FAILED.value,
        ]
        stmt = (
            select(AuditLog)
            .where(AuditLog.action.in_(login_actions))
            .where(AuditLog.details["email"].astext == email)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
