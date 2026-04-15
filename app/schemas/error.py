"""Shared API error schema."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """A structured model for error details in API responses.

    This model standardizes the format of error responses,
    making it easier for clients to parse and handle errors consistently.

    Attributes
    ----------
    code : str
        Machine-readable error code for client-side branching.
    message : str
        Human-readable summary of the error.
    details : dict
        Optional structured metadata; includes ``hint`` when available.
    """

    code: str = "UNKNOWN_ERROR"
    message: str = "An unknown error occurred."
    details: dict = Field(
        default_factory=dict,
        description="Structured details about the error, always containing a `hint` field (may be None).",
        examples=[{"hint": "The 'amount' field must be a positive number."}],
    )
