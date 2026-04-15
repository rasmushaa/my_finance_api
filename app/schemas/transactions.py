"""Transaction-related API schemas."""

from pydantic import BaseModel, Field


class CSVImportRequest(BaseModel):
    """Metadata accompanying a CSV file upload request.

    The file itself is provided as multipart form data (`UploadFile`).
    This model documents the expected content type constraint for client validation.

    Attributes
    ----------
    content_type : str
        MIME type of the uploaded file. Must be ``"text/csv"`` or
        ``"application/csv"``.
    """

    content_type: str = Field(
        ...,
        description="MIME type of the uploaded file. Must be 'text/csv' or 'application/csv'.",
        examples=["text/csv"],
    )


class CSVImportResponse(BaseModel):
    """Metadata returned alongside the processed CSV file download.

    The actual CSV content is streamed as a binary attachment. This model
    describes what clients can expect in the response headers and the
    structure of the processed data.

    Attributes
    ----------
    filename : str
        Output filename of the processed CSV, prefixed with ``"processed_"``.
    row_count : int
        Number of data rows in the processed CSV.
    columns : list[str]
        Ordered list of output column names in the processed CSV payload.
    """

    filename: str = Field(
        ...,
        description="Output filename of the processed CSV, prefixed with 'processed_'.",
        examples=["processed_transactions.csv"],
    )
    row_count: int = Field(
        ...,
        description="Number of data rows in the processed CSV.",
        examples=[42],
    )
    columns: list[str] = Field(
        ...,
        description="Ordered list of column names in the processed CSV.",
        examples=[["date", "receiver", "amount", "category"]],
    )


class TransactionLabels(BaseModel):
    """Single transaction label entry used by label-listing responses.

    Attributes
    ----------
    key : str
        Canonical category key used by reporting and model outputs.
    description : str
        Human-readable explanation of what transactions belong to the category.
    """

    key: str = Field(
        ...,
        description="The assigned category label for the transaction.",
        examples=["Groceries", "Utilities", "Entertainment"],
    )
    description: str = Field(
        ...,
        description="A brief description of the assigned category label.",
        examples=[
            "All food-related expenses",
            "Monthly utility bills",
            "Leisure and entertainment expenses",
        ],
    )


class TransactionLabelResponse(BaseModel):
    """Response model for transaction label listing endpoint.

    Attributes
    ----------
    labels : list[TransactionLabels]
        List of available transaction labels with user-facing descriptions.
    """

    labels: list[TransactionLabels] = Field(
        ...,
        description="List of transaction labels with their descriptions.",
    )
