"""Tests for FileTypesService using reusable DuckDB mock client."""

from unittest.mock import Mock

import pandas as pd
import pytest

from app.core.errors.domain import UnknownFileTypeError
from app.services.file_types import FileTypesService
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


def make_service(db_client: DuckDBMockClient) -> FileTypesService:
    return FileTypesService(db_client=db_client)


# --------------------- generate_filetype_id ---------------------
def test_generate_filetype_id_produces_schema_string():
    """KeyID is built from column names joined by '-'."""
    service = FileTypesService(db_client=Mock())
    df = pd.DataFrame(
        {"Date": ["2024-01-01"], "Amount": ["10.0"], "Receiver": ["Shop"]}
    )
    key_id = service.generate_filetype_id(list(df.columns))

    assert key_id == "Date-Amount-Receiver"


# --------------------- get_filetype ---------------------
def test_get_filetype_info_returns_dict_for_known_id():
    """Known KeyID should resolve to a dict with all expected fields."""
    mock_client = make_stateful_mock_client()
    service = make_service(mock_client)

    known_id = "Date-Amount-Receiver"
    result = service.get_filetype(known_id)

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
        service.get_filetype("nonexistent:key")
