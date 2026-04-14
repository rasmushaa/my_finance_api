"""Infrastructure-layer exception types."""

from .base_error import AppError, ErrorCode


class DatabaseInternalError(AppError):
    """Exception raised for internal database errors.

    This exception is used to indicate that an unexpected error occurred while
    interacting with the database, such as connection issues, query failures, or other
    internal problems that prevent the database from functioning properly.
    """

    def __init__(
        self, message: str = "An internal database error occurred.", details: dict = {}
    ):
        super().__init__(
            status_code=500,
            code=ErrorCode.DATABASE_INTERNAL_ERROR,
            message=message,
            details=details,
        )
