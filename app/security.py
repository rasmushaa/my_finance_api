"""Security middleware and utilities for the API."""

import logging
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware that adds security headers and validates requests."""

    def __init__(
        self,
        app,
        max_request_size: int = 1024 * 1024,  # 1MB default
        blocked_user_agents: Optional[list] = None,
        enable_security_headers: bool = True,
    ):
        """Initialize security middleware.

        Args:
            app: The FastAPI application
            max_request_size: Maximum request body size in bytes
            blocked_user_agents: List of user agent patterns to block
            enable_security_headers: Whether to add security headers
        """
        super().__init__(app)
        self.max_request_size = max_request_size
        self.blocked_user_agents = blocked_user_agents or [
            # Common bot/scraper patterns
            "curl/",
            "wget/",
            "python-requests/",
            "bot",
            "crawler",
            "spider",
            # Add more patterns as needed
        ]
        self.enable_security_headers = enable_security_headers

    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware."""
        start_time = time.time()

        # Log request for monitoring
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {client_ip} UA: {user_agent[:100]}"
        )

        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            logger.warning(
                f"Request too large from {client_ip}: {content_length} bytes"
            )
            return JSONResponse(
                status_code=413,
                content={
                    "detail": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": f"Request body too large. Maximum size: {self.max_request_size} bytes",
                    }
                },
            )

        # Check blocked user agents for non-authenticated endpoints
        if self._is_blocked_user_agent(user_agent) and not self._has_auth_header(
            request
        ):
            logger.warning(f"Blocked user agent from {client_ip}: {user_agent}")
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "code": "FORBIDDEN",
                        "message": "Access denied",
                    }
                },
            )

        # Process request
        response = await call_next(request)

        # Add security headers
        if self.enable_security_headers:
            self._add_security_headers(response)

        # Log response time
        process_time = time.time() - start_time
        logger.info(f"Response: {response.status_code} in {process_time:.3f}s")

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_blocked_user_agent(self, user_agent: str) -> bool:
        """Check if user agent should be blocked."""
        user_agent_lower = user_agent.lower()
        return any(
            pattern.lower() in user_agent_lower for pattern in self.blocked_user_agents
        )

    def _has_auth_header(self, request: Request) -> bool:
        """Check if request has authorization header."""
        return "authorization" in request.headers

    def _add_security_headers(self, response: Response):
        """Add security headers to response."""
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy (adjust as needed)
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        # Remove server identification
        response.headers.pop("server", None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed request/response logging."""

    async def dispatch(self, request: Request, call_next):
        """Log request details for security monitoring."""
        client_ip = request.client.host if request.client else "unknown"

        # Log suspicious patterns
        suspicious_patterns = [
            "admin",
            "login",
            "password",
            "token",
            "key",
            "secret",
            "../",
            "/..",
            "eval(",
            "script>",
            "SELECT",
            "DROP",
            "INSERT",
        ]

        path = str(request.url.path).lower()
        query = str(request.url.query).lower()

        if any(pattern.lower() in path + query for pattern in suspicious_patterns):
            logger.warning(
                f"Suspicious request from {client_ip}: "
                f"{request.method} {request.url}"
            )

        response = await call_next(request)

        # Log failed authentication attempts
        if response.status_code in [401, 403]:
            logger.warning(
                f"Authentication failure from {client_ip}: "
                f"{request.method} {request.url.path} -> {response.status_code}"
            )

        return response
