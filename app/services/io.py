import csv
import hashlib
import logging
import re
from typing import Tuple

import chardet
import pandas as pd

from app.core.exceptions.file import DMLError, UnknownFileTypeError
from app.services.model import ModelService

logger = logging.getLogger(__name__)


TRANSACTION_FEATURE_COLUMNS = ["Date", "Amount", "Receiver"]
TRANSACTION_COLUMNS = TRANSACTION_FEATURE_COLUMNS + ["Category"]


class IOService:

    def __init__(self, db_client, model_service: ModelService):
        """Initialize the IO service to handle file operations.

        Parameters
        ----------
            db_client: Database client instance.
            model_service: Model service instance.
        """
        self.db_client = db_client
        self.model_service = model_service

    def add_filetype_to_database(
        self,
        cols: list[str],
        file_name: str,
        date_col: str,
        date_col_format: str,
        amount_col: str,
        receiver_col: str,
    ):
        """Add a new supported filetype row to database.

        Parameters
        ----------
        cols: list[str]
            The column names of the file, used to generate the unique file type ID.
        file_name: str
            The name of the file type (e.g. "Nordea CSV")
        date_col: str
            The name of the date column in the file
        date_col_format: str
            The date format used in the date column (e.g. "%Y-%m-%d")
        amount_col: str
            The name of the amount column in the file
        receiver_col: str
            The name of the receiver/payee column in the file
        """
        data_insert = {
            "FileID": self.__generate_filetype_id(cols),
            "FileName": file_name,
            "DateColumn": date_col,
            "DateColumnFormat": date_col_format,
            "AmountColumn": amount_col,
            "ReceiverColumn": receiver_col,
        }
        df = pd.DataFrame([data_insert])
        self.db_client.append_pandas_to_table(df, "d_filetypes")

    def delete_filetype_from_database(self, filename: str):
        """Soft delete a file type from the database by its unique ID, by marking its
        status as 'd'.

        Parameters
        ----------
        filename: str
            The name of the file type to be deleted.
        """
        sql = f"""
        UPDATE `{self.db_client.dataset}.d_filetypes`
        SET _RowStatus = 'd', _RowUpdatedAt = CURRENT_TIMESTAMP()
        WHERE FileName = '{filename}' AND _RowStatus != 'd'
        """  # nosec B608
        row_count = self.db_client.execute_sql(sql)
        if row_count == 0 or row_count is None:
            raise DMLError(
                details={
                    "file_name": filename,
                    "details": "File type not found or already deleted",
                }
            )

    def append_transactions(self, input_file, user_email: str):
        """Append the user input file to the transactions table in the database.

        All new rows are marked with _RowStatus 'i' for inserted, and the current
        timestamp is added to _RowCreatedAt and _RowUpdatedAt.
        """
        encoding, separator = self.__autodetect_file_coding(input_file)
        df = pd.read_csv(input_file, encoding=encoding, sep=separator)
        df["UserEmail"] = user_email
        other_cols = [c for c in df.columns if c != "UserEmail"]
        df = df[["UserEmail"] + other_cols]  # Ensure UserEmail is the first column
        self.db_client.append_pandas_to_table(df, "f_transactions")
        logger.info(f"Appended {len(df)} rows to f_transactions table in the database.")

    def transform_input_file(self, input_file) -> pd.DataFrame:
        """Opens unkown CSV safely.

        The text encoding, and seperator characters are unkown,
        and must be determined manaully using external libraries.

        The model predictions are added to the file,
        and the file is transformed into the expected format,
        using the file type information from the database.

        The model predictions are also logged in the database for monitoring,
        and linked to the original user input rows using a hash of the original row data.

        Inputs
        ------
        input_file : Streamlit BytesIO
            User provided file, that has already been validated to be a csv

        Raises
        ------
        UnknownFileTypeError
            If the file type is not recognized, and thus not able to be processed.
        """
        # Safe open the file in binary mode to determine encoding and separator
        encoding, separator = self.__autodetect_file_coding(input_file)
        df = pd.read_csv(input_file, encoding=encoding, sep=separator)

        # Transform the file into the expected format using the file type information from the database
        id = self.__generate_filetype_id(list(df.columns))
        file_format_info = self.__get_filetype_info_from_database(id)
        df = self.__transform_input_file(df, file_format_info)

        # Add prediction categories to the file using the ML model
        df["Category"] = self.model_service.predict(df)

        # Add metadata a unique hash of the input row data, which is used to link the predictions for monitoring and auditing purposes.
        now = pd.Timestamp.now()
        df["_RowProcessingID"] = df.apply(
            lambda row: int.from_bytes(
                hashlib.sha256(str(tuple(row) + (now,)).encode()).digest()[:8], "big"
            ),
            axis=1,
        )  # Deterministic, always-positive 64-bit hash of the original row data

        # Log prediction results for monitoring
        df_preds = (
            df[["Category"]].copy().rename(columns={"Category": "PredictedCategory"})
        )
        df_preds["ModelName"] = self.model_service.metadata.get("model_name", "unknown")
        df_preds["ModelAlias"] = self.model_service.metadata.get("alias", "unknown")
        df_preds["ModelVersion"] = self.model_service.metadata.get("version", "unknown")
        df_preds["ModelCommitSHA"] = self.model_service.metadata.get(
            "commit_sha", "unknown"
        )
        df_preds["ModelArchitecture"] = self.model_service.metadata.get(
            "model_architecture", "unknown"
        )
        df_preds["_RowProcessingID"] = df["_RowProcessingID"]  # Link to original row
        self.db_client.append_pandas_to_table(df_preds, "f_predictions")

        logger.info(
            f"Transformed input file with {len(df)} rows and added predictions. Original file schema ID: {id}"
        )

        return df

    def __get_filetype_info_from_database(self, id: str) -> dict:
        """Retrieves the file type information from the database, which is used to
        transform the file into the expected format.

        The file type is identified by a unique key created by concatenating the column names and their data types.

        Inputs
        ------
        id: str
            The unique identifier for the file type
        """
        sql = f"""
        SELECT
            *
        FROM
            `{self.db_client.dataset}.d_filetypes`
        WHERE
            FileID = '{id}'
        """  # nosec B608
        df = self.db_client.sql_to_pandas(sql)

        if df.empty:
            logger.error(f"File type with ID '{id}' not found in database.")
            raise UnknownFileTypeError(details={"file_schema": id})

        return df.iloc[0].to_dict()

    def __transform_input_file(self, df: pd.DataFrame, file_format_info: dict):
        """The Raw CSV input file is transformed into the required format.

        The file is assumed to be known in this part, and its recorded column
        format is quered to transform it into the expected format.
        Floats and Dates are also handled.

        Inputs
        ------
        df: pd.DataFrame
            The user input csv file
        file_format_info: dict
            The file format information retrieved from the database
        """

        # Rename columns to expected names
        df.rename(
            columns={
                file_format_info["DateColumn"]: "Date",
                file_format_info["ReceiverColumn"]: "Receiver",
                file_format_info["AmountColumn"]: "Amount",
            },
            inplace=True,
        )

        # Cast Amounts with ',' to floats, if needed
        if df["Amount"].dtype == "object":
            df["Amount"] = (
                df["Amount"].str.replace(",", ".").astype(float)
                if df["Amount"].str.contains(",").any()
                else df["Amount"].astype(float)
            )

        # Add the user input column
        df["Category"] = None

        # Cast dates and sort by date
        df["Date"] = pd.to_datetime(
            df["Date"], format=file_format_info["DateColumnFormat"]
        ).dt.date
        df.sort_values(by="Date", ascending=True, inplace=True)

        # Keep only the expected columns, in the expected order
        return df[TRANSACTION_COLUMNS]

    def __generate_filetype_id(self, cols: list[str]) -> str:
        """Create a unique identifier for the file type based on its schema, which is
        used as a key in the database to identify different file types.

        Raises
        ------
        ValueError
            If cols is empty.
        """
        sanitized = [re.sub(r"[^a-zA-Z0-9_ .]", "_", col.strip()) for col in cols]
        return "-".join(sanitized)

    def __autodetect_file_coding(self, file_binary) -> Tuple[str, str]:
        """Auto detects used encoding and separator in user provided csv file.

        Details
        -------
        If file parameters are unkwown, it has to be first opened in binary
        to avoid any parsing errors.

        Parameters
        ----------
        file_binary : A subclass of BytesIO
            The raw input file from Streamlit File Uploader

        Returns
        -------
        encoding : str
            Detected encoding. Note, chardet works well, but its not perfect!
        separator : str
            Detected separator in [',', ';', ' ', '\t', '|']
        """
        raw = file_binary.read()
        file_binary.seek(0)
        encoding_dict = chardet.detect(raw)
        encoding = encoding_dict["encoding"]

        dialect = csv.Sniffer().sniff(raw.decode(encoding), delimiters=",; \t|")
        separator = dialect.delimiter

        return encoding, separator
