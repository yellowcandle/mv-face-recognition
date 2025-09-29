"""
Performance tests for security functions.
Ensures security operations meet performance requirements (<200ms).
"""

import time
import pytest
from src.encryption import FaceDataEncryption
from src.middleware.auth import AuthMiddleware, RateLimiter
from src.validation import InputValidator


class TestSecurityPerformance:
    """Performance tests for security components."""

    def setup_method(self):
        """Set up test fixtures."""
        self.encryption = FaceDataEncryption()
        self.auth = AuthMiddleware(secret_key="test_key")
        self.validator = InputValidator()
        self.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

    def test_encryption_performance(self):
        """Test encryption/decryption performance."""
        embedding = [0.1] * 512  # Typical face embedding size

        # Test encryption performance
        start_time = time.time()
        encrypted = self.encryption.encrypt_embedding(embedding)
        encrypt_time = time.time() - start_time

        # Test decryption performance
        start_time = time.time()
        decrypted = self.encryption.decrypt_embedding(encrypted)
        decrypt_time = time.time() - start_time

        # Assert performance requirements (<200ms each)
        assert encrypt_time < 0.2, f"Encryption too slow: {encrypt_time:.3f}s"
        assert decrypt_time < 0.2, f"Decryption too slow: {decrypt_time:.3f}s"

        # Verify correctness
        assert decrypted == embedding

    def test_auth_token_performance(self):
        """Test JWT token generation and verification performance."""
        user_id = "test_user_123"
        roles = ["user", "moderator"]

        # Test token generation
        start_time = time.time()
        token = self.auth.generate_token(user_id, roles)
        gen_time = time.time() - start_time

        # Test token verification
        start_time = time.time()
        payload = self.auth.verify_token(token)
        verify_time = time.time() - start_time

        # Assert performance requirements
        assert gen_time < 0.1, f"Token generation too slow: {gen_time:.3f}s"
        assert verify_time < 0.1, f"Token verification too slow: {verify_time:.3f}s"

        # Verify correctness
        assert payload is not None
        assert payload["user_id"] == user_id
        assert set(payload["roles"]) == set(roles)

    def test_rate_limiting_performance(self):
        """Test rate limiter performance."""
        client_id = "test_client"

        # Test rate limit checking performance
        times = []
        allowed = True
        for _ in range(10):
            start_time = time.time()
            allowed = self.rate_limiter.is_allowed(client_id)
            check_time = time.time() - start_time
            times.append(check_time)

        avg_time = sum(times) / len(times)

        # Assert performance requirements (<50ms per check)
        assert avg_time < 0.05, f"Rate limiting too slow: {avg_time:.3f}s average"
        assert allowed, "Rate limiting should allow requests within limit"

    def test_validation_performance(self):
        """Test input validation performance."""
        import tempfile
        import os

        # Test video file validation (create temp files)
        temp_files = []
        try:
            # Create test files
            for ext in ['.mp4', '.exe']:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                    f.write(b'test content')
                    temp_files.append(f.name)

            start_time = time.time()
            for file_path in temp_files:
                result = self.validator.validate_video_file(file_path)
            filename_time = time.time() - start_time

        finally:
            for f in temp_files:
                os.unlink(f)

        # Test contestant name validation
        names = ["John Doe", "张三", "", "A" * 101, "<script>alert('xss')</script>"]

        start_time = time.time()
        for name in names:
            result = self.validator.validate_contestant_name(name)
        name_time = time.time() - start_time

        # Test API input validation
        inputs = [
            {"video_id": "123", "contestant_name": "John"},
            {"video_id": "123", "__import__": "os"},  # Dangerous
            {"name": "<script>alert('xss')</script>"}  # XSS
        ]

        start_time = time.time()
        for data in inputs:
            result = self.validator.validate_api_input(data)
        api_time = time.time() - start_time

        # Assert performance requirements (<100ms total for batch)
        assert filename_time < 0.1, f"File validation too slow: {filename_time:.3f}s"
        assert name_time < 0.1, f"Name validation too slow: {name_time:.3f}s"
        assert api_time < 0.1, f"API validation too slow: {api_time:.3f}s"

    def test_bulk_encryption_performance(self):
        """Test bulk encryption performance for multiple embeddings."""
        embeddings = [[0.1 * i] * 512 for i in range(10)]  # 10 embeddings

        start_time = time.time()
        encrypted_list = []
        for embedding in embeddings:
            encrypted = self.encryption.encrypt_embedding(embedding)
            encrypted_list.append(encrypted)
        encrypt_time = time.time() - start_time

        start_time = time.time()
        decrypted_list = []
        for encrypted in encrypted_list:
            decrypted = self.encryption.decrypt_embedding(encrypted)
            decrypted_list.append(decrypted)
        decrypt_time = time.time() - start_time

        # Assert performance requirements (<2s for 10 embeddings)
        assert encrypt_time < 2.0, f"Bulk encryption too slow: {encrypt_time:.3f}s"
        assert decrypt_time < 2.0, f"Bulk decryption too slow: {decrypt_time:.3f}s"

        # Verify correctness
        assert decrypted_list == embeddings

    @pytest.mark.parametrize("num_tokens", [10, 50, 100])
    def test_auth_bulk_verification_performance(self, num_tokens):
        """Test bulk token verification performance."""
        # Generate multiple tokens
        tokens = []
        user_ids = []
        for i in range(num_tokens):
            user_id = f"user_{i}"
            user_ids.append(user_id)
            token = self.auth.generate_token(user_id, ["user"])
            tokens.append(token)

        # Test bulk verification
        start_time = time.time()
        payloads = []
        for token in tokens:
            payload = self.auth.verify_token(token)
            payloads.append(payload)
        verify_time = time.time() - start_time

        # Assert performance requirements (scale with number of tokens)
        max_time = 0.5 + (num_tokens * 0.01)  # 500ms base + 10ms per token
        assert verify_time < max_time, f"Bulk verification too slow: {verify_time:.3f}s for {num_tokens} tokens"

        # Verify correctness
        for i, payload in enumerate(payloads):
            assert payload is not None
            assert payload["user_id"] == user_ids[i]

    def test_memory_usage_stability(self):
        """Test that security operations don't have memory leaks."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform many security operations
        for i in range(100):
            embedding = [0.1 * (i % 10)] * 128
            encrypted = self.encryption.encrypt_embedding(embedding)
            decrypted = self.encryption.decrypt_embedding(encrypted)

            token = self.auth.generate_token(f"user_{i}")
            payload = self.auth.verify_token(token)

            assert decrypted == embedding
            assert payload is not None

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Assert memory usage is reasonable (<50MB increase)
        assert memory_increase < 50, f"Memory leak detected: {memory_increase:.1f}MB increase"