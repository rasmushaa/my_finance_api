"""Tests for TransactionService using reusable DuckDB mock client."""

import io

import pandas as pd
import pytest

from app.core.errors.domain import UnknownFileTypeError
from app.services.file_types import FileTypesService
from app.services.transactions import TransactionService
from tests.helpers.duckdb_mock_client import DuckDBMockClient

DATASET = "test_dataset_dev"


def create_test_filetypes_db() -> pd.DataFrame:
    """Seed data for the d_filetypes table."""
    return pd.DataFrame(
        {
            "FileID": ["Date-Amount-Receiver", "Deleted-FileType"],
            "FileName": ["Test Bank CSV", "Deleted FileType"],
            "DateColumn": ["Date", "Date"],
            "DateColumnFormat": ["%Y-%m-%d", "%Y-%m-%d"],
            "AmountColumn": ["Amount", "Amount"],
            "ReceiverColumn": ["Receiver", "Receiver"],
            "_RowStatus": ["i", "d"],
            "_RowCreatedAt": [pd.Timestamp("2024-01-01 00:00:00")] * 2,
            "_RowUpdatedAt": [pd.Timestamp("2024-01-01 00:00:00")] * 2,
            "_RowUploadHash": [201, 202],
        }
    )


def make_stateful_mock_client() -> DuckDBMockClient:
    return DuckDBMockClient(
        dataset=DATASET, seed_tables={"d_filetypes": create_test_filetypes_db()}
    )


def make_file_types_service(db_client: DuckDBMockClient) -> FileTypesService:
    return FileTypesService(db_client=db_client)


def make_service(
    db_client: DuckDBMockClient,
) -> tuple[TransactionService, FileTypesService]:
    file_types_service = make_file_types_service(db_client)
    return (
        TransactionService(
            db_client=db_client,
            file_types_service=file_types_service,
        ),
        file_types_service,
    )


def make_csv_bytes(content: str) -> io.BytesIO:
    """Helper: minimal in-memory CSV bytes."""
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = "test.csv"
    return buf


# -------------------------- Public methods (integration-like) --------------------------
EXPECTED_RESULT_COLS = ["Date", "Amount", "Receiver", "Category"]


def test_open_binary_as_pandas_returns_transformed_df():
    """End-to-end: a known CSV file is transformed correctly via the full pipeline."""
    csv_content = (
        "Date;Amount;Receiver\n2024-01-10;50,0;Bookstore\n2024-01-05;20,0;Cafe\n"
    )
    csv_file = make_csv_bytes(csv_content)

    mock_client = make_stateful_mock_client()
    service, _ = make_service(mock_client)

    result = service.transform_input_file(csv_file)

    assert list(result.columns) == EXPECTED_RESULT_COLS
    assert len(result) == 2
    assert result.iloc[0]["Receiver"] in ["Bookstore", "Cafe"]
    assert str(result.iloc[0]["Date"]) == "2024-01-05"

    # Prediction is not applied at the service level anymore
    assert result["Category"].isna().all()
    assert mock_client.append_pandas_to_table.call_count == 0


def test_open_binary_as_pandas_raises_for_unknown_schema():
    """A CSV with an unregistered schema should raise UnknownFileTypeError."""
    csv_content = "TransDate,Value,Payee\n2024-01-10,50.0,Shop\n"
    csv_file = make_csv_bytes(csv_content)

    mock_client = make_stateful_mock_client()
    service, _ = make_service(mock_client)

    with pytest.raises(UnknownFileTypeError):
        service.transform_input_file(csv_file)


def test_add_new_filetype_and_open_binary():
    """A new file type can be registered and then transformed."""
    mock_client = make_stateful_mock_client()
    service, file_types_service = make_service(mock_client)

    new_df = pd.DataFrame(
        {
            "Date": ["2024/01/01"],
            "dollars": ["2,3"],
            "PaymentTarget": ["Shop"],
            "NewCol": ["Extra"],
        }
    )
    file_types_service.add_filetype_to_database(
        list(new_df.columns),
        "New Bank CSV",
        "Date",
        "%Y/%m/%d",
        "dollars",
        "PaymentTarget",
    )

    csv_content = (
        "Date;dollars;PaymentTarget;NewCol\n"
        "2024/01/10;50,0;Bookstore;SomeValue\n"
        "2024/01/05;20,0;Cafe;AnotherValue\n"
    )
    csv_file = make_csv_bytes(csv_content)

    result = service.transform_input_file(csv_file)

    assert list(result.columns) == EXPECTED_RESULT_COLS
    assert len(result) == 2
    assert result.iloc[0]["Receiver"] in ["Bookstore", "Cafe"]
    assert str(result.iloc[0]["Date"]) == "2024-01-05"

    # Prediction is not applied at the service level anymore
    assert result["Category"].isna().all()
