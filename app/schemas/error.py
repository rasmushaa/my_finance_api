from pydantic import BaseModel
from fastapi import HTTPException
from typing import Any, Optional
from enum import Enum


class ErrorCode(Enum):
    """ Standardized error codes for API responses 
    to facilitate consistent error handling by clients.
    """
    MODEL_NOT_READY = "MODEL_NOT_READY"
    MODEL_FEATURES = "MODEL_FEATURES"
    INVALID_INPUT = "INVALID_INPUT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"


class ErrorDetail(BaseModel):
    """A structured model for error details in API responses.
    
    This model standardizes the format of error responses, 
    making it easier for clients to parse and handle errors consistently.

    Attributes
    ----------
    code : str
        A machine-readable error code that can be used for programmatic error handling by clients.
    message : str
        A human-readable error message describing the issue.
    detail : Optional[Any]
        Additional details about the error (e.g., validation errors, stack trace) that can be included in the response for debugging purposes.
    """
    code: str = "UNKNOWN_ERROR"
    message: str = "An unknown error occurred." 
    detail: Optional[Any] = None


class ErrorResponse(BaseModel):
    """A standardized error response model for API endpoints.
    
    This model aligns with FastAPI's error response structure, 
    allowing us to return consistent error responses across all endpoints.
    """
    detail: ErrorDetail


class CustomHTTPException(HTTPException):
    """Custom HTTPException that uses our structured error format.
    
    This class allows us to raise HTTP exceptions 
    with a consistent error response structure 
    defined by the ErrorDetail model.
    """
    
    def __init__(self, status_code: int, error_code: ErrorCode, message: str, details: Optional[Any] = None):
        error_detail = ErrorDetail(
            code=error_code.value,
            message=message,
            detail=details
        )
        super().__init__(status_code=status_code, detail=error_detail.model_dump())


