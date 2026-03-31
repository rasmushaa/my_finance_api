"""Tests for IOService using DuckDB as an in-process SQL engine."""

import io
import os
from unittest.mock import Mock

import duckdb
import pandas as pd
import pytest

from app.core.exceptions.file import UnknownFileTypeError
from app.services.io import IOService


class MockModelStore:
    """Minimal mock model service for IOService tests."""

    metadata = {
        "model_name": "test_model",
        "alias": "champion",
        "version": "1",
        "commit_sha": "abc123",
        "model_architecture": "LogisticRegression",
    }

    def predict(self, input_df: pd.DataFrame) -> list:
        return ["Uncategorized"] * len(input_df)


# -------------------------- Fixtures --------------------------


@pytest.fixture
def setup_env():
    os.environ["GCP_BQ_DATASET"] = "test_dataset"
    os.environ["ENV"] = "dev"
    yield
    for key in ["GCP_BQ_DATASET", "ENV"]:
        if key in os.environ:
            del os.environ[key]


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
        }
    )


def query_mock_filetypes_db(query: str) -> pd.DataFrame:
    """Execute SQL against an in-memory DuckDB instance seeded with d_filetypes."""
    seed = create_test_filetypes_db()
    dataset_name = f"{os.getenv('GCP_BQ_DATASET')}_{os.getenv('ENV')}"

    con = duckdb.connect()
    con.register("d_filetypes_seed", seed)
    con.execute(f"CREATE SCHEMA {dataset_name}")
    con.execute(
        f"CREATE TABLE {dataset_name}.d_filetypes AS SELECT * FROM d_filetypes_seed"
    )
    # DuckDB does not support BigQuery backtick quoting — strip them before executing
    duckdb_query = query.replace("`", "")
    print(f"\n[DuckDB] Query: {duckdb_query}")
    result = con.execute(duckdb_query).df()
    print(f"[DuckDB] Result ({len(result)} rows):\n{result}")
    return result


def make_stateful_mock_client(setup_env) -> Mock:
    """Return a Mock db_client backed by a single persistent DuckDB connection.

    Both sql_to_pandas and append_pandas_to_table operate on the same in-memory
    database, so rows written via append are visible to subsequent sql_to_pandas
    queries.
    """
    dataset_name = f"{os.getenv('GCP_BQ_DATASET')}_{os.getenv('ENV')}"

    con = duckdb.connect()
    seed = create_test_filetypes_db()
    con.register("_seed", seed)
    con.execute(f"CREATE SCHEMA {dataset_name}")
    con.execute(f"CREATE TABLE {dataset_name}.d_filetypes AS SELECT * FROM _seed")

    def sql_executor(query: str) -> pd.DataFrame:
        return con.execute(query.replace("`", "")).df()

    def append_executor(df: pd.DataFrame, table_name: str):
        # Add missing metadata columns if not present (mimic db_client)
        df = df.copy()
        if "_RowStatus" not in df.columns:
            df["_RowStatus"] = "i"
        con.register("_insert_df", df)
        table_exists = con.execute(
            f"SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema = '{dataset_name}' AND table_name = '{table_name}'"
        ).fetchone()[0]
        if table_exists:
            con.execute(
                f"INSERT INTO {dataset_name}.{table_name} SELECT * FROM _insert_df"
            )
        else:
            con.execute(
                f"CREATE TABLE {dataset_name}.{table_name} AS SELECT * FROM _insert_df"
            )

    mock_client = Mock()
    mock_client.dataset = dataset_name
    mock_client.sql_to_pandas.side_effect = sql_executor
    mock_client.append_pandas_to_table.side_effect = append_executor
    return mock_client


# Helper: minimal in-memory CSV bytes
def make_csv_bytes(content: str) -> io.BytesIO:
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = "test.csv"
    return buf


# --------------------- Private methods (unit tests) ---------------------


def test_generate_filetype_id_produces_schema_string(setup_env):
    """KeyID is built from column names joined by '-'."""
    service = IOService(db_client=Mock(), model_service=MockModelStore())
    df = pd.DataFrame(
        {"Date": ["2024-01-01"], "Amount": ["10.0"], "Receiver": ["Shop"]}
    )
    key_id = service._IOService__generate_filetype_id(list(df.columns))

    assert key_id == "Date-Amount-Receiver"


