from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """A structured model for error details in API responses.

    This model standardizes the format of error responses,
    making it easier for clients to parse and handle errors consistently.

    ## Attributes
    - **code** (str): A machine-readable error code that can be used for programmatic error handling by clients.
    - **message** (str): A human-readable error message describing the issue.
    - **details** (dict): Structured details about the error, always containing a `hint` field (may be None).
    """

    code: str = "UNKNOWN_ERROR"
    message: str = "An unknown error occurred."
    details: dict = Field(
        default_factory=dict,
        description="Structured details about the error, always containing a `hint` field (may be None).",
        examples=[{"hint": "The 'amount' field must be a positive number."}],
    )
