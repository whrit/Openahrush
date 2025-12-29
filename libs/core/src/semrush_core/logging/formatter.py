"""
Custom logging formatter with secret redaction.
"""

import logging

from semrush_core.logging.redactor import redact_secrets


class SecretRedactingFormatter(logging.Formatter):
    """A logging formatter that redacts secrets from log messages."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with secret redaction."""
        original = super().format(record)
        return redact_secrets(original)
