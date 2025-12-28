"""
Openahrush Core Library.

Provides shared infrastructure components for the Openahrush SEO platform:
- Configuration management via pydantic-settings
- Async SQLAlchemy database utilities
- Security primitives (JWT, password hashing, encryption)
- Base SQLAlchemy models with common mixins
"""

__version__ = "0.1.0"

from semrush_core.config import get_settings, Settings
from semrush_core.database import (
    get_async_session,
    create_all_tables,
    AsyncSessionLocal,
)

__all__ = [
    "__version__",
    "get_settings",
    "Settings",
    "get_async_session",
    "create_all_tables",
    "AsyncSessionLocal",
]
