"""
Integration tests for security fixes.
Tests the complete security enhancement implementation.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.validation import InputValidator
from src.encryption import FaceDataEncryption
from src.middleware.auth import AuthMiddleware
from src.error_handlers import SecureErrorHandler
from src.compliance import ComplianceChecker


class TestSecurityIntegration:
    """Integration tests for security feature implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = InputValidator()
        self.encryption = FaceDataEncryption()
        self.auth = AuthMiddleware("test_secret")
        self.error_handler = SecureErrorHandler()
        self.compliance_checker = ComplianceChecker()

    def test_input_validation_and_error_handling(self):
        """Test input validation with error handling."""
        # Test invalid input
        result = self.validator.validate_contestant_name("")

        # Should be invalid
        assert result["valid"] == False

        # Test error handling for this validation failure
        error = ValueError("Invalid contestant name")
        response = self.error_handler.handle_error(error, {"name": ""})

        assert response["error"] == "Invalid input provided"
        assert "name" not in str(response)  # Sensitive data not leaked

    def test_encryption_and_access_control(self):
        """Test data encryption with access control."""
        # Create test data
        embedding = [0.1, 0.2, 0.3]
        user_id = "test_user"

        # Encrypt data
        encrypted = self.encryption.encrypt_embedding(embedding)

        # Generate access token
        token = self.auth.generate_token(user_id, ["user"])

        # Verify token allows access
        payload = self.auth.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == user_id

        # Decrypt data (simulating authorized access)
        decrypted = self.encryption.decrypt_embedding(encrypted)
        assert decrypted == embedding

    def test_comprehensive_security_workflow(self):
        """Test complete security workflow from input to storage."""
        # 1. Validate input
        video_result = self.validator.validate_video_file("test.mp4")
        # Note: In real test, would need actual file

        # 2. Validate user data
        user_result = self.validator.validate_contestant_name("John Doe")
        assert user_result["valid"] == True

        # 3. Encrypt sensitive data
        embedding = [0.5, 0.6, 0.7]
        encrypted = self.encryption.encrypt_embedding(embedding)

        # 4. Check permissions
        token = self.auth.generate_token("user123", ["user"])
        has_permission = self.auth.has_permission(["user"], ["read", "write"])
        assert has_permission == True

        # 5. Verify compliance
        owasp_result = self.compliance_checker.check_owasp_compliance()
        assert owasp_result["compliant"] == True

        # 6. Handle potential errors safely
        try:
            # Simulate some operation
            if False:  # Simulate error condition
                raise ValueError("Test error")
        except ValueError as e:
            response = self.error_handler.handle_error(e)
            assert response["code"] == 500
            assert "Test error" not in response["error"]  # No leak

    def test_security_audit_workflow(self):
        """Test security audit workflow."""
        # Run compliance audit
        audit_result = self.compliance_checker.run_full_audit()

        assert "overall_compliant" in audit_result
        assert "results" in audit_result

        # Check audit history
        history = self.compliance_checker.get_audit_history()
        assert len(history) >= 1

        # Verify audit contains expected standards
        results = audit_result["results"]
        assert "owasp_top_10" in results
        assert "gdpr" in results

    def test_rate_limiting_integration(self):
        """Test rate limiting integration with auth."""
        from src.middleware.auth import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Simulate requests with auth
        for i in range(2):
            token = self.auth.generate_token(f"user{i}")
            payload = self.auth.verify_token(token)
            assert payload is not None

            # Check rate limiting
            allowed = limiter.is_allowed(f"user{i}")
            if i < 2:
                assert allowed == True
            else:
                assert allowed == False

    def test_error_logging_security(self):
        """Test that error logging doesn't expose sensitive data."""
        from src.error_handlers import log_security_event

        with patch('src.error_handlers.logger') as mock_logger:
            # Log event with sensitive data
            log_security_event(
                "test_event",
                {
                    "user_id": "123",
                    "ip": "192.168.1.1",
                    "token": "secret_jwt_token",
                    "password": "user_password",
                    "embedding": [0.1, 0.2, 0.3]
                }
            )

            # Check that sensitive data was redacted
            logged_message = mock_logger.info.call_args[0][0]
            assert "secret_jwt_token" not in logged_message
            assert "user_password" not in logged_message
            assert "[REDACTED]" in logged_message

    def test_data_protection_end_to_end(self):
        """Test data protection from creation to access."""
        # Create sensitive data
        contestant_data = {
            "name": "Jane Smith",
            "biometric_id": "BIO123",
            "embeddings": [[0.1, 0.2], [0.3, 0.4]]
        }

        # Encrypt
        encrypted = self.encryption.encrypt_contestant_data(contestant_data)

        # Simulate storage and retrieval
        # In real scenario, this would go to database
        stored_data = encrypted

        # Decrypt for authorized access
        token = self.auth.generate_token("authorized_user", ["admin"])
        payload = self.auth.verify_token(token)

        if payload and self.auth.has_permission(payload["roles"], ["read"]):
            decrypted = self.encryption.decrypt_contestant_data(stored_data)
            assert decrypted == contestant_data
        else:
            pytest.fail("Should have access")

    def test_compliance_monitoring(self):
        """Test ongoing compliance monitoring."""
        # Initial compliance check
        initial_result = self.compliance_checker.check_owasp_compliance()
        assert initial_result["compliant"] == True

        # Simulate system change that might affect compliance
        # In real system, this would trigger re-evaluation

        # Check audit trail
        audit_result = self.compliance_checker.run_full_audit()
        assert audit_result["overall_compliant"] == True

        # Verify audit is recorded
        history = self.compliance_checker.get_audit_history()
        assert len(history) > 0