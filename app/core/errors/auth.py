"""Authentication and authorization error types."""

from .base_error import AppError, ErrorCode


# -- Auth chain -------------------------------------------
class MissingBearerTokenError(AppError):
    """Raised when Authorization header is missing."""

    def __init__(self):
        super().__init__(
            status_code=401,
            code=ErrorCode.INVALID_TOKEN,
            message="Missing authorization header",
            details={
                "hint": "The request is missing the Authorization header with a Bearer token. Please include a valid JWT token in the Authorization header."
            },
        )


class CodeExchangeError(AppError):
    """Raised when Google OAuth authorization code exchange fails."""

    def __init__(self):
        super().__init__(
            status_code=401,
            code=ErrorCode.INVALID_TOKEN,
            message="Google code exchange failed",
        )


class MissingIdTokenError(AppError):
    """Raised when Google token exchange payload has no ID token."""

    def __init__(self):
        super().__init__(
            status_code=401,
            code=ErrorCode.INVALID_TOKEN,
            message="Google token exchange response missing id token",
        )


class InvalidIdTokenError(AppError):
    """Raised when Google ID token is invalid."""

    def __init__(self):
        super().__init__(
            status_code=401,
            code=ErrorCode.INVALID_TOKEN,
            message="Invalid Google ID token",
        )


class MissingEmailError(AppError):
    """Raised when verified Google ID token does not include an email."""

    def __init__(self):
        super().__init__(
            status_code=401,
            code=ErrorCode.INVALID_TOKEN,
            message="Google ID token missing email",
        )


class UserNotFoundError(AppError):
    """Raised when authenticated Google user is not provisioned in credentials table."""

    def __init__(self):
        super().__init__(
            status_code=404,
            code=ErrorCode.UNAUTHORIZED,
            message="User not found",
            details={
                "hint": "The user associated with Google account has not registered in the system. Please sign up first to create an account."
            },
        )


class UserNotAuthorizedError(AppError):
    """Raised when authenticated user role does not satisfy endpoint requirements."""

    def __init__(self):
        super().__init__(
            status_code=403,
            code=ErrorCode.FORBIDDEN,
            message="User does not have required permissions",
            details={
                "hint": "The user is authenticated but does not have access to this resource. You can request access from the administrator if you believe this is an error."
            },
        )


# -- Active in usage errors -------------------------------------------
class ExpiredIdTokenError(AppError):
    """Raised when JWT token has expired."""

    def __init__(self):
        super().__init__(
            status_code=401,
            code=ErrorCode.EXPIRED_TOKEN,
            message="Expired JWT ID token",
            details={
                "hint": "The token has expired. Please log in again to obtain a new token."
            },
        )


class AuthRateLimitExceededError(AppError):
    """Raised when user exceeds authentication rate-limit window."""

    def __init__(self, email: str, cooldown_seconds: int, details: dict | None = None):
        super().__init__(
            status_code=429,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Too many authentication attempts for {email}. Please wait {cooldown_seconds} seconds.",
            details={
                "hint": "You have spammed too many API calls, go to have a coffee break",
                "email": email,
                "cooldown_seconds": cooldown_seconds,
            },
        )
