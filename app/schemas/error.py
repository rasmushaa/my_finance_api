from typing import Any, Dict

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """A structured model for error details in API responses.

    This model standardizes the format of error responses,
    making it easier for clients to parse and handle errors consistently.

    Attributes
    ----------
    code : str
        A machine-readable error code that can be used for programmatic error handling by clients.
    message : str
        A human-readable error message describing the issue.
    details : Optional[Dict[str, Any]]
        Additional details about the error (e.g., validation errors, stack trace) that can be included in the response for debugging purposes.
    """

    code: str = "UNKNOWN_ERROR"
    message: str = "An unknown error occurred."
    details: Dict[str, Any]
