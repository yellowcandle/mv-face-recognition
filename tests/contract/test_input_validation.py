"""
Contract tests for input validation functionality.
Tests the InputValidator class against defined contracts.
"""

import pytest
import tempfile
import os
from unittest.mock import patch
from src.validation import InputValidator


class TestInputValidator:
    """Test suite for InputValidator contract compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = InputValidator()

    def test_validate_video_file_valid_extension(self):
        """Test validation of video file with valid extension."""
        # Create a temporary file with valid extension
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp.write(b'test video content')
            tmp_path = tmp.name

        try:
            result = self.validator.validate_video_file(tmp_path)
            assert result["valid"] == True
            assert result["error"] is None
        finally:
            os.unlink(tmp_path)

    def test_validate_video_file_invalid_extension(self):
        """Test validation rejects invalid file extensions."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b'text content')
            tmp_path = tmp.name

        try:
            result = self.validator.validate_video_file(tmp_path)
            assert result["valid"] == False
            assert "Invalid file type" in result["error"]
        finally:
            os.unlink(tmp_path)

    def test_validate_video_file_too_large(self):
        """Test validation rejects files that are too large."""
        # Create a large temporary file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            # Write more than 1GB (but not really, just mock the size)
            tmp.write(b'x' * 1024)
            tmp_path = tmp.name

        try:
            # Mock os.path.getsize to return large size
            with patch('os.path.getsize', return_value=2 * 1024 * 1024 * 1024):  # 2GB
                result = self.validator.validate_video_file(tmp_path)
                assert result["valid"] == False
                assert "too large" in result["error"]
        finally:
            os.unlink(tmp_path)

    def test_validate_contestant_name_valid(self):
        """Test validation of valid contestant names."""
        result = self.validator.validate_contestant_name("张三")
        assert result["valid"] == True
        assert result["sanitized"] == "张三"

        result = self.validator.validate_contestant_name("John Doe")
        assert result["valid"] == True
        assert result["sanitized"] == "John Doe"

    def test_validate_contestant_name_invalid(self):
        """Test validation rejects invalid contestant names."""
        result = self.validator.validate_contestant_name("")
        assert result["valid"] == False
        assert "cannot be empty" in result["error"]

        result = self.validator.validate_contestant_name("A" * 60)  # Too long
        assert result["valid"] == False
        assert "too long" in result["error"]

        result = self.validator.validate_contestant_name("John@Doe")  # Invalid chars
        assert result["valid"] == False
        assert "invalid characters" in result["error"]

    def test_validate_api_input_safe(self):
        """Test API input validation with safe data."""
        data = {"name": "John", "age": 25}
        result = self.validator.validate_api_input(data)
        assert result["valid"] == True
        assert result["sanitized"] == data

    def test_validate_api_input_dangerous_keys(self):
        """Test API input validation blocks dangerous keys."""
        data = {"name": "John", "__class__": "malicious"}
        result = self.validator.validate_api_input(data)
        assert result["valid"] == False
        assert "Dangerous key detected" in result["error"]

    def test_validate_api_input_sanitization(self):
        """Test API input sanitization."""
        data = {"comment": "<script>alert('xss')</script>"}
        result = self.validator.validate_api_input(data)
        assert result["valid"] == True
        assert result["sanitized"]["comment"] == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

    def test_sanitize_sql_input(self):
        """Test SQL input sanitization."""
        result = self.validator.sanitize_sql_input("user' OR '1'='1")
        assert "'" in result  # Should be escaped
        assert ";" not in result  # Dangerous chars removed