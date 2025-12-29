"""
Secret-redacting logging utilities.

Provides secure logging that automatically redacts sensitive information
like JWT tokens, API keys, passwords, and database credentials from log output.
"""

import logging

from semrush_core.logging.formatter import SecretRedactingFormatter
from semrush_core.logging.redactor import SECRET_PATTERNS, redact_secrets

__all__ = [
    "SECRET_PATTERNS",
    "SecretRedactingFormatter",
    "get_secure_logger",
    "redact_secrets",
]


def get_secure_logger(name: str) -> logging.Logger:
    """
    Get a logger configured with secret redaction.

    Args:
        name: The logger name (typically __name__).

    Returns:
        A logger instance with SecretRedactingFormatter attached.
    """
    logger = logging.getLogger(name)

    # Only add handler if logger does not already have one
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            SecretRedactingFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

    return logger
