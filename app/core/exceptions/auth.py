from .base import AppError, ErrorCodes


class MissingBearerTokenError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=401,
            code=ErrorCodes.MISSING_BEARER_TOKEN.value,
            message="Missing authorization header",
            # No sensitive details to include in the error response
        )


class CodeExchangeError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=401,
            code=ErrorCodes.AUTH.value,
            message="Google code exchange failed",
            # Do not include sensitive details in the error respons
        )


class MissingIdTokenError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=401,
            code=ErrorCodes.AUTH.value,
            message="Google token exchange response missing id_token",
            # Do not include sensitive details in the error respons
        )


class InvalidIdTokenError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=401,
            code=ErrorCodes.AUTH.value,
            message="Invalid Google ID token",
            # Do not include sensitive details in the error respons
        )


class MissingEmailError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=401,
            code=ErrorCodes.AUTH.value,
            message="Google ID token missing email",
            # Do not include sensitive details in the error respons
        )


class UserNotFoundError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=404,
            code=ErrorCodes.AUTH.value,
            message="User email not found",
            # Do not include sensitive details in the error response
        )


class UserNotAuthorizedError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=403,
            code=ErrorCodes.FORBIDDEN.value,
            message="User does not have required permissions",
            # Do not include sensitive details in the error response
        )


class AuthRateLimitExceededError(AppError):
    def __init__(self, cooldown_seconds: int):
        super().__init__(
            status_code=429,
            code=ErrorCodes.RATE_LIMIT_EXCEEDED.value,
            message=f"Too many authentication attempts. Please wait {cooldown_seconds} seconds.",
            details={"cooldown_seconds": cooldown_seconds},
        )
