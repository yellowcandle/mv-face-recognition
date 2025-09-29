"""
Unit tests for security functions and utilities.
Tests encryption, authentication, and security helpers.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from src.encryption import FaceDataEncryption
from src.middleware.auth import AuthMiddleware, RateLimiter
from src.validation import InputValidator
from src.error_handlers import SecureErrorHandler, create_error_response
from src.compliance import ComplianceChecker


class TestFaceDataEncryption:
    """Test face data encryption functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.encryption = FaceDataEncryption(master_key="test_key_123")

    def test_encrypt_decrypt_embedding(self):
        """Test encryption and decryption of face embeddings."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Encrypt
        encrypted = self.encryption.encrypt_embedding(embedding)
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

        # Decrypt
        decrypted = self.encryption.decrypt_embedding(encrypted)
        assert decrypted == embedding

    def test_encrypt_decrypt_invalid_data(self):
        """Test encryption/decryption with invalid data."""
        with pytest.raises(ValueError, match="Embedding must be a list of numbers"):
            self.encryption.encrypt_embedding("not a list")

        with pytest.raises(ValueError, match="Embedding must be a list of numbers"):
            self.encryption.encrypt_embedding([0.1, "invalid", 0.3])

    def test_decrypt_corrupted_data(self):
        """Test decryption of corrupted data."""
        with pytest.raises(ValueError, match="Failed to decrypt embedding"):
            self.encryption.decrypt_embedding("corrupted_data")

    def test_encrypt_decrypt_contestant_data(self):
        """Test encryption/decryption of contestant data."""
        data = {"name": "John Doe", "age": 25, "id": 123}

        # Encrypt
        encrypted = self.encryption.encrypt_contestant_data(data)
        assert isinstance(encrypted, str)

        # Decrypt
        decrypted = self.encryption.decrypt_contestant_data(encrypted)
        assert decrypted == data

    def test_backup_and_restore(self):
        """Test backup and restore of encryption keys."""
        # Get backup info
        master_key = self.encryption.get_master_key()
        salt = self.encryption.get_salt()

        # Create new instance from backup
        restored = FaceDataEncryption.from_backup(master_key, salt)

        # Test that they can decrypt each other's data
        embedding = [1.0, 2.0, 3.0]
        encrypted = self.encryption.encrypt_embedding(embedding)
        decrypted = restored.decrypt_embedding(encrypted)
        assert decrypted == embedding


class TestAuthMiddleware:
    """Test authentication middleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth = AuthMiddleware(secret_key="test_secret_key")

    def test_generate_token(self):
        """Test JWT token generation."""
        token = self.auth.generate_token("user123", ["user", "admin"])
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self):
        """Test verification of valid token."""
        token = self.auth.generate_token("user123", ["user"])
        payload = self.auth.verify_token(token)

        assert payload is not None
        assert payload["user_id"] == "user123"
        assert "user" in payload["roles"]

    def test_verify_expired_token(self):
        """Test verification of expired token."""
        # Create token with negative expiry
        import time
        import jwt

        payload = {
            "user_id": "user123",
            "roles": ["user"],
            "iat": int(time.time()),
            "exp": int(time.time()) - 3600  # Expired 1 hour ago
        }
        token = jwt.encode(payload, "test_secret_key", algorithm="HS256")

        result = self.auth.verify_token(token)
        assert result is None

    def test_verify_invalid_token(self):
        """Test verification of invalid token."""
        result = self.auth.verify_token("invalid_token")
        assert result is None

    def test_has_permission(self):
        """Test permission checking."""
        # Admin should have all permissions
        assert self.auth.has_permission(["admin"], ["read", "write", "delete"])
        assert self.auth.has_permission(["admin"], ["manage_users"])

        # User should have basic permissions
        assert self.auth.has_permission(["user"], ["read", "write"])
        assert not self.auth.has_permission(["user"], ["delete"])

        # Viewer should have read only
        assert self.auth.has_permission(["viewer"], ["read"])
        assert not self.auth.has_permission(["viewer"], ["write"])

    def test_validate_api_key(self):
        """Test API key validation."""
        valid_key = self.auth.validate_api_key("service_key_123")
        assert valid_key is not None
        assert valid_key["service"] == "face_processor"

        invalid_key = self.auth.validate_api_key("invalid_key")
        assert invalid_key is None


