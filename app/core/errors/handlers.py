"""FastAPI exception handlers for custom application errors."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors.base_error import AppError
from app.core.security import extract_client_context
from app.schemas.error import ErrorResponse

logger = logging.getLogger(__name__)


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle ``AppError`` exceptions and return structured JSON response.

    Parameters
    ----------
    request : Request
        FastAPI request object used for extracting client context.
    exc : AppError
        Raised application exception.

    Returns
    -------
    JSONResponse
        Standardized error payload matching ``ErrorResponse`` schema.
    """

    logger.error(
        f"{exc.code}: {exc.message} - Details:{exc.details} - Context:{extract_client_context(request)}"
    )

    error = ErrorResponse(
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error.model_dump(),
    )
