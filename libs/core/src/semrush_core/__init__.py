"""
Openahrush Core Library.

Provides shared infrastructure components for the Openahrush SEO platform:
- Configuration management via pydantic-settings
- Async SQLAlchemy database utilities
- Security primitives (JWT, password hashing, encryption)
- Base SQLAlchemy models with common mixins
"""

__version__ = "0.1.0"

from semrush_core.config import Settings, get_settings
from semrush_core.database import (
    AsyncSessionLocal,
    create_all_tables,
    get_async_session,
)

__all__ = [
    "AsyncSessionLocal",
    "Settings",
    "__version__",
    "create_all_tables",
    "get_async_session",
    "get_settings",
]
