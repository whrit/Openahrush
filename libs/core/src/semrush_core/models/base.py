"""
SQLAlchemy base model and mixins.

Provides:
- DeclarativeBase for all models
- UUIDMixin for UUID primary keys
- TimestampMixin for created_at/updated_at tracking
- SoftDeleteMixin for soft delete functionality
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Naming convention for constraints (improves Alembic migrations)
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Configures:
    - PostgreSQL-specific type mappings
    - Consistent constraint naming conventions
    - Common metadata settings
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Type annotation map for common Python types
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
    }

    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to dictionary.

        Useful for serialization and debugging.
        Excludes SQLAlchemy internal attributes.

        Returns:
            Dictionary of column names to values.
        """
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """Generate a readable string representation."""
        class_name = self.__class__.__name__
        attrs = ", ".join(
            f"{col.name}={getattr(self, col.name)!r}"
            for col in self.__table__.columns
            if col.primary_key or col.name in ("name", "email", "title", "slug")
        )
        return f"<{class_name}({attrs})>"


class UUIDMixin:
    """
    Mixin providing UUID primary key.

    Generates a UUID4 by default if not provided.
    Uses PostgreSQL-native UUID type for efficiency.
    """

    @declared_attr.directive
    @classmethod
    def id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )


class TimestampMixin:
    """
    Mixin providing automatic timestamp tracking.

    - created_at: Set once on insert (server-side default)
    - updated_at: Updated on every modification (server-side onupdate)

    Both timestamps are timezone-aware using PostgreSQL's TIMESTAMPTZ.
    """

    @declared_attr.directive
    @classmethod
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr.directive
    @classmethod
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )


class SoftDeleteMixin:
    """
    Mixin for soft delete functionality.

    Instead of hard deleting records, sets deleted_at timestamp.
    Queries should filter on deleted_at IS NULL for active records.
    """

    @declared_attr.directive
    @classmethod
    def deleted_at(cls) -> Mapped[datetime | None]:
        return mapped_column(
            DateTime(timezone=True),
            nullable=True,
            default=None,
        )

    @property
    def is_deleted(self) -> bool:
        """Check if the record has been soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        from datetime import timezone

        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
