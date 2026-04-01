from typing import Dict

from pydantic import BaseModel, Field


class CSVImportRequest(BaseModel):
    """Metadata accompanying a CSV file upload request.

    The file itself is provided as multipart form data (`UploadFile`).
    This model documents the expected content type constraint for client validation.

    ## Attributes
    - **content_type** (str): Must be `text/csv` or `application/csv`.
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

    ## Attributes
    - **filename** (str): The name of the output file (prefixed with `processed_`).
    - **row_count** (int): Number of data rows in the processed file.
    - **columns** (list[str]): Column names present in the processed file.
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


class FileTypeAppendRequest(BaseModel):
    """Request model for registering a new file type in the database.

    This model captures the necessary information about the file schema and
    formatting details required to process files of this new type.

    ## Attributes
    - **cols** (list[str]): Column names of the file, used to generate a unique file type ID.
    - **file_name** (str): A human-readable name for the file type (e.g., "Nordea CSV").
    - **date_col** (str): The name of the date column in the file.
    - **date_col_format** (str): The date format used in the date column (e.g., "%Y-%m-%d").
    - **amount_col** (str): The name of the amount column in the file.
    - **receiver_col** (str): The name of the receiver/payee column in the file.
    """

    cols: list[str] = Field(
        ...,
        description="Column names of the file, used to generate a unique file type ID.",
        examples=[["Date", "Amount", "Receiver"]],
    )
    file_name: str = Field(
        ...,
        description="A human-readable name for the file type (e.g., 'Nordea CSV').",
        examples=["Nordea CSV"],
    )
    date_col: str = Field(
        ...,
        description="The name of the date column in the file.",
        examples=["Date"],
    )
    date_col_format: str = Field(
        ...,
        description="The date format used in the date column (e.g., '%Y-%m-%d').",
        examples=["%Y-%m-%d"],
    )
    amount_col: str = Field(
        ...,
        description="The name of the amount column in the file.",
        examples=["Amount"],
    )
    receiver_col: str = Field(
        ...,
        description="The name of the receiver/payee column in the file.",
        examples=["Receiver"],
    )


class TransactionLabelResponse(BaseModel):
    """Response model for transaction labeling results.

    This model captures the essential information about a transaction and its
    assigned category label after processing.

    ## Attributes
    - **labels** (Dict[str, str]): A mapping of transaction labels (keys) to their descriptions (values).
    """

    labels: Dict[str, str] = Field(
        ...,
        description="A mapping of transaction labels (keys) to their descriptions (values).",
        examples=[
            {"Groceries": "All food stuff", "Utilities": "Monthly utility bills"}
        ],
    )


class FileTypeDeleteRequest(BaseModel):
    """Request model for deleting an existing file type from the database.

    This model captures the unique identifier of the file type to be deleted.

    ## Attributes
    - **file_name** (str): The human-readable name of the file type to delete (e.g., "Nordea CSV").
    """

    file_name: str = Field(
        ...,
        description="The human-readable name of the file type to delete (e.g., 'Nordea CSV').",
        examples=["Nordea CSV"],
    )
