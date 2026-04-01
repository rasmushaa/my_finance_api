from pydantic import BaseModel, ConfigDict


class ErrorDetails(BaseModel):
    """Structured details included in an error response.

    Always contains a `hint` field, but may also include any number of
    additional fields depending on the error type.

    ## Attributes
    - **hint** (Optional[str]): An optional hint to help resolve the error. Always present, but may be None if not provided.
    - **...**: Additional error-specific fields may be present depending on the error type.
    """

    model_config = ConfigDict(extra="allow")

    hint: str = ""


class ErrorResponse(BaseModel):
    """A structured model for error details in API responses.

    This model standardizes the format of error responses,
    making it easier for clients to parse and handle errors consistently.

    ## Attributes
    - **code** (str): A machine-readable error code that can be used for programmatic error handling by clients.
    - **message** (str): A human-readable error message describing the issue.
    - **details** (ErrorDetails): Structured details about the error, always containing a `hint` field (may be None).
    """

    code: str = "UNKNOWN_ERROR"
    message: str = "An unknown error occurred."
    details: ErrorDetails = ErrorDetails()
