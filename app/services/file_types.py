"""Service for managing supported transaction file schemas."""

import logging
import re

import pandas as pd

from app.core.errors.domain import DatabaseQueryError, UnknownFileTypeError

logger = logging.getLogger(__name__)


class FileTypesService:
    """Manage file-type registry records used by transaction normalization.

    The registry maps arbitrary bank CSV schemas into canonical API column names.
    """

    def __init__(self, db_client):
        """Initialize the FileTypesService to add and read registered file types.

        Parameters
        ----------
        db_client :
            Database client used for CRUD operations on ``d_filetypes``.
        """
        self.db_client = db_client

    def add_filetype_to_database(
        self,
        cols: list[str],
        file_name: str,
        date_col: str,
        date_col_format: str,
        amount_col: str,
        receiver_col: str,
    ):
        """Register a new supported file-type mapping.

        Parameters
        ----------
        cols : list[str]
            Source file columns used to generate deterministic file schema ID.
        file_name : str
            Human-readable name for the file format.
        date_col : str
            Source date column name.
        date_col_format : str
            Datetime format used to parse values in ``date_col``.
        amount_col : str
            Source amount column name.
        receiver_col : str
            Source receiver/payee column name.
        """
        data_insert = {
            "FileID": self.generate_filetype_id(cols),
            "FileName": file_name,
            "DateColumn": date_col,
            "DateColumnFormat": date_col_format,
            "AmountColumn": amount_col,
            "ReceiverColumn": receiver_col,
        }
        df = pd.DataFrame([data_insert])
        self.db_client.append_pandas_to_table(df, "d_filetypes")

    def delete_filetype_from_database(self, filename: str):
        """Soft-delete a file type from registry by file name.

        Parameters
        ----------
        filename : str
            Human-readable file-type name to mark as deleted.
        """
        sql = f"""
        UPDATE `{self.db_client.dataset}.d_filetypes`
        SET _RowStatus = 'd', _RowUpdatedAt = CURRENT_TIMESTAMP()
        WHERE FileName = @filename AND _RowStatus != @deleted_status
        """  # nosec B608
        row_count = self.db_client.execute_sql(
            sql,
            params={"filename": filename, "deleted_status": "d"},
        )
        if row_count == 0 or row_count is None:
            raise DatabaseQueryError(
                message=f"File type with name '{filename}' not found or already deleted.",
                details={
                    "hint": "Check if the file name is correct and not already deleted.",
                    "file_name": filename,
                },
            )

    def list_filetypes(self) -> pd.DataFrame:
        """List the supported file types that are registered in the database.

        Returns
        -------
        pd.DataFrame
            A dataframe containing the supported file types and their information.
        """
        sql = f"""
        SELECT
            FileID AS file_id,
            FileName AS file_name,
            DateColumn AS date_column,
            DateColumnFormat AS date_column_format,
            AmountColumn AS amount_column,
            ReceiverColumn AS receiver_column,
            CAST(_RowCreatedAt AS STRING) AS row_created_at
        FROM
            `{self.db_client.dataset}.d_filetypes`
        WHERE
            _RowStatus != @deleted_status
        ORDER BY
            _RowCreatedAt DESC
        """  # nosec B608
        return self.db_client.sql_to_pandas(sql, params={"deleted_status": "d"})

    def get_filetype(self, id: str) -> dict:
        """Fetch file-type mapping used for transformation.

        Parameters
        ----------
        id : str
            Deterministic file schema identifier generated from source columns.

        Returns
        -------
        dict
            File-type row containing source-to-canonical column mapping.

        Raises
        ------
        UnknownFileTypeError
            If schema ID is not registered.
        DatabaseQueryError
            If more than one active row matches the same schema ID.
        """
        sql = f"""
        SELECT
            *
        FROM
            `{self.db_client.dataset}.d_filetypes`
        WHERE
            FileID = @file_id
            AND _RowStatus != @deleted_status
        """  # nosec B608
        df = self.db_client.sql_to_pandas(
            sql,
            params={"file_id": id, "deleted_status": "d"},
        )

        if df.empty:
            raise UnknownFileTypeError(
                details={
                    "hint": "The file type has not been registered in the database. Please check the file format and ensure it is supported.",
                    "file_schema": id,
                }
            )

        if len(df) > 1:
            raise DatabaseQueryError(
                message=f"Multiple file types found with the same schema ID '{id}'",
                details={
                    "hint": "This should not happen, as the file schema ID is supposed to be unique. Please check the database for duplicate entries.",
                    "file_schema": id,
                    "row_count": len(df),
                },
            )

        return df.iloc[0].to_dict()

    def generate_filetype_id(self, cols: list[str]) -> str:
        """Create deterministic schema identifier from source column names.

        Non-alphanumeric characters are replaced with underscores to keep identifiers
        storage-safe and comparable.

        Raises
        ------
        ValueError
            If cols is empty.
        """
        sanitized = [re.sub(r"[^a-zA-Z0-9_ .]", "_", col.strip()) for col in cols]
        return "-".join(sanitized)
