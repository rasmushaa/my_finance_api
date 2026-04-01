"""Test FastAPI IO endpoints using DI container pattern."""

import io
import os

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.dependencys import (
    get_require_admin,
    get_require_user,
    get_transaction_service,
)
from app.core.errors.domain import ModelInputError, UnknownFileTypeError
from app.main import app

# Container needs JWT, which needs environment variables
os.environ["APP_JWT_SECRET"] = "test-secret-key-for-jwt-testing"
os.environ["APP_JWT_EXP_DELTA_MINUTES"] = "60"

# --------------- Sample CSV data ---------------
SAMPLE_CSV = (
    "date,receiver,amount\n2024-01-01,Grocery Store,-25.50\n2024-01-02,Salary,2000.00\n"
)
SAMPLE_PREDICTIONS = ["Food", "Income"]


# --------------- Mock Services ---------------
class MockModelStore:
    """Mock model service that returns predefined predictions."""

    def __init__(self, predictions: list | None = None, should_fail: bool = False):
        self.predictions = (
            predictions if predictions is not None else SAMPLE_PREDICTIONS
        )
        self.should_fail = should_fail

    def predict(self, input_df: pd.DataFrame) -> list:
        if self.should_fail:
            raise ModelInputError(
                details={"message": "Input features missing required model features."}
            )
        return self.predictions


class MockIOService:
    """Mock IO service with an embedded MockModelStore."""

    def __init__(
        self,
        result_df: pd.DataFrame | None = None,
        io_should_fail: bool = False,
        model_store: MockModelStore | None = None,
    ):
        self.result_df = (
            result_df
            if result_df is not None
            else pd.DataFrame(
                {
                    "date": ["2024-01-01", "2024-01-02"],
                    "receiver": ["Grocery Store", "Salary"],
                    "amount": [-25.50, 2000.00],
                }
            )
        )
        self.io_should_fail = io_should_fail
        self.model_service = (
            model_store if model_store is not None else MockModelStore()
        )

    def transform_input_file(self, file) -> pd.DataFrame:
        if self.io_should_fail:
            raise UnknownFileTypeError(details={"reason": "Unrecognised file format"})
        df = self.result_df.copy()
        df["Category"] = self.model_service.predict(df)
        return df

    def add_filetype_to_database(self, **kwargs):
        self.last_registered = kwargs


# --------------- Dependency Override Factories ---------------
def override_io_service():
    return MockIOService()


def override_io_service_unknown_filetype():
    return MockIOService(io_should_fail=True)


def override_io_service_model_failing():
    return MockIOService(model_store=MockModelStore(should_fail=True))


def mock_require_user():
    return {"user_id": "test_user", "username": "testuser"}


def mock_require_admin():
    return {"user_id": "admin_user", "username": "adminuser", "role": "admin"}


# --------------- Fixtures ---------------
@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Ensure clean dependency state for each test."""
    yield
    app.dependency_overrides.clear()


# --------------- Helper ---------------
def _make_csv_upload(
    content: str = SAMPLE_CSV,
    content_type: str = "text/csv",
    filename: str = "transactions.csv",
):
    return ("file", (filename, io.BytesIO(content.encode()), content_type))


# --------------- Tests ---------------
def test_import_csv_success():
    """Test that a valid CSV upload returns a processed CSV with predicted
    categories."""
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = override_io_service

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    # Validate response metadata and headers
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        'attachment; filename="processed_transactions.csv"'
        in response.headers["content-disposition"]
    )
    assert "x-row-count" in response.headers
    assert int(response.headers["x-row-count"]) == 2
    assert "x-columns" in response.headers
    assert "Category" in response.headers["x-columns"].split(",")


def test_import_csv_unknown_filetype_error_returns_400():
    """Test that an unrecognised CSV structure from IOService returns a 400 error."""
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = (
        override_io_service_unknown_filetype
    )

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code == 400


def test_import_csv_model_input_error_returns_400():
    """Test that a model prediction failure due to bad features returns a 400 error."""
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = (
        override_io_service_model_failing
    )

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code == 400


def test_import_csv_unauthorized():
    """Test that the endpoint rejects requests without authentication."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_transaction_service] = override_io_service

    client = TestClient(app)
    response = client.post("/app/v1/transactions/transform", files=[_make_csv_upload()])

    assert response.status_code in [401, 422]


# --------------- register_filetype tests ---------------

VALID_FILETYPE_PAYLOAD = {
    "cols": ["Date", "Amount", "Receiver"],
    "file_name": "Test Bank CSV",
    "date_col": "Date",
    "date_col_format": "%Y-%m-%d",
    "amount_col": "Amount",
    "receiver_col": "Receiver",
}


def test_register_filetype_success():
    """Admin user with valid payload receives 200 and the service method is called."""
    mock_io = MockIOService()
    app.dependency_overrides[get_require_admin] = mock_require_admin
    app.dependency_overrides[get_transaction_service] = lambda: mock_io

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json=VALID_FILETYPE_PAYLOAD
    )

    assert response.status_code == 200
    assert mock_io.last_registered["file_name"] == "Test Bank CSV"
    assert mock_io.last_registered["date_col"] == "Date"
    assert mock_io.last_registered["amount_col"] == "Amount"
    assert mock_io.last_registered["receiver_col"] == "Receiver"


def test_register_filetype_unauthorized():
    """Request without any auth token is rejected before reaching the service."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_transaction_service] = override_io_service

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json=VALID_FILETYPE_PAYLOAD
    )

    assert response.status_code in [401, 422]


def test_register_filetype_forbidden_for_regular_user():
    """A non-admin authenticated user must not be able to register file types."""
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_transaction_service] = override_io_service
    # get_require_admin is NOT overridden — real check runs and should reject

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json=VALID_FILETYPE_PAYLOAD
    )

    assert response.status_code in [401, 403, 422]


def test_register_filetype_invalid_payload_returns_422():
    """Missing required fields return a 422 Unprocessable Entity from FastAPI
    validation."""
    app.dependency_overrides[get_require_admin] = mock_require_admin
    app.dependency_overrides[get_transaction_service] = override_io_service

    client = TestClient(app)
    response = client.post(
        "/app/v1/transactions/register-filetype", json={"file_name": "Incomplete"}
    )

    assert response.status_code == 422
