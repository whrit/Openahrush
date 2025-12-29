"""
OAuth state management for CSRF protection.

Implements secure state token generation and validation for OAuth flows.
State tokens are single-use and time-limited to prevent replay attacks.
"""

import json
import logging
import secrets
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class OAuthState:
    """
    Manages OAuth state tokens for CSRF protection (synchronous version).

    State tokens are:
    - Cryptographically secure random values
    - Single-use (deleted after validation)
    - Time-limited (configurable TTL)
    - Associated with user and provider metadata

    Supports both Redis (production) and in-memory (testing) backends.

    Example:
        >>> state_mgr = OAuthState(redis_client=redis)
        >>> state = state_mgr.generate("user123", "google", {"redirect": "/dashboard"})
        >>> # Include state in OAuth authorization URL
        >>> # After callback:
        >>> data = state_mgr.validate(state)
        >>> if data:
        ...     user_id = data["user_id"]
        ...     provider = data["provider"]
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        ttl_seconds: int = 600,
    ) -> None:
        """
        Initialize OAuth state manager.

        Args:
            redis_client: Redis client instance. If None, uses in-memory storage.
            ttl_seconds: Time-to-live for state tokens in seconds. Default 600 (10 min).
        """
        self.redis = redis_client
        self.ttl = ttl_seconds
        self._memory_store: dict[str, dict[str, Any]] = {}  # Fallback for testing

    def generate(
        self,
        user_id: str,
        provider: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a secure state token and store associated metadata.

        Creates a cryptographically random token (32 bytes, URL-safe base64 encoded)
        and stores the associated metadata with a TTL.

        Args:
            user_id: ID of the user initiating the OAuth flow.
            provider: Name of the OAuth provider (e.g., "google", "microsoft").
            extra: Optional additional metadata to store with the state.

        Returns:
            URL-safe base64-encoded state token.

        Example:
            >>> state = state_mgr.generate(
            ...     user_id="user123",
            ...     provider="google",
            ...     extra={"redirect": "/dashboard", "project_id": "proj456"}
            ... )
        """
        state = secrets.token_urlsafe(32)
        data: dict[str, Any] = {
            "user_id": user_id,
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "extra": extra or {},
        }

        if self.redis is not None:
            self.redis.setex(
                f"oauth_state:{state}",
                self.ttl,
                json.dumps(data),
            )
        else:
            self._memory_store[state] = data

        return state

    def validate(self, state: str) -> dict[str, Any] | None:
        """
        Validate a state token and return its metadata.

        This is a single-use operation: the state token is deleted after
        successful validation to prevent replay attacks.

        Args:
            state: The state token to validate.

        Returns:
            Dictionary containing the stored metadata if valid, None otherwise.
            Returns None if:
            - State token is empty or invalid
            - State token has expired
            - State token has already been used

        Example:
            >>> data = state_mgr.validate(state)
            >>> if data:
            ...     print(f"User: {data['user_id']}, Provider: {data['provider']}")
            ... else:
            ...     print("Invalid or expired state token")
        """
        if not state:
            return None

        if self.redis is not None:
            raw_data = self.redis.get(f"oauth_state:{state}")
            if raw_data:
                self.redis.delete(f"oauth_state:{state}")  # One-time use
                result: dict[str, Any] = json.loads(raw_data)
                return result
            return None
        else:
            return self._memory_store.pop(state, None)


