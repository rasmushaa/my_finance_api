from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions.base import AppError
from app.schemas.error import ErrorResponse


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handles AppError exceptions and returns a structured JSON response with error
    details.

    This function is registered as an exception handler for AppError in the FastAPI
    application, allowing it to catch any exceptions that inherit from AppError and
    return a consistent error response format.
    """

    error = ErrorResponse(
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error.model_dump(),
    )
