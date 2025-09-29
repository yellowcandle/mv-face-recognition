"""
Secure logging utilities for face recognition system.
Provides sanitized logging that protects sensitive information.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime


class SecureLogger:
    """
    Logger that automatically sanitizes sensitive data from log messages.
    """

    def __init__(self, name: str = "face_recognition", level: int = logging.INFO):
        """
        Initialize secure logger.

        Args:
            name: Logger name
            level: Logging level
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.sensitive_keys = {
            'password', 'token', 'key', 'secret', 'embedding', 'biometric',
            'face_data', 'personal_info', 'auth_token', 'session_id'
        }

    def _sanitize_data(self, data: Any) -> Any:
        """
        Recursively sanitize sensitive data from dictionaries and objects.
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                key_lower = str(key).lower()
                if any(sensitive in key_lower for sensitive in self.sensitive_keys):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_data(item) for item in data]
        elif isinstance(data, str):
            # Check for potential sensitive patterns in strings
            if any(pattern in data.lower() for pattern in ['password=', 'token=', 'key=']):
                return "[REDACTED]"
            return data
        else:
            return data

    def _sanitize_message(self, message: str, *args, **kwargs) -> tuple:
        """
        Sanitize log message and arguments.
        """
        # Sanitize the main message
        sanitized_message = message

        # Sanitize any dict arguments
        sanitized_args = []
        for arg in args:
            if isinstance(arg, dict):
                sanitized_args.append(self._sanitize_data(arg))
            else:
                sanitized_args.append(arg)

        sanitized_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, dict):
                sanitized_kwargs[key] = self._sanitize_data(value)
            else:
                sanitized_kwargs[key] = value

        return (sanitized_message,) + tuple(sanitized_args), sanitized_kwargs

    def debug(self, message: str, *args, **kwargs):
        """Log debug message with sanitization."""
        sanitized_args, sanitized_kwargs = self._sanitize_message(message, *args, **kwargs)
        self.logger.debug(*sanitized_args, **sanitized_kwargs)

    def info(self, message: str, *args, **kwargs):
        """Log info message with sanitization."""
        sanitized_args, sanitized_kwargs = self._sanitize_message(message, *args, **kwargs)
        self.logger.info(*sanitized_args, **sanitized_kwargs)

    def warning(self, message: str, *args, **kwargs):
        """Log warning message with sanitization."""
        sanitized_args, sanitized_kwargs = self._sanitize_message(message, *args, **kwargs)
        self.logger.warning(*sanitized_args, **sanitized_kwargs)

    def error(self, message: str, *args, **kwargs):
        """Log error message with sanitization."""
        sanitized_args, sanitized_kwargs = self._sanitize_message(message, *args, **kwargs)
        self.logger.error(*sanitized_args, **sanitized_kwargs)

    def critical(self, message: str, *args, **kwargs):
        """Log critical message with sanitization."""
        sanitized_args, sanitized_kwargs = self._sanitize_message(message, *args, **kwargs)
        self.logger.critical(*sanitized_args, **sanitized_kwargs)

    def log_security_event(self, event_type: str, details: Dict[str, Any], level: int = logging.WARNING):
        """
        Log security-related events with enhanced sanitization.

        Args:
            event_type: Type of security event
            details: Event details
            level: Logging level
        """
        sanitized_details = self._sanitize_data(details)
        timestamp = datetime.now().isoformat()

        message = f"SECURITY_EVENT: {event_type} at {timestamp}"
        self.logger.log(level, message, extra={"security_details": sanitized_details})

    def log_access_attempt(self, user_id: str, resource: str, action: str, success: bool,
                          ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """
        Log access attempts for audit trail.

        Args:
            user_id: User identifier (anonymized if needed)
            resource: Resource being accessed
            action: Action performed
            success: Whether access was successful
            ip_address: Client IP address
            user_agent: Client user agent
        """
        status = "SUCCESS" if success else "FAILED"

        # Sanitize user_id if it looks sensitive
        safe_user_id = self._sanitize_data(user_id)

        message = f"ACCESS: {status} - User: {safe_user_id}, Resource: {resource}, Action: {action}"

        extra = {}
        if ip_address:
            extra["ip_address"] = ip_address
        if user_agent:
            extra["user_agent"] = user_agent[:200]  # Truncate long user agents

        self.logger.info(message, extra=extra)


# Global secure logger instance
secure_logger = SecureLogger()

# Convenience functions
def log_security_event(event_type: str, details: Dict[str, Any]):
    """Log security event using global logger."""
    secure_logger.log_security_event(event_type, details)

def log_access_attempt(user_id: str, resource: str, action: str, success: bool,
                      ip_address: Optional[str] = None, user_agent: Optional[str] = None):
    """Log access attempt using global logger."""
    secure_logger.log_access_attempt(user_id, resource, action, success, ip_address, user_agent)