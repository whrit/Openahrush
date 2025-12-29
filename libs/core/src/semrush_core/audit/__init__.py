"""
Audit logging module for Openahrush.

Provides comprehensive audit logging for security-sensitive operations:
- User authentication (login/logout/password changes)
- Integration connections/disconnections
- Project lifecycle (create/update/delete)
- Export downloads
- Webhook configuration changes

Usage:
    from semrush_core.audit import AuditService, AuditAction, AuditLog, AuditContext

    # In a FastAPI endpoint
    async def my_endpoint(
        request: Request,
        db: AsyncSession = Depends(get_db),
    ):
        audit = AuditService(db)
        ctx = AuditContext.from_request(request)

        await audit.log_login_success(
            user_id=user.id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
        )
"""

from semrush_core.audit.context import AuditContext
from semrush_core.audit.models import AuditAction, AuditLog
from semrush_core.audit.service import AuditService

__all__ = [
    "AuditAction",
    "AuditContext",
    "AuditLog",
    "AuditService",
]
