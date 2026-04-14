"""File-type registry API schemas."""

from typing import Dict

from pydantic import BaseModel, Field


class FileTypeAppendRequest(BaseModel):
    """Request model for registering a new file type in the database.

    This model captures the necessary information about the file schema and
    formatting details required to process files of this new type.

    Attributes
    ----------
    cols : list[str]
        Ordered source column names used to generate a deterministic schema ID.
    file_name : str
        Human-readable label for this file type.
    date_col : str
        Source column containing transaction date values.
    date_col_format : str
        Python datetime format string used to parse ``date_col``.
    amount_col : str
        Source column containing transaction amount values.
    receiver_col : str
        Source column containing counterparty/receiver values.
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


class FileTypeDeleteRequest(BaseModel):
    """Request model for deleting an existing file type from the database.

    This model captures the unique identifier of the file type to be deleted.

    Attributes
    ----------
    file_name : str
        Human-readable file-type name to soft-delete from registry.
    """

    file_name: str = Field(
        ...,
        description="The human-readable name of the file type to delete (e.g., 'Nordea CSV').",
        examples=["Nordea CSV"],
    )


class FileTypeListResponse(BaseModel):
    """Response model for listing supported file types.

    This model captures the essential information about each registered file type
    that clients can expect when requesting the list of supported file types.

    Attributes
    ----------
    filetypes : list[Dict[str, str]]
        File-type rows returned from the registry table.
    """

    filetypes: list[Dict[str, str]] = Field(
        ...,
        description="A list of dictionaries, each containing details about a supported file type.",
        examples=[
            {
                "file_id": "Date-Amount-Receiver",
                "file_name": "Nordea CSV",
                "date_column": "Date",
                "date_column_format": "%Y-%m-%d",
                "amount_column": "Amount",
                "receiver_column": "Receiver",
                "row_created_at": "2024-01-01T12:00:00Z",
            }
        ],
    )
