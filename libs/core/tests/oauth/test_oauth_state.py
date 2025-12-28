"""
Tests for OAuth state management.

Following TDD: These tests are written FIRST, then the implementation.
"""

from datetime import datetime
from unittest.mock import MagicMock

from semrush_core.oauth.state import OAuthState


class TestOAuthStateGeneration:
    """Tests for OAuth state token generation."""

    def test_generate_creates_unique_states(self):
        """Each call to generate should produce a unique state token."""
        state_mgr = OAuthState()
        state1 = state_mgr.generate("user1", "google")
        state2 = state_mgr.generate("user1", "google")
        assert state1 != state2

    def test_generate_creates_url_safe_token(self):
        """Generated state should be URL-safe base64."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google")
        # URL-safe base64 contains only alphanumeric, -, and _
        assert all(c.isalnum() or c in "-_" for c in state)

    def test_generate_creates_sufficient_entropy(self):
        """State tokens should have at least 32 bytes of entropy."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google")
        # 32 bytes = ~43 base64 chars
        assert len(state) >= 40

    def test_generate_stores_user_id(self):
        """Generated state should be associated with the user ID."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user123", "google")
        data = state_mgr.validate(state)
        assert data is not None
        assert data["user_id"] == "user123"

    def test_generate_stores_provider(self):
        """Generated state should be associated with the provider."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google")
        data = state_mgr.validate(state)
        assert data is not None
        assert data["provider"] == "google"

    def test_generate_stores_extra_metadata(self):
        """Extra metadata should be stored with the state."""
        state_mgr = OAuthState()
        extra = {"redirect": "/dashboard", "project_id": "proj123"}
        state = state_mgr.generate("user1", "google", extra=extra)
        data = state_mgr.validate(state)
        assert data is not None
        assert data["extra"]["redirect"] == "/dashboard"
        assert data["extra"]["project_id"] == "proj123"

    def test_generate_includes_timestamp(self):
        """State data should include creation timestamp."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google")
        data = state_mgr.validate(state)
        assert data is not None
        assert "created_at" in data
        # Should be parseable as ISO format
        datetime.fromisoformat(data["created_at"])


class TestOAuthStateValidation:
    """Tests for OAuth state token validation."""

    def test_validate_returns_metadata(self):
        """Validate should return the stored metadata."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google", {"redirect": "/dashboard"})
        data = state_mgr.validate(state)
        assert data is not None
        assert data["user_id"] == "user1"
        assert data["provider"] == "google"
        assert data["extra"]["redirect"] == "/dashboard"

    def test_validate_is_one_time_use(self):
        """State tokens should only be usable once."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google")
        first_validate = state_mgr.validate(state)
        second_validate = state_mgr.validate(state)
        assert first_validate is not None
        assert second_validate is None

    def test_validate_invalid_state_returns_none(self):
        """Invalid state tokens should return None."""
        state_mgr = OAuthState()
        assert state_mgr.validate("invalid_state") is None

    def test_validate_empty_string_returns_none(self):
        """Empty string state should return None."""
        state_mgr = OAuthState()
        assert state_mgr.validate("") is None

    def test_validate_tampered_state_returns_none(self):
        """Tampered state tokens should return None."""
        state_mgr = OAuthState()
        state = state_mgr.generate("user1", "google")
        # Tamper with the state
        tampered = state[:-1] + ("X" if state[-1] != "X" else "Y")
        assert state_mgr.validate(tampered) is None


class TestOAuthStateWithRedis:
    """Tests for OAuth state with Redis backend."""

    def test_redis_setex_called_on_generate(self):
        """Generate should store state in Redis with TTL."""
        mock_redis = MagicMock()
        state_mgr = OAuthState(redis_client=mock_redis, ttl_seconds=600)

        state = state_mgr.generate("user1", "google")

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"oauth_state:{state}"
        assert call_args[0][1] == 600

    def test_redis_get_called_on_validate(self):
        """Validate should retrieve state from Redis."""
        import json
        mock_redis = MagicMock()
        stored_data = json.dumps({
            "user_id": "user1",
            "provider": "google",
            "created_at": datetime.utcnow().isoformat(),
            "extra": {}
        })
        mock_redis.get.return_value = stored_data

        state_mgr = OAuthState(redis_client=mock_redis)
        data = state_mgr.validate("test_state")

        mock_redis.get.assert_called_once_with("oauth_state:test_state")
        assert data is not None
        assert data["user_id"] == "user1"

    def test_redis_delete_called_after_validate(self):
        """Validate should delete state from Redis (one-time use)."""
        import json
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({
            "user_id": "user1",
            "provider": "google",
            "created_at": datetime.utcnow().isoformat(),
            "extra": {}
        })

        state_mgr = OAuthState(redis_client=mock_redis)
        state_mgr.validate("test_state")

        mock_redis.delete.assert_called_once_with("oauth_state:test_state")

    def test_redis_get_returns_none_for_missing_state(self):
        """Validate should return None when Redis returns None."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        state_mgr = OAuthState(redis_client=mock_redis)
        data = state_mgr.validate("missing_state")

        assert data is None


class TestOAuthStateTTL:
    """Tests for OAuth state TTL configuration."""

    def test_default_ttl_is_600_seconds(self):
        """Default TTL should be 600 seconds (10 minutes)."""
        state_mgr = OAuthState()
        assert state_mgr.ttl == 600

    def test_custom_ttl_is_respected(self):
        """Custom TTL should be stored correctly."""
        state_mgr = OAuthState(ttl_seconds=300)
        assert state_mgr.ttl == 300

    def test_redis_uses_custom_ttl(self):
        """Redis setex should use the custom TTL."""
        mock_redis = MagicMock()
        state_mgr = OAuthState(redis_client=mock_redis, ttl_seconds=120)

        state_mgr.generate("user1", "google")

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 120
