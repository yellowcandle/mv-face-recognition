"""
Structured Logger for MV Face Recognition

Provides consistent, structured logging across the video processing pipeline.
Supports JSON output for production and human-readable output for development.

Usage:
    from src.utils.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing started", video_id="123", frames=1000)
    logger.error("Failed to process", error=str(e), video_id="123")
"""

import logging
import json
import os
import sys
from datetime import datetime
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs in production
    and human-readable logs in development.
    """
    
    def __init__(self, json_output: bool = False):
        super().__init__()
        self.json_output = json_output
    
    def format(self, record: logging.LogRecord) -> str:
        # Extract extra fields from record
        extra = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'taskName', 'message'
            }:
                extra[key] = value
        
        # Format the message
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        
        if self.json_output:
            # JSON format for production
            log_data = {
                "timestamp": timestamp,
                "level": record.levelname,
                "logger": record.name,
                "message": message,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            if extra:
                log_data["metadata"] = extra
            
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
            
            return json.dumps(log_data)
        else:
            # Human-readable format for development
            extra_str = ""
            if extra:
                extra_parts = [f"{k}={v}" for k, v in extra.items()]
                extra_str = " | " + ", ".join(extra_parts)
            
            base = f"[{timestamp}] [{record.levelname}] {record.name}: {message}{extra_str}"
            
            if record.exc_info:
                base += "\n" + self.formatException(record.exc_info)
            
            return base


class StructuredLogger(logging.Logger):
    """
    Extended logger that supports structured metadata in log calls.
    """
    
    def _log_with_metadata(
        self,
        level: int,
        msg: str,
        args: tuple = (),
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 2,
        **kwargs
    ):
        """Log with additional structured metadata."""
        extra = kwargs if kwargs else {}
        super()._log(
            level, msg, args,
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info,
            stacklevel=stacklevel
        )
    
    def debug(self, msg: str, *args, **kwargs):
        """Debug log with optional metadata."""
        if self.isEnabledFor(logging.DEBUG):
            self._log_with_metadata(logging.DEBUG, msg, args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Info log with optional metadata."""
        if self.isEnabledFor(logging.INFO):
            self._log_with_metadata(logging.INFO, msg, args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Warning log with optional metadata."""
        if self.isEnabledFor(logging.WARNING):
            self._log_with_metadata(logging.WARNING, msg, args, **kwargs)
    
    def error(self, msg: str, *args, exc_info: bool = False, **kwargs):
        """Error log with optional metadata and exception info."""
        if self.isEnabledFor(logging.ERROR):
            self._log_with_metadata(logging.ERROR, msg, args, exc_info=exc_info, **kwargs)
    
    def critical(self, msg: str, *args, exc_info: bool = True, **kwargs):
        """Critical log with optional metadata (includes exception by default)."""
        if self.isEnabledFor(logging.CRITICAL):
            self._log_with_metadata(logging.CRITICAL, msg, args, exc_info=exc_info, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        """Exception log - always includes exception info."""
        self.error(msg, *args, exc_info=True, **kwargs)


# Register our custom logger class
logging.setLoggerClass(StructuredLogger)


def get_logger(
    name: str,
    level: Optional[str] = None,
    json_output: Optional[bool] = None
) -> StructuredLogger:
    """
    Get or create a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to LOG_LEVEL env var or INFO
        json_output: Whether to output JSON format
                    Defaults to JSON_LOGS env var or False
    
    Returns:
        StructuredLogger instance
    
    Example:
        logger = get_logger(__name__)
        logger.info("Processing video", video_id="123", frames=1000)
    """
    # Determine log level
    if level is None:
        level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    log_level = getattr(logging, level, logging.INFO)
    
    # Determine output format
    if json_output is None:
        json_output = os.environ.get('JSON_LOGS', '').lower() in ('true', '1', 'yes')
    
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(log_level)
        
        # Create handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(log_level)
        
        # Set formatter
        formatter = StructuredFormatter(json_output=json_output)
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger


def configure_root_logger(
    level: str = 'INFO',
    json_output: bool = False
):
    """
    Configure the root logger for the application.
    Call this once at application startup.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to output JSON format
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # Add new handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler.setFormatter(StructuredFormatter(json_output=json_output))
    root.addHandler(handler)


# Convenience shortcuts for module-level logging
_default_logger: Optional[StructuredLogger] = None


def _get_default_logger() -> StructuredLogger:
    """Get or create the default logger."""
    global _default_logger
    if _default_logger is None:
        _default_logger = get_logger('mvp-processor')
    return _default_logger


def debug(msg: str, **kwargs):
    """Module-level debug log."""
    _get_default_logger().debug(msg, **kwargs)


def info(msg: str, **kwargs):
    """Module-level info log."""
    _get_default_logger().info(msg, **kwargs)


def warning(msg: str, **kwargs):
    """Module-level warning log."""
    _get_default_logger().warning(msg, **kwargs)


def error(msg: str, exc_info: bool = False, **kwargs):
    """Module-level error log."""
    _get_default_logger().error(msg, exc_info=exc_info, **kwargs)


def critical(msg: str, exc_info: bool = True, **kwargs):
    """Module-level critical log."""
    _get_default_logger().critical(msg, exc_info=exc_info, **kwargs)


def exception(msg: str, **kwargs):
    """Module-level exception log."""
    _get_default_logger().exception(msg, **kwargs)
