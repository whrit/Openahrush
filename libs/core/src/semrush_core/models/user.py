"""
User model for authentication and ownership.

Users own projects and have integration accounts linked to them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from semrush_core.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from semrush_core.models.integration_account import IntegrationAccount
    from semrush_core.models.project import Project


class User(Base, UUIDMixin, TimestampMixin):
    """
    User model representing authenticated users of the platform.

    Attributes:
        email: Unique email address (case-insensitive via CITEXT in DB).
        password_hash: Bcrypt hashed password.
        name: Optional display name.
        is_active: Whether the user can log in (for soft-disable).
        projects: Projects owned by this user.
        integration_accounts: OAuth accounts linked to this user.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    # Relationships
    projects: Mapped[list[Project]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    integration_accounts: Mapped[list[IntegrationAccount]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
