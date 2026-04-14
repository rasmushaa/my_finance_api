"""Test FastAPI transaction endpoints with real service and mocked DB client."""

import io

import pandas as pd
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_db_client,
    get_file_types_service,
    get_model_store,
    get_require_admin,
    get_require_user,
    get_transaction_service,
)
from app.core.errors.auth import UserNotAuthorizedError
from app.main import app
from app.services.file_types import FileTypesService
from app.services.transactions import TransactionService
from tests.helpers.duckdb_mock_client import DuckDBMockClient
from tests.helpers.fake_services import FakeModelService

# --------------- Sample CSV data ---------------
SAMPLE_CSV = (
    "date,receiver,amount\n2024-01-01,Grocery Store,-25.50\n2024-01-02,Salary,2000.00\n"
)
SAMPLE_PREDICTIONS = ["Food", "Income"]
DATASET = "test_dataset_dev"


def seed_filetypes_matching_sample_csv() -> pd.DataFrame:
    """Seed d_filetypes so SAMPLE_CSV can be transformed by TransactionService."""
    return pd.DataFrame(
        {
            "FileID": ["date-receiver-amount"],
            "FileName": ["Sample CSV"],
            "DateColumn": ["date"],
            "DateColumnFormat": ["%Y-%m-%d"],
            "AmountColumn": ["amount"],
            "ReceiverColumn": ["receiver"],
            "_RowStatus": ["i"],
            "_RowCreatedAt": [pd.Timestamp("2024-01-01 00:00:00")],
            "_RowUpdatedAt": [pd.Timestamp("2024-01-01 00:00:00")],
            "_RowUploadHash": [301],
        }
    )


def build_file_types_service(*, db_client: DuckDBMockClient) -> FileTypesService:
    return FileTypesService(db_client=db_client)


def build_transaction_service(*, db_client: DuckDBMockClient) -> TransactionService:
    return TransactionService(
        db_client=db_client,
        file_types_service=build_file_types_service(db_client=db_client),
    )


def build_model_service(
    *,
    predictions: list[str] | None = None,
) -> FakeModelService:
    return FakeModelService(
        predictions=predictions or SAMPLE_PREDICTIONS,
        prod_metadata={
            "model_name": "test_model",
            "aliases": ["prod"],
            "version": 1,
            "run_id": "run-1",
            "description": "test",
            "package_version": "1.0.0",
            "commit_sha": "abc123",
            "commit_head_sha": "abc123head",
            "model_features": "date,receiver,amount",
            "model_architecture": "RandomForest",
        },
    )


def mock_require_admin():
    return {"user_id": "admin_user", "sub": "admin@example.com", "role": "admin"}


def mock_require_user():
    return {"user_id": "test_user", "sub": "user@example.com"}


def mock_forbidden_admin():
    raise UserNotAuthorizedError()


def _make_csv_upload(
    content: str = SAMPLE_CSV,
    content_type: str = "text/csv",
    filename: str = "transactions.csv",
):
    return ("file", (filename, io.BytesIO(content.encode()), content_type))


# -- Transform --------------------------------
def test_import_csv_success():
    """Vanilla success case: valid CSV, known file type, authorized user."""
    # Actual mock database client
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )

    service = build_transaction_service(db_client=db_client)
    model = build_model_service()

    # API dependency overrides to inject our mocks
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = lambda: service
    app.dependency_overrides[get_model_store] = lambda: model
    app.dependency_overrides[get_db_client] = lambda: db_client

    # Test client to call the API endpoint
    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    # Assertions on the response
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        'attachment; filename="processed_transactions.csv"'
        in response.headers["content-disposition"]
    )
    assert int(response.headers["x-row-count"]) == 2
    assert "Category" in response.headers["x-columns"].split(",")


def test_import_csv_unknown_filetype_error_returns_400():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={
            "d_filetypes": pd.DataFrame(
                {
                    "FileID": ["different-schema"],
                    "FileName": ["Other CSV"],
                    "DateColumn": ["Date"],
                    "DateColumnFormat": ["%Y-%m-%d"],
                    "AmountColumn": ["Amount"],
                    "ReceiverColumn": ["Receiver"],
                    "_RowStatus": ["i"],
                    "_RowCreatedAt": [pd.Timestamp("2024-01-01 00:00:00")],
                    "_RowUpdatedAt": [pd.Timestamp("2024-01-01 00:00:00")],
                    "_RowUploadHash": [302],
                }
            )
        },
    )
    service = build_transaction_service(db_client=db_client)
    model = build_model_service()

    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = lambda: service
    app.dependency_overrides[get_model_store] = lambda: model
    app.dependency_overrides[get_db_client] = lambda: db_client

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code == 400


def test_import_csv_unauthorized():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_transaction_service(db_client=db_client)
    model = build_model_service()

    app.dependency_overrides[get_transaction_service] = lambda: service
    app.dependency_overrides[get_model_store] = lambda: model
    app.dependency_overrides[get_db_client] = lambda: db_client

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code in [401, 422]


# --------------- Tests: filetypes/register ---------------
VALID_FILETYPE_PAYLOAD = {
    "cols": ["Date", "Amount", "Receiver"],
    "file_name": "Test Bank CSV",
    "date_col": "Date",
    "date_col_format": "%Y-%m-%d",
    "amount_col": "Amount",
    "receiver_col": "Receiver",
}


def test_register_filetype_success():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_file_types_service(db_client=db_client)

    app.dependency_overrides[get_require_admin] = mock_require_admin
    app.dependency_overrides[get_file_types_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/filetypes/register", json=VALID_FILETYPE_PAYLOAD)

    assert response.status_code == 200

    inserted = db_client.sql_to_pandas(
        f"""
        SELECT
            *
        FROM
            `{DATASET}.d_filetypes`
        WHERE
            FileName = 'Test Bank CSV'
            AND _RowStatus != 'd'
        """
    )
    assert len(inserted) == 1
    assert inserted.iloc[0]["DateColumn"] == "Date"
    assert inserted.iloc[0]["AmountColumn"] == "Amount"
    assert inserted.iloc[0]["ReceiverColumn"] == "Receiver"


def test_register_filetype_unauthorized():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_file_types_service(db_client=db_client)

    app.dependency_overrides[get_file_types_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/filetypes/register", json=VALID_FILETYPE_PAYLOAD)

    assert response.status_code in [401, 422]


def test_register_filetype_forbidden_for_regular_user():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_file_types_service(db_client=db_client)

    app.dependency_overrides[get_require_admin] = mock_forbidden_admin
    app.dependency_overrides[get_file_types_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/filetypes/register", json=VALID_FILETYPE_PAYLOAD)

    assert response.status_code == 403


def test_register_filetype_invalid_payload_returns_422():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_file_types_service(db_client=db_client)

    app.dependency_overrides[get_require_admin] = mock_require_admin
    app.dependency_overrides[get_file_types_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/app/v1/filetypes/register", json={"file_name": "Incomplete"}
    )

    assert response.status_code == 422
