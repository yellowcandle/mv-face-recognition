"""
Contract tests for access control functionality.
Tests the AuthMiddleware class against defined contracts.
"""

import pytest
import time
from unittest.mock import patch
from src.middleware.auth import AuthMiddleware, RateLimiter


class TestAuthMiddleware:
    """Test suite for AuthMiddleware contract compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.secret_key = "test_secret_key_12345"
        self.auth = AuthMiddleware(self.secret_key)

    def test_generate_token(self):
        """Test JWT token generation."""
        user_id = "user123"
        roles = ["user", "admin"]

        token = self.auth.generate_token(user_id, roles)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = self.auth.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == user_id
        assert payload["roles"] == roles
        assert "exp" in payload
        assert "iat" in payload

    def test_generate_token_default_roles(self):
        """Test token generation with default roles."""
        user_id = "user456"

        token = self.auth.generate_token(user_id)
        payload = self.auth.verify_token(token)

        assert payload["roles"] == ["user"]

    def test_verify_valid_token(self):
        """Test verification of valid token."""
        user_id = "test_user"
        token = self.auth.generate_token(user_id, ["moderator"])

        payload = self.auth.verify_token(token)

        assert payload is not None
        assert payload["user_id"] == user_id
        assert payload["roles"] == ["moderator"]

    def test_verify_expired_token(self):
        """Test verification rejects expired tokens."""
        # Create token with very short expiry
        with patch.object(self.auth, 'token_expiry_hours', 0):
            token = self.auth.generate_token("user")

        # Wait a bit for expiry
        time.sleep(0.1)

        payload = self.auth.verify_token(token)
        assert payload is None

    def test_verify_invalid_token(self):
        """Test verification rejects invalid tokens."""
        payload = self.auth.verify_token("invalid.token.here")
        assert payload is None

        payload = self.auth.verify_token("")
        assert payload is None

    def test_verify_token_wrong_secret(self):
        """Test verification rejects tokens with wrong secret."""
        other_auth = AuthMiddleware("different_secret")
        token = other_auth.generate_token("user")

        payload = self.auth.verify_token(token)
        assert payload is None

    def test_has_permission(self):
        """Test permission checking."""
        # Admin should have all permissions
        assert self.auth.has_permission(["admin"], ["read", "write", "delete"])
        assert self.auth.has_permission(["admin"], ["manage_users"])

        # User should have basic permissions
        assert self.auth.has_permission(["user"], ["read", "write"])
        assert not self.auth.has_permission(["user"], ["delete"])

        # Moderator permissions
        assert self.auth.has_permission(["moderator"], ["read", "write"])
        assert self.auth.has_permission(["moderator"], ["view_logs"])
        assert not self.auth.has_permission(["moderator"], ["manage_users"])

        # Viewer permissions
        assert self.auth.has_permission(["viewer"], ["read"])
        assert not self.auth.has_permission(["viewer"], ["write"])

    def test_has_permission_multiple_roles(self):
        """Test permission checking with multiple roles."""
        # User with multiple roles gets combined permissions
        roles = ["user", "moderator"]
        assert self.auth.has_permission(roles, ["read", "write", "view_logs"])
        assert not self.auth.has_permission(roles, ["manage_users"])

    def test_validate_api_key_valid(self):
        """Test API key validation with valid key."""
        result = self.auth.validate_api_key("service_key_123")
        assert result is not None
        assert result["service"] == "face_processor"
        assert "permissions" in result

    def test_validate_api_key_invalid(self):
        """Test API key validation with invalid key."""
        result = self.auth.validate_api_key("invalid_key")
        assert result is None

        result = self.auth.validate_api_key("")
        assert result is None


class TestRateLimiter:
    """Test suite for RateLimiter contract compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.limiter = RateLimiter(max_requests=3, window_seconds=1)

    def test_allow_initial_requests(self):
        """Test rate limiter allows initial requests."""
        assert self.limiter.is_allowed("client1") == True
        assert self.limiter.is_allowed("client1") == True
        assert self.limiter.is_allowed("client1") == True

    def test_block_after_limit(self):
        """Test rate limiter blocks requests after limit."""
        client = "client2"

        # Use up the limit
        for _ in range(3):
            assert self.limiter.is_allowed(client) == True

        # Next request should be blocked
        assert self.limiter.is_allowed(client) == False

    def test_allow_after_window(self):
        """Test rate limiter allows requests after window expires."""
        client = "client3"

        # Use up the limit
        for _ in range(3):
            assert self.limiter.is_allowed(client) == True

        # Wait for window to expire
        time.sleep(1.1)

        # Should allow again
        assert self.limiter.is_allowed(client) == True

    def test_different_clients_isolated(self):
        """Test rate limiter isolates different clients."""
        # Client 1 uses up limit
        for _ in range(3):
            assert self.limiter.is_allowed("client_a") == True

        # Client 2 should still be allowed
        assert self.limiter.is_allowed("client_b") == True
        assert self.limiter.is_allowed("client_b") == True
        assert self.limiter.is_allowed("client_b") == True

        # Client 1 still blocked
        assert self.limiter.is_allowed("client_a") == False