class TestRateLimiter:
    """Test rate limiting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.limiter = RateLimiter(max_requests=3, window_seconds=60)

    def test_allow_requests_within_limit(self):
        """Test allowing requests within rate limit."""
        client_id = "test_client"

        # Should allow first 3 requests
        assert self.limiter.is_allowed(client_id)
        assert self.limiter.is_allowed(client_id)
        assert self.limiter.is_allowed(client_id)

    def test_block_requests_over_limit(self):
        """Test blocking requests over rate limit."""
        client_id = "test_client"

        # Use up the limit
        for _ in range(3):
            assert self.limiter.is_allowed(client_id)

        # Should block the 4th request
        assert not self.limiter.is_allowed(client_id)

    def test_reset_after_window(self):
        """Test rate limit reset after time window."""
        client_id = "test_client"

        # Use up limit
        for _ in range(3):
            self.limiter.is_allowed(client_id)

        # Simulate time passing (mock time)
        with patch('time.time', return_value=int(time.time()) + 61):
            # Should allow again after window
            assert self.limiter.is_allowed(client_id)


class TestInputValidator:
    """Test input validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = InputValidator()

    def test_validate_video_file(self):
        """Test video file validation."""
        # Valid files (create temp files for testing)
        import tempfile
        import os

        # Create a valid mp4 file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'test video content')
            valid_file = f.name

        try:
            result = self.validator.validate_video_file(valid_file)
            assert result['valid'] is True
            assert result['error'] is None
        finally:
            os.unlink(valid_file)

        # Invalid file extension
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as f:
            f.write(b'test content')
            invalid_file = f.name

        try:
            result = self.validator.validate_video_file(invalid_file)
            assert result['valid'] is False
            assert 'Invalid file type' in result['error']
        finally:
            os.unlink(invalid_file)

    def test_validate_contestant_name(self):
        """Test contestant name validation."""
        # Valid names
        result = self.validator.validate_contestant_name("John Doe")
        assert result['valid'] is True
        assert result['sanitized'] == "John Doe"

        result = self.validator.validate_contestant_name("张三")
        assert result['valid'] is True

        # Invalid names
        result = self.validator.validate_contestant_name("")
        assert result['valid'] is False
        assert "non-empty string" in result['error']

        result = self.validator.validate_contestant_name("A" * 101)
        assert result['valid'] is False
        assert "too long" in result['error']

        result = self.validator.validate_contestant_name("<script>alert('xss')</script>")
        assert result['valid'] is False
        assert "invalid characters" in result['error']

    def test_validate_api_input(self):
        """Test API input validation."""
        # Valid input
        valid_data = {"video_id": "123", "contestant_name": "John"}
        result = self.validator.validate_api_input(valid_data)
        assert result['valid'] is True

        # Dangerous key
        invalid_data = {"video_id": "123", "__import__": "os"}
        result = self.validator.validate_api_input(invalid_data)
        assert result['valid'] is False
        assert "Dangerous key" in result['error']

        # XSS content
        xss_data = {"name": "<script>alert('xss')</script>"}
        result = self.validator.validate_api_input(xss_data)
        assert result['valid'] is True  # Should sanitize, not reject
        assert result['sanitized']['name'] == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"


class TestSecureErrorHandler:
    """Test secure error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = SecureErrorHandler()

    def test_create_error_response(self):
        """Test creation of secure error responses."""
        response = create_error_response("Test error", 400)

        assert response['code'] == 400
        assert response['error'] == "Test error"
        assert response['type'] == 'server_error'

    def test_log_security_event(self):
        """Test security event logging."""
        with patch('src.error_handlers.logger') as mock_logger:
            from src.error_handlers import log_security_event, ErrorSeverity

            log_security_event("Test security event", {"user": "test"}, ErrorSeverity.MEDIUM)

            mock_logger.warning.assert_called_once()
            args = mock_logger.warning.call_args
            assert "Test security event" in str(args)
            assert "Details:" in str(args)


class TestComplianceChecker:
    """Test compliance checking functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = ComplianceChecker()

    def test_check_owasp_compliance(self):
        """Test OWASP compliance checking."""
        result = self.checker.check_owasp_compliance()
        assert isinstance(result, dict)
        assert "compliant" in result
        assert "checks" in result
        assert "score" in result

    def test_check_gdpr_compliance(self):
        """Test GDPR compliance checking."""
        result = self.checker.check_gdpr_compliance()
        assert isinstance(result, dict)
        assert "compliant" in result
        assert "checks" in result
        assert "score" in result

    def test_compliance_initialization(self):
        """Test compliance checker initialization."""
        assert self.checker.last_audit is None
        assert isinstance(self.checker.audit_results, dict)