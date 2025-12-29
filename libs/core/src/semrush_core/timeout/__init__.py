"""
Job timeout enforcement module.

Provides:
- Timeout configuration (crawl: 4 hours, export: 30 minutes)
- Timeout checking utilities
- Job marking as failed on timeout
"""

from semrush_core.timeout.config import TimeoutConfig
from semrush_core.timeout.enforcer import TimeoutEnforcer
from semrush_core.timeout.errors import JobTimeoutError

__all__ = [
    "TimeoutConfig",
    "TimeoutEnforcer",
    "JobTimeoutError",
]
