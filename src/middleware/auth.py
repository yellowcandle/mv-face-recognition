"""
Authentication and authorization middleware for face recognition system.
Provides JWT-based authentication and role-based access control.
"""

import time
import jwt
import logging
from typing import Optional, Dict, Any, List
from functools import wraps
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# FastAPI security scheme
security = HTTPBearer()

class AuthMiddleware:
    """
    Handles authentication and authorization for the face recognition API.
    Supports JWT tokens and role-based permissions.
    """

    def __init__(self, secret_key: str, token_expiry_hours: int = 24):
        """
        Initialize auth middleware.

        Args:
            secret_key: Secret key for JWT signing
            token_expiry_hours: Token expiry time in hours
        """
        self.secret_key = secret_key
        self.token_expiry_hours = token_expiry_hours
        self.algorithm = "HS256"

    def generate_token(self, user_id: str, roles: Optional[List[str]] = None) -> str:
        """
        Generate JWT token for user.

        Args:
            user_id: Unique user identifier
            roles: List of user roles

        Returns:
            JWT token string
        """
        if roles is None:
            roles = ["user"]

        payload = {
            "user_id": user_id,
            "roles": roles,
            "iat": int(time.time()),
            "exp": int(time.time()) + (self.token_expiry_hours * 3600)
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None if invalid
        """
        try:
            # Remove Bearer prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check expiry
            if payload.get("exp", 0) < int(time.time()):
                logger.warning("Token expired")
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return None

    def require_auth(self, required_roles: Optional[List[str]] = None):
        """
        Decorator for requiring authentication and specific roles.

        Args:
            required_roles: List of required roles (if None, any authenticated user)

        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # In a real implementation, this would extract token from request headers
                # For now, this is a placeholder structure
                token = kwargs.get('token')  # Placeholder

                if not token:
                    raise PermissionError("Authentication required")

                payload = self.verify_token(token)
                if not payload:
                    raise PermissionError("Invalid or expired token")

                user_roles = payload.get("roles", [])
                if required_roles:
                    if not any(role in user_roles for role in required_roles):
                        raise PermissionError(f"Required roles: {required_roles}")

                # Add user info to kwargs
                kwargs['user_id'] = payload.get('user_id')
                kwargs['user_roles'] = user_roles

                return func(*args, **kwargs)
            return wrapper
        return decorator

    def has_permission(self, user_roles: List[str], required_permissions: List[str]) -> bool:
        """
        Check if user has required permissions based on roles.

        Args:
            user_roles: User's roles
            required_permissions: Required permissions

        Returns:
            True if user has permission
        """
        # Define role permissions (can be moved to config)
        role_permissions = {
            "admin": ["read", "write", "delete", "manage_users", "view_logs"],
            "moderator": ["read", "write", "view_logs"],
            "user": ["read", "write"],
            "viewer": ["read"]
        }

        user_permissions = set()
        for role in user_roles:
            user_permissions.update(role_permissions.get(role, []))

        return all(perm in user_permissions for perm in required_permissions)

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate API key for service-to-service authentication.

        Args:
            api_key: API key string

        Returns:
            Service info or None if invalid
        """
        # Placeholder for API key validation
        # In production, this would check against a database or config
        valid_keys = {
            "service_key_123": {"service": "face_processor", "permissions": ["read", "write"]},
            "admin_key_456": {"service": "admin", "permissions": ["read", "write", "delete"]}
        }

        return valid_keys.get(api_key)

    def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """
        FastAPI dependency for getting current authenticated user.

        Args:
            credentials: HTTP Bearer token credentials

        Returns:
            User information dictionary

        Raises:
            HTTPException: If authentication fails
        """
        token = credentials.credentials
        payload = self.verify_token(token)

        if not payload:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    def require_roles(self, required_roles: Optional[List[str]] = None):
        """
        FastAPI dependency for requiring specific roles.

        Args:
            required_roles: List of required roles

        Returns:
            Dependency function
        """
        def dependency(current_user: Dict[str, Any] = Depends(self.get_current_user)) -> Dict[str, Any]:
            user_roles = current_user.get("roles", [])

            if required_roles:
                if not any(role in user_roles for role in required_roles):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Insufficient permissions. Required roles: {required_roles}",
                    )

            return current_user

        return dependency

    def rate_limit_dependency(self, rate_limiter: 'RateLimiter'):
        """
        FastAPI dependency for rate limiting.

        Args:
            rate_limiter: RateLimiter instance

        Returns:
            Dependency function
        """
        def dependency(request: Request) -> None:
            # Use client IP as identifier (in production, use user ID)
            client_id = request.client.host if request.client else "unknown"

            if not rate_limiter.is_allowed(client_id):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                )

        return dependency

class RateLimiter:
    """
    Simple rate limiter for API protection.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # In production, use Redis or similar

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed for client.

        Args:
            client_id: Unique client identifier

        Returns:
            True if request is allowed
        """
        current_time = int(time.time())

        if client_id not in self.requests:
            self.requests[client_id] = []

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if current_time - req_time < self.window_seconds
        ]

        if len(self.requests[client_id]) >= self.max_requests:
            return False

        self.requests[client_id].append(current_time)
        return True