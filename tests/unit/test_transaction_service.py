"""Tests for TransactionService using reusable DuckDB mock client."""

import io
from unittest.mock import Mock

import pandas as pd
import pytest

from app.core.errors.domain import UnknownFileTypeError
from app.services.transactions import TransactionService
from tests.helpers.duckdb_mock_client import DuckDBMockClient
from tests.helpers.fake_services import FakeModelService

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


def make_service(db_client: DuckDBMockClient) -> TransactionService:
    return TransactionService(
        db_client=db_client,
        model_service=FakeModelService(
            predictions=["Uncategorized"],
            metadata={
                "model_name": "test_model",
                "alias": "champion",
                "version": "1",
                "commit_sha": "abc123",
                "model_architecture": "LogisticRegression",
            },
        ),
    )


def make_csv_bytes(content: str) -> io.BytesIO:
    """Helper: minimal in-memory CSV bytes."""
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = "test.csv"
    return buf


# --------------------- Private methods (unit tests) ---------------------
def test_generate_filetype_id_produces_schema_string():
    """KeyID is built from column names joined by '-'."""
    service = TransactionService(db_client=Mock(), model_service=FakeModelService())
    df = pd.DataFrame(
        {"Date": ["2024-01-01"], "Amount": ["10.0"], "Receiver": ["Shop"]}
    )
    key_id = service._TransactionService__generate_filetype_id(list(df.columns))

    assert key_id == "Date-Amount-Receiver"


def test_get_filetype_info_returns_dict_for_known_id():
    """Known KeyID should resolve to a dict with all expected fields."""
    mock_client = make_stateful_mock_client()
    service = make_service(mock_client)

    known_id = "Date-Amount-Receiver"
    result = service._TransactionService__get_filetype_info_from_database(known_id)

    assert isinstance(result, dict)
    assert result["FileName"] == "Test Bank CSV"
    assert result["DateColumn"] == "Date"
    assert result["AmountColumn"] == "Amount"
    assert result["ReceiverColumn"] == "Receiver"
    assert result["DateColumnFormat"] == "%Y-%m-%d"


def test_get_filetype_info_raises_for_unknown_id():
    """Unknown KeyID should raise UnknownFileTypeError."""
    mock_client = make_stateful_mock_client()
    service = make_service(mock_client)

    with pytest.raises(UnknownFileTypeError):
        service._TransactionService__get_filetype_info_from_database("nonexistent:key")


def test_transform_input_file_renames_and_casts():
    """Transformation should rename columns, cast types, and select correct columns."""
    service = TransactionService(db_client=Mock(), model_service=FakeModelService())

    raw_df = pd.DataFrame(
        {
            "Date": ["2024-01-15", "2024-02-20"],
            "Amount": ["-99,90", "150.00"],
            "Receiver": ["Supermarket", "Gas station"],
            "ExtraCol": ["x", "y"],
        }
    )
    file_format_info = {
        "DateColumn": "Date",
        "DateColumnFormat": "%Y-%m-%d",
        "AmountColumn": "Amount",
        "ReceiverColumn": "Receiver",
    }

    result = service._TransactionService__transform_input_file(raw_df, file_format_info)

    assert list(result.columns) == ["Date", "Amount", "Receiver", "Category"]
    assert result["Amount"].dtype == float
    assert result.iloc[0]["Receiver"] == "Supermarket"
    assert result["Category"].isna().all()
    assert result.iloc[0]["Date"] <= result.iloc[-1]["Date"]


# -------------------------- Public methods (integration-like) --------------------------
EXPECTED_RESULT_COLS = ["Date", "Amount", "Receiver", "Category", "_RowProcessingID"]
EXPECTED_PREDICTIONS_COLS = [
    "PredictedCategory",
    "ModelName",
    "ModelAlias",
    "ModelVersion",
    "ModelCommitSHA",
    "ModelArchitecture",
    "_RowProcessingID",
]


def test_open_binary_as_pandas_returns_transformed_df():
    """End-to-end: a known CSV file is transformed correctly via the full pipeline."""
    csv_content = (
        "Date;Amount;Receiver\n2024-01-10;50,0;Bookstore\n2024-01-05;20,0;Cafe\n"
    )
    csv_file = make_csv_bytes(csv_content)

    mock_client = make_stateful_mock_client()
    service = make_service(mock_client)

    result = service.transform_input_file(csv_file)

    assert list(result.columns) == EXPECTED_RESULT_COLS
    assert len(result) == 2
    assert result.iloc[0]["Receiver"] in ["Bookstore", "Cafe"]
    assert str(result.iloc[0]["Date"]) == "2024-01-05"
    assert result["_RowProcessingID"].notna().all()
    assert result["_RowProcessingID"].nunique() == 2

    assert mock_client.append_pandas_to_table.call_count == 1
    logged_df, logged_table = mock_client.append_pandas_to_table.call_args[0]
    assert logged_table == "f_predictions"
    assert list(logged_df.columns) == EXPECTED_PREDICTIONS_COLS
    assert (logged_df["PredictedCategory"] == "Uncategorized").all()
    assert (logged_df["ModelName"] == "test_model").all()


def test_open_binary_as_pandas_raises_for_unknown_schema():
    """A CSV with an unregistered schema should raise UnknownFileTypeError."""
    csv_content = "TransDate,Value,Payee\n2024-01-10,50.0,Shop\n"
    csv_file = make_csv_bytes(csv_content)

    mock_client = make_stateful_mock_client()
    service = make_service(mock_client)

    with pytest.raises(UnknownFileTypeError):
        service.transform_input_file(csv_file)


def test_add_new_filetype_and_open_binary():
    """A new file type can be registered and then transformed."""
    mock_client = make_stateful_mock_client()
    service = make_service(mock_client)

    new_df = pd.DataFrame(
        {
            "Date": ["2024/01/01"],
            "dollars": ["2,3"],
            "PaymentTarget": ["Shop"],
            "NewCol": ["Extra"],
        }
    )
    service.add_filetype_to_database(
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
    assert result["_RowProcessingID"].notna().all()