def test_get_filetype_info_returns_dict_for_known_id(setup_env):
    """Known KeyID should resolve to a dict with all expected fields."""
    mock_client = make_stateful_mock_client(setup_env)
    service = IOService(db_client=mock_client, model_service=MockModelStore())

    known_id = "Date-Amount-Receiver"
    result = service._IOService__get_filetype_info_from_database(known_id)

    assert isinstance(result, dict)
    assert result["FileName"] == "Test Bank CSV"
    assert result["DateColumn"] == "Date"
    assert result["AmountColumn"] == "Amount"
    assert result["ReceiverColumn"] == "Receiver"
    assert result["DateColumnFormat"] == "%Y-%m-%d"


def test_get_filetype_info_raises_for_unknown_id(setup_env):
    """Unknown KeyID should raise UnknownFileTypeError."""
    mock_client = make_stateful_mock_client(setup_env)
    service = IOService(db_client=mock_client, model_service=MockModelStore())

    with pytest.raises(UnknownFileTypeError):
        service._IOService__get_filetype_info_from_database("nonexistent:key")


def test_transform_input_file_renames_and_casts(setup_env):
    """Transformation should rename columns, cast types, and select correct columns."""
    service = IOService(db_client=Mock(), model_service=MockModelStore())

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

    result = service._IOService__transform_input_file(raw_df, file_format_info)

    assert list(result.columns) == ["Date", "Amount", "Receiver", "Category"]
    assert result["Amount"].dtype == float
    assert result.iloc[0]["Receiver"] == "Supermarket"
    assert result["Category"].isna().all()
    # Sorted ascending by date
    assert result.iloc[0]["Date"] <= result.iloc[-1]["Date"]


# -------------------------- Public methods (integration) --------------------------

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


def test_open_binary_as_pandas_returns_transformed_df(setup_env):
    """End-to-end: a known CSV file is transformed correctly via the full pipeline."""
    csv_content = (
        "Date;Amount;Receiver\n2024-01-10;50,0;Bookstore\n2024-01-05;20,0;Cafe\n"
    )
    csv_file = make_csv_bytes(csv_content)

    mock_client = make_stateful_mock_client(setup_env)
    service = IOService(db_client=mock_client, model_service=MockModelStore())

    result = service.transform_input_file(csv_file)

    assert list(result.columns) == EXPECTED_RESULT_COLS
    assert len(result) == 2
    assert result.iloc[0]["Receiver"] in ["Bookstore", "Cafe"]
    assert str(result.iloc[0]["Date"]) == "2024-01-05"
    # Each row gets a unique processing ID linking it to the f_predictions log
    assert result["_RowProcessingID"].notna().all()
    assert result["_RowProcessingID"].nunique() == 2
    # Predictions were logged to f_predictions
    assert mock_client.append_pandas_to_table.call_count == 1
    logged_df, logged_table = mock_client.append_pandas_to_table.call_args[0]
    assert logged_table == "f_predictions"
    assert list(logged_df.columns) == EXPECTED_PREDICTIONS_COLS
    assert (logged_df["PredictedCategory"] == "Uncategorized").all()
    assert (logged_df["ModelName"] == "test_model").all()


def test_open_binary_as_pandas_raises_for_unknown_schema(setup_env):
    """A CSV with an unregistered schema should raise UnknownFileTypeError."""
    # This CSV has different columns than what's in the mock DB
    csv_content = "TransDate,Value,Payee\n2024-01-10,50.0,Shop\n"
    csv_file = make_csv_bytes(csv_content)

    mock_client = make_stateful_mock_client(setup_env)
    service = IOService(db_client=mock_client, model_service=MockModelStore())

    with pytest.raises(UnknownFileTypeError):
        service.transform_input_file(csv_file)


def test_add_new_filetype_and_open_binary(setup_env):
    """Test that a new file type can be added to the database and retrieved."""
    mock_client = make_stateful_mock_client(setup_env)
    service = IOService(db_client=mock_client, model_service=MockModelStore())

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

    csv_content = "Date;dollars;PaymentTarget;NewCol\n2024/01/10;50,0;Bookstore;SomeValue\n2024/01/05;20,0;Cafe;AnotherValue\n"
    csv_file = make_csv_bytes(csv_content)

    result = service.transform_input_file(csv_file)

    assert list(result.columns) == EXPECTED_RESULT_COLS
    assert len(result) == 2
    assert result.iloc[0]["Receiver"] in ["Bookstore", "Cafe"]
    assert str(result.iloc[0]["Date"]) == "2024-01-05"
    assert result["_RowProcessingID"].notna().all()
