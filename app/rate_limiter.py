import logging
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import schemas

logger = logging.getLogger(__name__)

# 1. Open endpoints (anyone can access - prevent spam!)
UNAUTH_LIMITS = ["5/minute"]  # Health checks, Auth - open to public but limited

# 2. Authenticated endpoints (users with valid JWT - be generous!)
ML_PREDICT_LIMITS = [
    "100/minute",
    "2000/hour",
]  # ML predictions - expensive but authenticated users
DATA_LIMITS = ["200/minute", "5000/hour"]  # Data endpoints - authenticated users

# Rate limiter configuration
RATE_LIMITER_STORAGE = os.getenv(
    "RATE_LIMITER_STORAGE", "memory://"
)  # In production, consider using Redis for distributed rate limiting


def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded exceptions.

    This function logs the rate limit violation and raises a structured HTTP exception
    with a consistent error response format defined by our ErrorDetail model.
    """

    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)}: " f"{exc.detail}"
    )

    raise schemas.CustomHTTPException(
        status_code=429,
        error_code=schemas.ErrorCode.RATE_LIMIT_EXCEEDED,
        message="Rate limit exceeded. Please try again later.",
        details={"retry_after": getattr(exc, "retry_after", None), "limit": exc.detail},
    )


def get_rate_limit_key(request: Request) -> str:
    """Get the key for rate limiting - just use client IP.

    Keep it simple - rate limiting is primarily for open endpoints
    to prevent spam. Authenticated endpoints get generous or no limits.
    """

    return get_remote_address(request)


limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=RATE_LIMITER_STORAGE,
    default_limits=[
        "5/minute"
    ],  # Strict default limit for any endpoint that doesn't specify its own limits
)
