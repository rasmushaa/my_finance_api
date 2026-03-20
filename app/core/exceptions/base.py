"""This module defines custom base exceptions for the application, which is inherited by
more specific exceptions in different parts for services.

The base exceptions is FastAPI compatible, and raises are automatically handled by
custom exception handlers defined in ./handlers.py.
"""

from enum import Enum


class ErrorCodes(Enum):
    """Standardized error codes for API responses."""

    ML_ERROR = "ML_ERROR"
    AUTH = "AUTH_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DATABASE_INTERNAL_ERROR = "DATABASE_INTERNAL_ERROR"
    MISSING_BEARER_TOKEN = "MISSING_BEARER_TOKEN"


class AppError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict | None = None
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)
