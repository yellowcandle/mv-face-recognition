"""
Contract tests for error handling functionality.
Tests the SecureErrorHandler class against defined contracts.
"""

import pytest
from unittest.mock import patch
from src.error_handlers import SecureErrorHandler, create_error_response, log_security_event, ErrorSeverity


class TestSecureErrorHandler:
    """Test suite for SecureErrorHandler contract compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = SecureErrorHandler()

    def test_handle_value_error(self):
        """Test handling of ValueError."""
        error = ValueError("Invalid input value")
        response = self.handler.handle_error(error)

        assert response["error"] == "Invalid input provided"
        assert response["code"] == 500
        assert response["type"] == "server_error"

    def test_handle_permission_error(self):
        """Test handling of PermissionError."""
        error = PermissionError("Access denied")
        response = self.handler.handle_error(error)

        assert response["error"] == "Access denied"
        assert response["code"] == 500

    def test_handle_generic_error(self):
        """Test handling of generic exceptions."""
        error = RuntimeError("Something went wrong")
        response = self.handler.handle_error(error)

        assert response["error"] == "An error occurred"
        assert response["code"] == 500

    def test_handle_error_with_context(self):
        """Test error handling with context information."""
        error = KeyError("missing_key")
        context = {"user_id": "12345", "action": "read_data", "password": "secret123"}

        with patch('src.error_handlers.logger') as mock_logger:
            response = self.handler.handle_error(error, context)

            # Check that sensitive data was sanitized in logs
            mock_logger.error.assert_called()
            call_args = mock_logger.error.call_args[0]
            log_message = call_args[0]
            assert "password" not in log_message.lower()
            assert "[REDACTED]" in log_message

    def test_determine_severity_levels(self):
        """Test error severity determination."""
        # Low severity
        assert self.handler._determine_severity(ValueError("test")) == ErrorSeverity.LOW
        assert self.handler._determine_severity(TypeError("test")) == ErrorSeverity.LOW

        # Medium severity
        assert self.handler._determine_severity(KeyError("test")) == ErrorSeverity.MEDIUM

        # High severity
        assert self.handler._determine_severity(PermissionError("test")) == ErrorSeverity.HIGH
        assert self.handler._determine_severity(ConnectionError("test")) == ErrorSeverity.HIGH

        # Critical severity
        error_with_security = ValueError("Security breach detected")
        assert self.handler._determine_severity(error_with_security) == ErrorSeverity.CRITICAL

    def test_sanitize_context(self):
        """Test context sanitization."""
        context = {
            "user_id": "123",
            "name": "John Doe",
            "token": "secret_token_123",
            "password": "my_password",
            "embedding": [0.1, 0.2, 0.3],
            "normal_data": "safe_value"
        }

        sanitized = self.handler._sanitize_context(context)

        # Sensitive fields should be redacted
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["embedding"] == "[REDACTED]"

        # Normal fields should be preserved
        assert sanitized["user_id"] == "123"
        assert sanitized["name"] == "John Doe"
        assert sanitized["normal_data"] == "safe_value"

    def test_create_safe_response(self):
        """Test safe response creation."""
        response = self.handler._create_safe_response(ValueError("test"))
        assert "error" in response
        assert "code" in response
        assert "type" in response
        assert response["error"] != "test"  # Original message should not leak


class TestErrorResponseUtilities:
    """Test suite for error response utility functions."""

    def test_create_error_response(self):
        """Test error response creation."""
        response = create_error_response("Custom error", 400, "validation_error")

        assert response["error"] == "Custom error"
        assert response["code"] == 400
        assert response["type"] == "validation_error"

    def test_log_security_event(self):
        """Test security event logging."""
        with patch('src.error_handlers.logger') as mock_logger:
            log_security_event(
                "unauthorized_access",
                {"user_id": "123", "ip": "192.168.1.1", "token": "secret"},
                ErrorSeverity.HIGH
            )

            # Check that security event was logged
            mock_logger.error.assert_called()
            call_args = mock_logger.error.call_args[0]
            assert "Security Event" in call_args[0]
            assert "unauthorized_access" in call_args[0]
            # Sensitive data should be redacted
            assert "secret" not in call_args[0]

    def test_log_security_event_different_severities(self):
        """Test security event logging with different severities."""
        with patch('src.error_handlers.logger') as mock_logger:
            # Critical
            log_security_event("breach", {}, ErrorSeverity.CRITICAL)
            mock_logger.critical.assert_called()

            # High
            log_security_event("suspicious", {}, ErrorSeverity.HIGH)
            mock_logger.error.assert_called()

            # Medium
            log_security_event("warning", {}, ErrorSeverity.MEDIUM)
            mock_logger.warning.assert_called()

            # Low
            log_security_event("info", {}, ErrorSeverity.LOW)
            mock_logger.info.assert_called()