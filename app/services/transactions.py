"""Transaction transformation and persistence service."""

import csv
import logging
from typing import Tuple

import chardet
import pandas as pd

from app.core.errors.domain import DatabaseQueryError
from app.services.file_types import FileTypesService

logger = logging.getLogger(__name__)


TRANSACTION_COLUMNS = [
    "Date",
    "Amount",
    "Receiver",
    "Category",
]  # Canonical transformed CSV column order (without warehouse metadata columns).

TRANSACTION_LABELS = {  # Reporting pipelines and model outputs depend on these exact keys.
    "FOOD": "All normal food and lunch expenses (including groceries and pet food).",
    "ENTERTAINMENT": "All expenses related to leisure activities, such as movies, concerts, cafes, and restaurants.",
    "COMMUTING": "All expenses related to transportation and commuting, such as public transportation, fuel, parking, and tolls",
    "OTHER-INCOME": "All income that does not fit into the SALARY category, such as gifts, refunds, and other miscellaneous income",
    "TECHNOLOGY": "All expenses related to technology and electronics, such as computer and phone purchases, software subscriptions, and online services",
    "HEALTH": "All expenses related to health and wellness, such as medical bills, cosmetics, and haircuts",
    "LIVING": "All expenses related to living costs, such as rent, utilities, housing maintenance, and insurances",
    "HOBBIES": "All expenses related to hobbies and personal interests, such as sports equipment, books, and games",
    "HOUSEHOLD-ITEMS": "All expenses related to household items, such as furniture, appliances, and tools",
    "CLOTHING": "All expenses related to clothing and footwear (online returns can be balanced against original purchases if amounts match exactly).",
    "UNCATEGORIZED": "All transactions that could not be categorized into the other categories, such as student loan payments, taxes, and other expenses that do not fit into the other categories",
    "INVESTING": "All expenses related to investments and financial products, such as stock purchases, cryptocurrency transactions, and investment fund contributions",
    "SALARY": "All income from salary, including benefits and refunds from work",
}


class TransactionService:
    """Service for transaction ingestion, normalization, and utility queries."""

    def __init__(self, db_client, file_types_service: FileTypesService):
        """Initialize transaction service.

        Parameters
        ----------
        db_client :
            Database client used for BigQuery reads/writes.
        file_types_service : FileTypesService
            Service used to resolve registered input file schema mappings.
        """
        self.db_client = db_client
        self.file_types_service = file_types_service

    def get_transaction_labels(self) -> list[dict[str, str]]:
        """Return canonical transaction label definitions.

        Returns
        -------
        list[dict[str, str]]
            List containing ``{"key": ..., "description": ...}`` mappings.
        """
        return [
            {"key": key, "description": description}
            for key, description in TRANSACTION_LABELS.items()
        ]

    def upload_transactions(self, input_file, user_email: str):
        """Append the user input file to the transactions table in the database.

        Empty values are normalized to ``"N/A"`` before persistence to keep downstream
        reporting logic consistent and avoid mixed null/empty-string handling.

        Parameters
        ----------
        input_file :
            Open file-like object containing transformed CSV rows.
        user_email : str
            Authenticated user email used for row ownership.
        """
        encoding, separator = self.__autodetect_file_coding(input_file)
        df = pd.read_csv(input_file, encoding=encoding, sep=separator)
        df["UserEmail"] = user_email
        df = df[
            ["UserEmail", "Date", "Amount", "Receiver", "Category", "RowProcessingID"]
        ]
        df = df.fillna("N/A")
        self.db_client.append_pandas_to_table(df, "f_transactions")

    def transform_input_file(self, input_file) -> pd.DataFrame:
        """Normalize an unknown CSV into canonical transaction schema.

        The method auto-detects encoding/separator, resolves source column mapping via
        file-type registry, normalizes types, and returns canonical column order.

        Parameters
        ----------
        input_file :
            Binary file-like object for a user-provided CSV upload.

        Returns
        -------
        pd.DataFrame
            Normalized transaction rows with columns in ``TRANSACTION_COLUMNS`` order.

        Raises
        ------
        UnknownFileTypeError
            If source schema is not registered in file-type registry.
        """
        encoding, separator = self.__autodetect_file_coding(input_file)
        df = pd.read_csv(input_file, encoding=encoding, sep=separator)

        # Transform the file into the expected format using the file type information from the database
        id = self.file_types_service.generate_filetype_id(df.columns.tolist())
        file_format_info = self.file_types_service.get_filetype(id)

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
        df = df[TRANSACTION_COLUMNS]
        return df

    def get_latest_entry_date(self, user_email: str) -> str:
        """Get the date of the latest transaction entry for the user.

        Parameters
        ----------
        user_email : str
            The email of the user to get the latest entry date for.

        Returns
        -------
        str
            ISO format string of the latest transaction date for the user, or None if no transactions exist.
        """
        sql = f"""
        SELECT MAX(Date) as latest_date
        FROM `{self.db_client.dataset}.f_transactions`
        WHERE UserEmail = @user_email AND _RowStatus != @deleted_status
        """  # nosec B608
        df = self.db_client.sql_to_pandas(
            sql,
            params={"user_email": user_email, "deleted_status": "d"},
        )
        if df.empty:
            raise DatabaseQueryError(
                message=f"No transactions found for user {user_email} when querying latest entry date.",
                details={
                    "hint": "This may indicate that the user has not uploaded any transactions yet, or that there is an issue with the database query.",
                    "user_email": user_email,
                },
            )
        latest_date = df["latest_date"].iloc[0]
        return latest_date.isoformat() if pd.notna(latest_date) else None

    def __autodetect_file_coding(self, file_binary) -> Tuple[str, str]:
        """Auto-detect file encoding and separator for user-provided CSV.

        Details
        -------
        Reading raw bytes first avoids decode errors when upload origin/locale is
        unknown and allows delimiter sniffing on decoded content.

        Parameters
        ----------
        file_binary :
            Binary file-like object from FastAPI upload handling.

        Returns
        -------
        encoding : str
            Detected text encoding (best effort from `chardet`).
        separator : str
            Detected separator in [',', ';', ' ', '\t', '|']
        """
        raw = file_binary.read()
        file_binary.seek(0)
        encoding_dict = chardet.detect(raw)
        encoding = encoding_dict["encoding"]

        dialect = csv.Sniffer().sniff(raw.decode(encoding), delimiters=",; \t|")
        separator = dialect.delimiter
        logger.debug(
            f"Auto-detected file (encoding: {encoding}, separator: '{separator}')"
        )

        return encoding, separator
