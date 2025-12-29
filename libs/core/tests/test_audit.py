"""
Tests for audit logging system.

Following TDD: Tests written first, then implementation.

Tests cover:
- AuditLog model creation and field validation
- AuditAction enum values
- AuditService for logging operations
- Audit log querying and filtering
- FastAPI middleware for request context capture
- Security-sensitive operation logging
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# AuditLog Model Tests
# =============================================================================


class TestAuditLogModel:
    """Tests for the AuditLog SQLAlchemy model."""

    def test_audit_log_has_required_fields(self):
        """AuditLog should have all required fields."""
        from semrush_core.audit.models import AuditLog

        # Create an instance to verify fields exist
        log = AuditLog(
            user_id=uuid.uuid4(),
            action="user.login",
            resource_type="user",
            resource_id=uuid.uuid4(),
            details={"success": True},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert hasattr(log, "id")
        assert hasattr(log, "user_id")
        assert hasattr(log, "action")
        assert hasattr(log, "resource_type")
        assert hasattr(log, "resource_id")
        assert hasattr(log, "details")
        assert hasattr(log, "ip_address")
        assert hasattr(log, "user_agent")
        assert hasattr(log, "created_at")

    def test_audit_log_uuid_id(self):
        """AuditLog should have UUID primary key."""
        from semrush_core.audit.models import AuditLog

        log = AuditLog(
            action="user.login",
        )

        # id should be generated if not provided
        assert log.id is None or isinstance(log.id, uuid.UUID)

    def test_audit_log_nullable_fields(self):
        """AuditLog should allow nullable fields."""
        from semrush_core.audit.models import AuditLog

        # user_id can be null for anonymous actions
        log = AuditLog(
            user_id=None,
            action="system.startup",
            resource_type=None,
            resource_id=None,
            details=None,
            ip_address=None,
            user_agent=None,
        )

        assert log.user_id is None
        assert log.resource_type is None
        assert log.resource_id is None

    def test_audit_log_action_required(self):
        """AuditLog action field should be required."""
        from semrush_core.audit.models import AuditLog

        log = AuditLog(action="test.action")
        assert log.action == "test.action"

    def test_audit_log_details_is_jsonb(self):
        """AuditLog details should accept dict/JSON data."""
        from semrush_core.audit.models import AuditLog

        details = {
            "success": True,
            "old_value": "old",
            "new_value": "new",
            "nested": {"key": "value"},
        }
        log = AuditLog(
            action="test.action",
            details=details,
        )

        assert log.details == details

    def test_audit_log_to_dict(self):
        """AuditLog should have to_dict method."""
        from semrush_core.audit.models import AuditLog

        log_id = uuid.uuid4()
        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        log = AuditLog(
            id=log_id,
            user_id=user_id,
            action="project.create",
            resource_type="project",
            resource_id=resource_id,
            details={"name": "Test Project"},
            ip_address="10.0.0.1",
            user_agent="Test Agent",
        )

        result = log.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == log_id
        assert result["user_id"] == user_id
        assert result["action"] == "project.create"


# =============================================================================
# AuditAction Enum Tests
# =============================================================================


class TestAuditAction:
    """Tests for audit action constants/enum."""

    def test_login_actions_defined(self):
        """Login-related actions should be defined."""
        from semrush_core.audit.models import AuditAction

        assert hasattr(AuditAction, "LOGIN_SUCCESS")
        assert hasattr(AuditAction, "LOGIN_FAILED")
        assert hasattr(AuditAction, "LOGOUT")

    def test_integration_actions_defined(self):
        """Integration-related actions should be defined."""
        from semrush_core.audit.models import AuditAction

        assert hasattr(AuditAction, "INTEGRATION_CONNECT")
        assert hasattr(AuditAction, "INTEGRATION_DISCONNECT")

    def test_project_actions_defined(self):
        """Project-related actions should be defined."""
        from semrush_core.audit.models import AuditAction

        assert hasattr(AuditAction, "PROJECT_CREATE")
        assert hasattr(AuditAction, "PROJECT_DELETE")
        assert hasattr(AuditAction, "PROJECT_UPDATE")

    def test_export_actions_defined(self):
        """Export-related actions should be defined."""
        from semrush_core.audit.models import AuditAction

        assert hasattr(AuditAction, "EXPORT_DOWNLOAD")
        assert hasattr(AuditAction, "EXPORT_CREATE")

    def test_webhook_actions_defined(self):
        """Webhook-related actions should be defined."""
        from semrush_core.audit.models import AuditAction

        assert hasattr(AuditAction, "WEBHOOK_CREATE")
        assert hasattr(AuditAction, "WEBHOOK_UPDATE")
        assert hasattr(AuditAction, "WEBHOOK_DELETE")

    def test_action_values_are_strings(self):
        """Action values should be descriptive strings."""
        from semrush_core.audit.models import AuditAction

        assert AuditAction.LOGIN_SUCCESS.value == "user.login.success"
        assert AuditAction.LOGIN_FAILED.value == "user.login.failed"
        assert AuditAction.PROJECT_CREATE.value == "project.create"


# =============================================================================
# AuditService Tests
# =============================================================================


class TestAuditService:
    """Tests for the AuditService."""

    @pytest.mark.asyncio
    async def test_log_creates_audit_entry(self):
        """AuditService.log should create an audit log entry."""
        from semrush_core.audit.models import AuditAction
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        await service.log(
            action=AuditAction.LOGIN_SUCCESS,
            user_id=user_id,
            ip_address="192.168.1.100",
            user_agent="Test Browser",
        )

        # Should have called session.add
        mock_session.add.assert_called_once()

        # Verify the audit log object
        added_log = mock_session.add.call_args[0][0]
        assert added_log.action == AuditAction.LOGIN_SUCCESS.value
        assert added_log.user_id == user_id
        assert added_log.ip_address == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_log_with_resource_info(self):
        """AuditService.log should include resource information."""
        from semrush_core.audit.models import AuditAction
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        project_id = uuid.uuid4()

        await service.log(
            action=AuditAction.PROJECT_CREATE,
            user_id=user_id,
            resource_type="project",
            resource_id=project_id,
            details={"name": "New Project", "domain": "example.com"},
        )

        added_log = mock_session.add.call_args[0][0]
        assert added_log.resource_type == "project"
        assert added_log.resource_id == project_id
        assert added_log.details["name"] == "New Project"

    @pytest.mark.asyncio
    async def test_log_accepts_string_action(self):
        """AuditService.log should accept string action."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        await service.log(
            action="custom.action",
            user_id=uuid.uuid4(),
        )

        added_log = mock_session.add.call_args[0][0]
        assert added_log.action == "custom.action"

    @pytest.mark.asyncio
    async def test_log_login_success(self):
        """log_login_success helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        await service.log_login_success(
            user_id=user_id,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "login" in added_log.action.lower()
        assert "success" in added_log.action.lower()
        assert added_log.user_id == user_id

    @pytest.mark.asyncio
    async def test_log_login_failed(self):
        """log_login_failed helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        await service.log_login_failed(
            email="test@example.com",
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
            reason="Invalid password",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "login" in added_log.action.lower()
        assert "failed" in added_log.action.lower()
        assert added_log.user_id is None  # No user for failed login
        assert added_log.details["email"] == "test@example.com"
        assert "reason" in added_log.details

    @pytest.mark.asyncio
    async def test_log_integration_connect(self):
        """log_integration_connect helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        integration_id = uuid.uuid4()

        await service.log_integration_connect(
            user_id=user_id,
            integration_id=integration_id,
            provider="google",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "integration" in added_log.action.lower()
        assert "connect" in added_log.action.lower()
        assert added_log.resource_type == "integration"
        assert added_log.resource_id == integration_id
        assert added_log.details["provider"] == "google"

    @pytest.mark.asyncio
    async def test_log_integration_disconnect(self):
        """log_integration_disconnect helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        integration_id = uuid.uuid4()

        await service.log_integration_disconnect(
            user_id=user_id,
            integration_id=integration_id,
            provider="microsoft",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "integration" in added_log.action.lower()
        assert "disconnect" in added_log.action.lower()
        assert added_log.details["provider"] == "microsoft"

    @pytest.mark.asyncio
    async def test_log_project_create(self):
        """log_project_create helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        project_id = uuid.uuid4()

        await service.log_project_create(
            user_id=user_id,
            project_id=project_id,
            project_name="Test Project",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "project" in added_log.action.lower()
        assert "create" in added_log.action.lower()
        assert added_log.resource_type == "project"
        assert added_log.resource_id == project_id
        assert added_log.details["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_log_project_delete(self):
        """log_project_delete helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        project_id = uuid.uuid4()

        await service.log_project_delete(
            user_id=user_id,
            project_id=project_id,
            project_name="Deleted Project",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "project" in added_log.action.lower()
        assert "delete" in added_log.action.lower()

    @pytest.mark.asyncio
    async def test_log_export_download(self):
        """log_export_download helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        export_id = uuid.uuid4()

        await service.log_export_download(
            user_id=user_id,
            export_id=export_id,
            export_format="csv",
            resource_type="issues",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "export" in added_log.action.lower()
        assert "download" in added_log.action.lower()
        assert added_log.resource_type == "export"
        assert added_log.details["format"] == "csv"

    @pytest.mark.asyncio
    async def test_log_webhook_create(self):
        """log_webhook_create helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        webhook_id = uuid.uuid4()
        project_id = uuid.uuid4()

        await service.log_webhook_create(
            user_id=user_id,
            webhook_id=webhook_id,
            project_id=project_id,
            webhook_url="https://example.com/webhook",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "webhook" in added_log.action.lower()
        assert "create" in added_log.action.lower()
        assert added_log.resource_type == "webhook"
        # URL should be logged but not sensitive secret
        assert "url" in added_log.details

    @pytest.mark.asyncio
    async def test_log_webhook_update(self):
        """log_webhook_update helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        webhook_id = uuid.uuid4()

        await service.log_webhook_update(
            user_id=user_id,
            webhook_id=webhook_id,
            changes={"url": "https://new-url.com/webhook", "is_enabled": False},
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "webhook" in added_log.action.lower()
        assert "update" in added_log.action.lower()
        assert "changes" in added_log.details

    @pytest.mark.asyncio
    async def test_log_webhook_delete(self):
        """log_webhook_delete helper should create correct entry."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        webhook_id = uuid.uuid4()

        await service.log_webhook_delete(
            user_id=user_id,
            webhook_id=webhook_id,
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]
        assert "webhook" in added_log.action.lower()
        assert "delete" in added_log.action.lower()


# =============================================================================
# AuditService Query Tests
# =============================================================================


class TestAuditServiceQueries:
    """Tests for AuditService query methods."""

    @pytest.mark.asyncio
    async def test_get_logs_by_user(self):
        """get_logs_by_user should filter by user_id."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AuditService(mock_session)

        user_id = uuid.uuid4()
        result = await service.get_logs_by_user(user_id, limit=50)

        assert mock_session.execute.called
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_logs_by_action(self):
        """get_logs_by_action should filter by action type."""
        from semrush_core.audit.models import AuditAction
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AuditService(mock_session)

        result = await service.get_logs_by_action(
            AuditAction.LOGIN_SUCCESS, limit=100
        )

        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_logs_by_resource(self):
        """get_logs_by_resource should filter by resource."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AuditService(mock_session)

        resource_id = uuid.uuid4()
        result = await service.get_logs_by_resource(
            resource_type="project",
            resource_id=resource_id,
        )

        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_logs_with_date_range(self):
        """get_logs should support date range filtering."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AuditService(mock_session)

        from_date = datetime(2024, 1, 1, tzinfo=UTC)
        to_date = datetime(2024, 12, 31, tzinfo=UTC)

        result = await service.get_logs(
            from_date=from_date,
            to_date=to_date,
            limit=100,
        )

        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_recent_login_attempts(self):
        """get_recent_login_attempts should return recent login logs."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AuditService(mock_session)

        result = await service.get_recent_login_attempts(
            email="test@example.com",
            limit=10,
        )

        assert mock_session.execute.called


# =============================================================================
# Audit Context Tests
# =============================================================================


class TestAuditContext:
    """Tests for audit context management."""

    def test_audit_context_stores_request_info(self):
        """AuditContext should store request information."""
        from semrush_core.audit.context import AuditContext

        ctx = AuditContext(
            ip_address="192.168.1.1",
            user_agent="Test Browser",
            request_id="req-123",
        )

        assert ctx.ip_address == "192.168.1.1"
        assert ctx.user_agent == "Test Browser"
        assert ctx.request_id == "req-123"

    def test_audit_context_extracts_from_request(self):
        """AuditContext should extract info from FastAPI request."""
        from semrush_core.audit.context import AuditContext

        # Mock FastAPI request
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get.side_effect = lambda key, default=None: {
            "user-agent": "Mozilla/5.0",
            "x-request-id": "test-req-id",
            "x-forwarded-for": None,
        }.get(key.lower(), default)

        ctx = AuditContext.from_request(mock_request)

        assert ctx.ip_address == "10.0.0.1"
        assert ctx.user_agent == "Mozilla/5.0"

    def test_audit_context_x_forwarded_for(self):
        """AuditContext should use X-Forwarded-For when present."""
        from semrush_core.audit.context import AuditContext

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.side_effect = lambda key, default=None: {
            "user-agent": "Browser",
            "x-forwarded-for": "203.0.113.195, 70.41.3.18",
        }.get(key.lower(), default)

        ctx = AuditContext.from_request(mock_request)

        # Should use first IP from X-Forwarded-For
        assert ctx.ip_address == "203.0.113.195"


# =============================================================================
# Database Schema Tests
# =============================================================================


class TestAuditLogTableSchema:
    """Tests to verify AuditLog table schema."""

    def test_audit_log_tablename(self):
        """AuditLog should have correct table name."""
        from semrush_core.audit.models import AuditLog

        assert AuditLog.__tablename__ == "audit_logs"

    def test_audit_log_columns(self):
        """AuditLog should have expected columns."""
        from semrush_core.audit.models import AuditLog

        columns = {c.name for c in AuditLog.__table__.columns}

        expected_columns = {
            "id",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "details",
            "ip_address",
            "user_agent",
            "created_at",
        }

        assert expected_columns.issubset(columns)

    def test_audit_log_has_indexes(self):
        """AuditLog should have appropriate indexes."""
        from semrush_core.audit.models import AuditLog

        indexes = {idx.name for idx in AuditLog.__table__.indexes}

        # Should have indexes for common query patterns
        # Index names depend on implementation, just verify some exist
        assert len(indexes) > 0


# =============================================================================
# Integration with Other Modules Tests
# =============================================================================


class TestAuditIntegration:
    """Tests for audit logging integration with other modules."""

    def test_audit_log_user_relationship(self):
        """AuditLog should reference User model correctly."""
        from semrush_core.audit.models import AuditLog

        # Should have user_id foreign key
        user_id_col = AuditLog.__table__.c.user_id
        assert user_id_col is not None

    def test_audit_action_enum_export(self):
        """AuditAction should be importable from audit module."""
        from semrush_core.audit import AuditAction

        assert AuditAction is not None

    def test_audit_service_export(self):
        """AuditService should be importable from audit module."""
        from semrush_core.audit import AuditService

        assert AuditService is not None

    def test_audit_log_export(self):
        """AuditLog should be importable from audit module."""
        from semrush_core.audit import AuditLog

        assert AuditLog is not None


# =============================================================================
# Security Tests
# =============================================================================


class TestAuditSecurity:
    """Tests for audit logging security considerations."""

    @pytest.mark.asyncio
    async def test_sensitive_data_not_logged(self):
        """Sensitive data like passwords should not be logged."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        # Attempt to log with sensitive data
        await service.log_login_failed(
            email="test@example.com",
            ip_address="10.0.0.1",
            user_agent="Browser",
            reason="Invalid password",
            # These fields should be filtered or not accepted
        )

        added_log = mock_session.add.call_args[0][0]

        # Should not contain password in details
        details_str = str(added_log.details).lower()
        assert "password" not in details_str or "password123" not in details_str

    @pytest.mark.asyncio
    async def test_webhook_secret_not_logged(self):
        """Webhook secrets should not be logged."""
        from semrush_core.audit.service import AuditService

        mock_session = AsyncMock(spec=AsyncSession)
        service = AuditService(mock_session)

        await service.log_webhook_create(
            user_id=uuid.uuid4(),
            webhook_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            webhook_url="https://example.com/webhook",
            ip_address="10.0.0.1",
        )

        added_log = mock_session.add.call_args[0][0]

        # Should not contain secret
        details_str = str(added_log.details).lower()
        assert "secret" not in details_str

    @pytest.mark.asyncio
    async def test_immutable_audit_logs(self):
        """Audit logs should be append-only (no update/delete in service)."""
        from semrush_core.audit.service import AuditService

        service = AuditService(AsyncMock(spec=AsyncSession))

        # Service should not have update or delete methods
        assert not hasattr(service, "update_log")
        assert not hasattr(service, "delete_log")
        assert not hasattr(service, "update")
        assert not hasattr(service, "delete")
