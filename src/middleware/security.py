"""
Security middleware for face recognition system.
Provides security headers, CSRF protection, and other web security measures.
"""

import hashlib
import hmac
import time
from typing import Optional, Dict, Any


class SecurityHeadersMiddleware:
    """
    Middleware for adding security headers to HTTP responses.
    Implements OWASP security headers recommendations.
    """

    def __init__(self, csp_origins: Optional[list] = None):
        """
        Initialize security headers middleware.

        Args:
            csp_origins: List of allowed origins for Content Security Policy
        """
        self.csp_origins = csp_origins or ["'self'"]

    def get_security_headers(self) -> Dict[str, str]:
        """
        Get comprehensive security headers.

        Returns:
            Dictionary of security headers
        """
        headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",

            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",

            # Enable XSS protection
            "X-XSS-Protection": "1; mode=block",

            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Permissions policy (restrict features)
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",

            # HSTS (HTTP Strict Transport Security)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

            # Content Security Policy
            "Content-Security-Policy": self._build_csp(),
        }

        return headers

    def _build_csp(self) -> str:
        """
        Build Content Security Policy header.

        Returns:
            CSP header value
        """
        csp_parts = [
            "default-src 'self'",
            f"script-src {' '.join(self.csp_origins)} 'unsafe-inline' 'unsafe-eval'",  # Allow inline scripts for now
            f"style-src {' '.join(self.csp_origins)} 'unsafe-inline'",
            f"img-src {' '.join(self.csp_origins)} data: https:",
            f"font-src {' '.join(self.csp_origins)}",
            f"connect-src {' '.join(self.csp_origins)}",
            "object-src 'none'",  # Block plugins
            "base-uri 'self'",
            "form-action 'self'",
        ]

        return "; ".join(csp_parts)

    def apply_headers(self, response_headers: Dict[str, str]) -> Dict[str, str]:
        """
        Apply security headers to response headers.

        Args:
            response_headers: Existing response headers

        Returns:
            Updated headers with security headers
        """
        security_headers = self.get_security_headers()
        response_headers.update(security_headers)
        return response_headers


class CSRFProtection:
    """
    CSRF (Cross-Site Request Forgery) protection utilities.
    """

    def __init__(self, secret_key: str, token_lifetime: int = 3600):
        """
        Initialize CSRF protection.

        Args:
            secret_key: Secret key for token signing
            token_lifetime: Token lifetime in seconds
        """
        self.secret_key = secret_key
        self.token_lifetime = token_lifetime

    def generate_token(self, session_id: str) -> str:
        """
        Generate CSRF token for session.

        Args:
            session_id: User session identifier

        Returns:
            CSRF token
        """
        timestamp = str(int(time.time()))
        message = f"{session_id}:{timestamp}"

        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        token = f"{timestamp}:{signature}"
        return token

    def validate_token(self, token: str, session_id: str) -> bool:
        """
        Validate CSRF token.

        Args:
            token: CSRF token to validate
            session_id: User session identifier

        Returns:
            True if token is valid
        """
        try:
            timestamp_str, signature = token.split(":", 1)
            timestamp = int(timestamp_str)

            # Check if token has expired
            if int(time.time()) - timestamp > self.token_lifetime:
                return False

            # Verify signature
            message = f"{session_id}:{timestamp_str}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)

        except (ValueError, TypeError):
            return False


class InputSanitizer:
    """
    Input sanitization utilities for web requests.
    """

    @staticmethod
    def sanitize_html_input(input_str: str) -> str:
        """
        Sanitize HTML input to prevent XSS.

        Args:
            input_str: Input string to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(input_str, str):
            return str(input_str)

        # Basic HTML entity encoding
        sanitized = input_str.replace("&", "&amp;")
        sanitized = sanitized.replace("<", "&lt;")
        sanitized = sanitized.replace(">", "&gt;")
        sanitized = sanitized.replace('"', "&quot;")
        sanitized = sanitized.replace("'", "&#x27;")

        return sanitized

    @staticmethod
    def sanitize_sql_input(input_str: str) -> str:
        """
        DEPRECATED: Manual SQL sanitization is unsafe and should not be used.
        
        This method has been deprecated because manual SQL sanitization is 
        inherently insecure and prone to bypasses. Modern database libraries
        provide parameterized queries that are much safer.
        
        Args:
            input_str: Input string (not sanitized)
            
        Raises:
            NotImplementedError: Always raises to prevent unsafe usage
            
        Example of safe alternative:
            # WRONG (vulnerable to SQL injection):
            cursor.execute(f"SELECT * FROM table WHERE name = '{sanitize_sql_input(name)}'")
            
            # CORRECT (safe with parameterized queries):
            # For SQLite/PostgreSQL:
            cursor.execute("SELECT * FROM table WHERE name = ?", (name,))
            # For MySQL/PostgreSQL:
            cursor.execute("SELECT * FROM table WHERE name = %s", (name,))
        """
        raise NotImplementedError(
            "Manual SQL sanitization is unsafe and has been deprecated. "
            "Use parameterized queries instead: "
            "cursor.execute('SELECT * FROM table WHERE id = ?', (id,))"
        )

    @staticmethod
    def validate_file_upload(filename: str, allowed_extensions: list) -> bool:
        """
        Validate file upload filename.

        Args:
            filename: Uploaded filename
            allowed_extensions: List of allowed extensions

        Returns:
            True if filename is safe
        """
        if not filename or ".." in filename:
            return False

        # Check extension
        import os
        _, ext = os.path.splitext(filename)
        return ext.lower() in [e.lower() for e in allowed_extensions]


class SecurityMiddleware:
    """
    Combined security middleware that applies all security measures.
    """

    def __init__(self, secret_key: str, csp_origins: Optional[list] = None):
        """
        Initialize combined security middleware.

        Args:
            secret_key: Secret key for cryptographic operations
            csp_origins: Allowed CSP origins
        """
        self.headers_middleware = SecurityHeadersMiddleware(csp_origins)
        self.csrf_protection = CSRFProtection(secret_key)
        self.sanitizer = InputSanitizer()

    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming request for security.

        Args:
            request_data: Request data dictionary

        Returns:
            Processed request data
        """
        processed = request_data.copy()

        # Sanitize string inputs
        for key, value in processed.items():
            if isinstance(value, str):
                processed[key] = self.sanitizer.sanitize_html_input(value)

        return processed

    def process_response(self, response_data: Dict[str, Any],
                        response_headers: Dict[str, str]) -> Dict[str, str]:
        """
        Process outgoing response for security.

        Args:
            response_data: Response data
            response_headers: Response headers

        Returns:
            Updated response headers
        """
        return self.headers_middleware.apply_headers(response_headers)

    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token."""
        return self.csrf_protection.generate_token(session_id)

    def validate_csrf_token(self, token: str, session_id: str) -> bool:
        """Validate CSRF token."""
        return self.csrf_protection.validate_token(token, session_id)