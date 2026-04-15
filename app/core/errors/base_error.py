"""Base error types and shared error-code enum.

All application-specific exceptions inherit from ``AppError`` and are translated to
HTTP responses by the global FastAPI exception handler.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Machine-readable error categories returned by API responses."""

    # Auth / access
    INVALID_TOKEN = "INVALID_TOKEN"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Infrastructure
    DATABASE_INTERNAL_ERROR = "DATABASE_INTERNAL_ERROR"

    # Domain / data / ML
    DATA_VALIDATION_FAILED = "DATA_VALIDATION_FAILED"
    DATA_PROCESSING_FAILED = "DATA_PROCESSING_FAILED"
    INVALID_INPUT = "INVALID_INPUT"


class AppError(Exception):
    """Base exception type mapped to HTTP responses by global error handler."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict | None = None,
    ):
        """Base exception for the application.

        Parameters
        ----------
        status_code : int
            HTTP status code to be returned in the response.
        code : ErrorCode
            A specific error code from the ErrorCode enum to categorize the error.
        message : str
            A human-readable message describing the error.
        details : dict, optional
            Additional details about the error.
            Each details dict will have at least 'hint' field, even if not provided
        """
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = {"hint": ""}
        if details:
            self.details.update(details)
        super().__init__(message)
