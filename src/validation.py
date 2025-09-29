"""
Input validation utilities for face recognition system.
Provides secure validation of file uploads, API inputs, and user data.
"""

import os
import re
from typing import Optional, Dict, Any
from pathlib import Path

class InputValidator:
    """Comprehensive input validation for the face recognition system."""

    # Valid video file extensions
    VALID_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'}

    # Maximum file size (1GB)
    MAX_FILE_SIZE_MB = 1000

    # Contestant name validation pattern (Chinese and English names)
    NAME_PATTERN = re.compile(r'^[a-zA-Z\u4e00-\u9fff\s]{1,50}$')

    def validate_video_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate video file for upload and processing.

        Args:
            file_path: Path to the video file

        Returns:
            Dict with validation result and error message if invalid
        """
        result = {"valid": True, "error": None}

        # Check if file exists
        if not os.path.exists(file_path):
            result["valid"] = False
            result["error"] = "File does not exist"
            return result

        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.VALID_VIDEO_EXTENSIONS:
            result["valid"] = False
            result["error"] = f"Invalid file type. Supported: {', '.join(self.VALID_VIDEO_EXTENSIONS)}"
            return result

        # Check file size
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                result["valid"] = False
                result["error"] = f"File too large. Maximum size: {self.MAX_FILE_SIZE_MB}MB"
                return result
        except OSError:
            result["valid"] = False
            result["error"] = "Cannot read file size"
            return result

        # Check if file is readable
        try:
            with open(file_path, 'rb') as f:
                f.read(1024)  # Read first 1KB
        except (IOError, OSError):
            result["valid"] = False
            result["error"] = "File is not readable"
            return result

        return result

    def validate_contestant_name(self, name: str) -> Dict[str, Any]:
        """
        Validate contestant name for security and format.

        Args:
            name: Contestant name to validate

        Returns:
            Dict with validation result and sanitized name
        """
        result = {"valid": True, "error": None, "sanitized": name}

        if not name or not isinstance(name, str):
            result["valid"] = False
            result["error"] = "Name must be a non-empty string"
            return result

        # Check length
        if len(name.strip()) == 0:
            result["valid"] = False
            result["error"] = "Name cannot be empty"
            return result

        if len(name) > 50:
            result["valid"] = False
            result["error"] = "Name too long (max 50 characters)"
            return result

        # Validate pattern
        if not self.NAME_PATTERN.match(name):
            result["valid"] = False
            result["error"] = "Name contains invalid characters"
            return result

        # Sanitize
        result["sanitized"] = name.strip()

        return result

    def validate_api_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate API input data for security.

        Args:
            data: Input data dictionary

        Returns:
            Dict with validation result and sanitized data
        """
        result = {"valid": True, "error": None, "sanitized": data.copy()}

        # Check for dangerous keys
        dangerous_keys = ['__class__', '__globals__', '__import__', 'eval', 'exec']
        for key in data.keys():
            if any(dangerous in str(key).lower() for dangerous in dangerous_keys):
                result["valid"] = False
                result["error"] = f"Dangerous key detected: {key}"
                return result

        # Sanitize string values
        for key, value in data.items():
            if isinstance(value, str):
                # Basic XSS prevention
                sanitized = value.replace('<', '&lt;').replace('>', '&gt;')
                sanitized = sanitized.replace('"', '&quot;').replace("'", '&#x27;')
                result["sanitized"][key] = sanitized

        return result

    def sanitize_sql_input(self, input_str: str) -> str:
        """
        Sanitize input for SQL queries (basic protection).

        Args:
            input_str: Input string to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(input_str, str):
            return str(input_str)

        # Remove or escape dangerous characters
        sanitized = input_str.replace("'", "''")  # SQL escape
        sanitized = re.sub(r'[;\-\-]', '', sanitized)  # Remove semicolons and comments

        return sanitized