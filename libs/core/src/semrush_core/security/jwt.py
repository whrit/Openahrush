"""
JWT token creation and verification.

Implements access tokens and refresh tokens using python-jose.
Tokens include standard claims plus custom user data.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from semrush_core.config import get_settings


class TokenData(BaseModel):
    """
    Decoded token payload data.

    Attributes:
        sub: Subject (user ID as string)
        exp: Expiration timestamp
        iat: Issued at timestamp
        jti: Unique token identifier
        token_type: Either "access" or "refresh"
        scopes: Optional list of permission scopes
    """

    sub: str = Field(..., description="Subject (user ID)")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    jti: str = Field(..., description="JWT ID (unique identifier)")
    token_type: str = Field(..., description="Token type (access/refresh)")
    scopes: list[str] = Field(default_factory=list, description="Permission scopes")

    @property
    def user_id(self) -> uuid.UUID:
        """Get user ID as UUID."""
        return uuid.UUID(self.sub)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(UTC) > self.exp


class TokenError(Exception):
    """Base exception for token-related errors."""

    pass


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""

    pass


class TokenInvalidError(TokenError):
    """Raised when a token is invalid or malformed."""

    pass


def create_access_token(
    subject: str | uuid.UUID,
    *,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: User identifier (usually user ID).
        scopes: Optional list of permission scopes.
        expires_delta: Custom expiration time (defaults to settings).
        extra_claims: Additional claims to include in the token.

    Returns:
        Encoded JWT access token string.

    Example:
        >>> token = create_access_token("user-123", scopes=["read", "write"])
        >>> token.count(".") == 2  # JWT has 3 parts
        True
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    return _create_token(
        subject=str(subject),
        token_type="access",
        expires_delta=expires_delta,
        scopes=scopes or [],
        extra_claims=extra_claims,
    )


def create_refresh_token(
    subject: str | uuid.UUID,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens have longer expiration and are used to obtain
    new access tokens without re-authentication.

    Args:
        subject: User identifier (usually user ID).
        expires_delta: Custom expiration time (defaults to settings).

    Returns:
        Encoded JWT refresh token string.
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    return _create_token(
        subject=str(subject),
        token_type="refresh",
        expires_delta=expires_delta,
        scopes=[],
        extra_claims=None,
    )


def decode_token(
    token: str,
    *,
    verify_exp: bool = True,
    required_type: str | None = None,
) -> TokenData:
    """
    Decode and validate a JWT token.

    Args:
        token: Encoded JWT token string.
        verify_exp: Whether to verify expiration (set False for expired token info).
        required_type: If set, validates the token_type claim matches.

    Returns:
        TokenData with decoded claims.

    Raises:
        TokenExpiredError: If the token has expired (and verify_exp=True).
        TokenInvalidError: If the token is malformed or signature is invalid.

    Example:
        >>> token = create_access_token("user-123")
        >>> data = decode_token(token)
        >>> data.sub
        'user-123'
    """
    settings = get_settings()

    options = {
        "verify_exp": verify_exp,
        "verify_iat": True,
        "verify_sub": True,
        "require_exp": True,
        "require_iat": True,
        "require_sub": True,
    }

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options=options,
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    except JWTError as e:
        raise TokenInvalidError(f"Invalid token: {e}") from e

    # Validate token type if required
    token_type = payload.get("token_type")
    if required_type is not None and token_type != required_type:
        raise TokenInvalidError(f"Expected {required_type} token, got {token_type}")

    return TokenData(
        sub=payload["sub"],
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        jti=payload.get("jti", ""),
        token_type=token_type or "access",
        scopes=payload.get("scopes", []),
    )


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    scopes: list[str],
    extra_claims: dict[str, Any] | None,
) -> str:
    """
    Internal helper to create JWT tokens.

    Args:
        subject: Token subject (user ID).
        token_type: Type of token (access/refresh).
        expires_delta: Time until expiration.
        scopes: Permission scopes.
        extra_claims: Additional claims.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    claims = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
        "token_type": token_type,
        "scopes": scopes,
    }

    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(
        claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