class AsyncOAuthStateManager:
    """
    Async OAuth state manager with Redis backend and in-memory fallback.

    Provides async methods for storing and validating OAuth state tokens.
    Uses Redis as the primary backing store for production (multi-instance safe).
    Falls back to in-memory storage when Redis is unavailable (for testing).

    State tokens are:
    - Cryptographically secure random values (32 bytes, URL-safe base64)
    - Single-use (deleted after validation to prevent replay attacks)
    - Time-limited with configurable TTL (default 10 minutes)
    - Associated with user ID and provider metadata

    Example:
        >>> from redis.asyncio import Redis
        >>> redis = Redis.from_url("redis://localhost:6379/0")
        >>> state_mgr = AsyncOAuthStateManager(redis)
        >>> state = await state_mgr.generate("user-uuid", "google_search_console")
        >>> # Include state in OAuth authorization URL
        >>> # After callback:
        >>> data = await state_mgr.validate(state)
        >>> if data:
        ...     user_id = data["user_id"]
        ...     provider = data["provider"]
    """

    # Redis key prefix for OAuth state tokens
    KEY_PREFIX = "oauth_state:"

    def __init__(
        self,
        redis_client: Any | None = None,
        ttl_seconds: int = 600,
    ) -> None:
        """
        Initialize async OAuth state manager.

        Args:
            redis_client: Async Redis client instance (from redis.asyncio).
                         If None, uses in-memory storage (for testing).
            ttl_seconds: Time-to-live for state tokens in seconds. Default 600 (10 min).
        """
        self._redis = redis_client
        self._ttl = ttl_seconds
        # In-memory fallback for testing or when Redis is unavailable
        self._memory_store: dict[str, dict[str, Any]] = {}
        self._use_memory = redis_client is None

    async def generate(
        self,
        user_id: str,
        provider: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a secure state token and store associated metadata.

        Creates a cryptographically random token (32 bytes, URL-safe base64 encoded)
        and stores the associated metadata with a TTL.

        Args:
            user_id: ID of the user initiating the OAuth flow.
            provider: Name of the OAuth provider (e.g., "google_search_console").
            extra: Optional additional metadata to store with the state.

        Returns:
            URL-safe base64-encoded state token.
        """
        state = secrets.token_urlsafe(32)
        data: dict[str, Any] = {
            "user_id": user_id,
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "extra": extra or {},
        }

        if self._use_memory:
            self._memory_store[state] = data
        else:
            try:
                key = f"{self.KEY_PREFIX}{state}"
                await self._redis.setex(key, self._ttl, json.dumps(data))
            except Exception as e:
                # Fall back to in-memory if Redis fails
                logger.warning(f"Redis unavailable, falling back to in-memory: {e}")
                self._use_memory = True
                self._memory_store[state] = data

        return state

    async def validate(self, state: str) -> dict[str, Any] | None:
        """
        Validate a state token and return its metadata.

        This is a single-use operation: the state token is deleted after
        successful validation to prevent replay attacks.

        Args:
            state: The state token to validate.

        Returns:
            Dictionary containing the stored metadata if valid, None otherwise.
            Returns None if:
            - State token is empty or invalid
            - State token has expired
            - State token has already been used
        """
        if not state:
            return None

        if self._use_memory:
            return self._memory_store.pop(state, None)

        try:
            key = f"{self.KEY_PREFIX}{state}"

            # Use GETDEL for atomic get-and-delete (Redis 6.2+)
            # Falls back to GET + DELETE if GETDEL not available
            try:
                raw_data = await self._redis.getdel(key)
            except Exception:
                # Fallback for older Redis versions
                raw_data = await self._redis.get(key)
                if raw_data:
                    await self._redis.delete(key)

            if raw_data:
                result: dict[str, Any] = json.loads(raw_data)
                return result

            return None
        except Exception as e:
            # Fall back to in-memory if Redis fails
            logger.warning(f"Redis unavailable, falling back to in-memory: {e}")
            self._use_memory = True
            return self._memory_store.pop(state, None)

    async def exists(self, state: str) -> bool:
        """
        Check if a state token exists without consuming it.

        Useful for validation checks before processing callback.

        Args:
            state: The state token to check.

        Returns:
            True if the state token exists and has not expired.
        """
        if not state:
            return False

        if self._use_memory:
            return state in self._memory_store

        try:
            key = f"{self.KEY_PREFIX}{state}"
            return bool(await self._redis.exists(key))
        except Exception:
            return state in self._memory_store
