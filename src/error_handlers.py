"""
Secure error handling for face recognition system.
Provides safe error responses without exposing sensitive information.
"""

import logging
import traceback
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SecureErrorHandler:
    """
    Handles errors securely, logging details internally while
    returning safe responses to clients.
    """

    def __init__(self, log_sensitive_data: bool = False):
        """
        Initialize error handler.

        Args:
            log_sensitive_data: Whether to log potentially sensitive data (False for production)
        """
        self.log_sensitive_data = log_sensitive_data

    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle an exception and return a safe error response.

        Args:
            error: The exception that occurred
            context: Additional context information (will be sanitized)

        Returns:
            Safe error response dictionary
        """
        # Log the full error internally
        self._log_error(error, context)

        # Return safe response
        return self._create_safe_response(error)

    def _log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log error details internally for debugging.
        """
        try:
            error_msg = str(error)
            error_type = type(error).__name__

            # Determine severity
            severity = self._determine_severity(error)

            # Sanitize context for logging
            safe_context = self._sanitize_context(context) if context else {}

            # Log with appropriate level
            log_msg = f"Error: {error_type}: {error_msg}"
            if safe_context:
                log_msg += f" | Context: {safe_context}"

            if severity == ErrorSeverity.CRITICAL:
                logger.critical(log_msg)
                # Log full traceback for critical errors
                logger.critical("Full traceback:", exc_info=True)
            elif severity == ErrorSeverity.HIGH:
                logger.error(log_msg)
                logger.error("Traceback:", exc_info=True)
            elif severity == ErrorSeverity.MEDIUM:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

        except Exception as log_error:
            # If logging fails, log the logging failure (safely)
            logger.error(f"Failed to log error: {type(log_error).__name__}")

    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """
        Determine error severity based on exception type and content.
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Critical errors
        if any(keyword in error_msg for keyword in ['security', 'breach', 'exploit', 'injection']):
            return ErrorSeverity.CRITICAL

        if isinstance(error, (SystemExit, KeyboardInterrupt)):
            return ErrorSeverity.CRITICAL

        # High severity
        if any(keyword in error_msg for keyword in ['database', 'connection', 'timeout', 'unauthorized']):
            return ErrorSeverity.HIGH

        if isinstance(error, (PermissionError, ConnectionError)):
            return ErrorSeverity.HIGH

        # Medium severity
        if isinstance(error, (ValueError, TypeError, KeyError)):
            return ErrorSeverity.MEDIUM

        # Low severity (default)
        return ErrorSeverity.LOW

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize context data for safe logging.
        """
        if not context:
            return {}

        sanitized = {}
        sensitive_keys = {'password', 'token', 'key', 'secret', 'embedding', 'biometric'}

        for key, value in context.items():
            key_lower = str(key).lower()

            # Skip sensitive keys entirely
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
                continue

            # Sanitize values
            if isinstance(value, str):
                # Truncate long strings
                if len(value) > 100:
                    sanitized[key] = value[:100] + "..."
                else:
                    sanitized[key] = value
            elif isinstance(value, (list, dict)):
                # Convert to type info
                sanitized[key] = f"{type(value).__name__} with {len(value)} items"
            else:
                sanitized[key] = str(type(value).__name__)

        return sanitized

    def _create_safe_response(self, error: Exception) -> Dict[str, Any]:
        """
        Create a safe error response for client.
        """
        error_type = type(error).__name__

        # Map error types to safe messages
        safe_messages = {
            'ValueError': 'Invalid input provided',
            'KeyError': 'Required data missing',
            'TypeError': 'Invalid data type',
            'PermissionError': 'Access denied',
            'FileNotFoundError': 'Resource not found',
            'ConnectionError': 'Service temporarily unavailable',
            'TimeoutError': 'Request timed out',
        }

        # Default safe message
        message = safe_messages.get(error_type, 'An error occurred')

        return {
            'error': message,
            'code': 500,
            'type': 'server_error'
        }

def create_error_response(message: str, code: int = 500, error_type: str = 'server_error') -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        message: Safe error message
        code: HTTP status code
        error_type: Error type identifier

    Returns:
        Error response dictionary
    """
    return {
        'error': message,
        'code': code,
        'type': error_type
    }

def log_security_event(event_type: str, details: Dict[str, Any], severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> None:
    """
    Log security-related events.

    Args:
        event_type: Type of security event
        details: Event details (will be sanitized)
        severity: Event severity
    """
    handler = SecureErrorHandler()
    sanitized_details = handler._sanitize_context(details)

    log_msg = f"Security Event: {event_type} | Details: {sanitized_details}"

    if severity == ErrorSeverity.CRITICAL:
        logger.critical(log_msg)
    elif severity == ErrorSeverity.HIGH:
        logger.error(log_msg)
    elif severity == ErrorSeverity.MEDIUM:
        logger.warning(log_msg)
    else:
        logger.info(log_msg)