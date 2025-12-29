"""Tests for logging."""
import logging
import re


class TestJWTTokenRedaction:
    def test_redact_jwt_token(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc"
        redacted = redact_secrets(msg)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
        assert "[REDACTED_JWT]" in redacted


class TestBearerTokenRedaction:
    def test_redact_bearer_token(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "Authorization: Bearer abc123xyz456token789"
        redacted = redact_secrets(msg)
        assert "abc123xyz456token789" not in redacted
        assert "Bearer [REDACTED_BEARER]" in redacted


class TestPasswordRedaction:
    def test_redact_password_equals(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "Connection string: password=mysecret123"
        redacted = redact_secrets(msg)
        assert "mysecret123" not in redacted
        assert "password=[REDACTED_PASSWORD]" in redacted


class TestAPIKeyRedaction:
    def test_redact_api_key(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "Request: api_key=sk_live_abc123"
        redacted = redact_secrets(msg)
        assert "sk_live_abc123" not in redacted
        assert "api_key=[REDACTED_API_KEY]" in redacted


class TestWebhookSecretRedaction:
    def test_redact_webhook_secret(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "Config: webhook_secret=whsec_abc123"
        redacted = redact_secrets(msg)
        assert "whsec_abc123" not in redacted
        assert "webhook_secret=[REDACTED_WEBHOOK_SECRET]" in redacted


class TestDatabaseURLRedaction:
    def test_redact_postgres_url(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "DB: postgresql://user:mysecret@localhost:5432/db"
        redacted = redact_secrets(msg)
        assert "mysecret" not in redacted
        assert "[REDACTED_DB_PASSWORD]" in redacted


class TestEdgeCases:
    def test_empty_message(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        assert redact_secrets("") == ""

    def test_no_secrets(self) -> None:
        from semrush_core.logging.redactor import redact_secrets
        msg = "Normal log message"
        assert redact_secrets(msg) == msg


class TestSecretRedactingFormatter:
    def test_formatter_redacts_jwt(self) -> None:
        from semrush_core.logging.formatter import SecretRedactingFormatter
        fmt = SecretRedactingFormatter("%(message)s")
        rec = logging.LogRecord("test", logging.INFO, "test.py", 1,
            "Token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc", (), None)
        result = fmt.format(rec)
        assert "[REDACTED_JWT]" in result


class TestLoggerIntegration:
    def test_get_secure_logger(self) -> None:
        from semrush_core.logging import get_secure_logger
        logger = get_secure_logger("test")
        assert logger.name == "test"


class TestPatternCompilation:
    def test_patterns_compiled(self) -> None:
        from semrush_core.logging.redactor import SECRET_PATTERNS
        for pattern, _ in SECRET_PATTERNS:
            assert isinstance(pattern, re.Pattern)
