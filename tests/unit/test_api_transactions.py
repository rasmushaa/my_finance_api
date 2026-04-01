"""Test FastAPI transaction endpoints with real service and mocked DB client."""

import io

import pandas as pd
from fastapi.testclient import TestClient

from app.api.dependencys import (
    get_require_admin,
    get_require_user,
    get_transaction_service,
)
from app.core.errors.domain import ModelInputError
from app.main import app
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
        }
    )


def build_transaction_service(
    *,
    db_client: DuckDBMockClient,
    predictions: list[str] | None = None,
    model_error: Exception | None = None,
) -> TransactionService:
    model = FakeModelService(
        predictions=predictions or SAMPLE_PREDICTIONS,
        error=model_error,
        metadata={
            "model_name": "test_model",
            "alias": "dev",
            "version": 1,
            "run_id": "run-1",
            "description": "test",
            "package_version": "1.0.0",
            "commit_sha": "abc123",
            "model_features": "date,receiver,amount",
            "model_architecture": "RandomForest",
        },
    )
    return TransactionService(db_client=db_client, model_service=model)


def mock_require_user():
    return {"user_id": "test_user", "sub": "user@example.com"}


def mock_require_admin():
    return {"user_id": "admin_user", "sub": "admin@example.com", "role": "admin"}


def _make_csv_upload(
    content: str = SAMPLE_CSV,
    content_type: str = "text/csv",
    filename: str = "transactions.csv",
):
    return ("file", (filename, io.BytesIO(content.encode()), content_type))


# --------------- Tests: transform/upload ---------------
def test_import_csv_success():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

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
                }
            )
        },
    )
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code == 400


def test_import_csv_model_input_error_returns_400():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_transaction_service(
        db_client=db_client,
        model_error=ModelInputError(
            details={"message": "Input features missing required model features."}
        ),
    )

    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code == 400


def test_import_csv_unauthorized():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code in [401, 422]


# --------------- Tests: register-filetype ---------------
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
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_require_admin] = mock_require_admin
    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json=VALID_FILETYPE_PAYLOAD
    )

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
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json=VALID_FILETYPE_PAYLOAD
    )

    assert response.status_code in [401, 422]


def test_register_filetype_forbidden_for_regular_user():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json=VALID_FILETYPE_PAYLOAD
    )

    assert response.status_code in [401, 403, 422]


def test_register_filetype_invalid_payload_returns_422():
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_filetypes": seed_filetypes_matching_sample_csv()},
    )
    service = build_transaction_service(db_client=db_client)

    app.dependency_overrides[get_require_admin] = mock_require_admin
    app.dependency_overrides[get_transaction_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json={"file_name": "Incomplete"}
    )

    assert response.status_code == 422
