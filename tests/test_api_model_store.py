import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.providers import (
    get_model_store,
    get_require_admin,
    get_require_user,
)
from app.core.exceptions.base import ErrorCodes
from app.core.exceptions.model import ModelNotAvailableError
from app.main import app
from app.services.model import ModelLoadingStatus

# Container needs JWT, which needs environment variables
os.environ["APP_JWT_SECRET"] = "test-secret-key-for-jwt-testing"
os.environ["APP_JWT_EXP_DELTA_MINUTES"] = "60"


# --------------- Mock Model Store and Dummy Model for Testing ----------------
class DummyModel:
    def predict(self, df):
        return ["class_a"] * len(df)


class DummyStore:
    def __init__(
        self, is_ready=True, status=ModelLoadingStatus.READY, error_message=None
    ):
        self._model = DummyModel() if is_ready else None
        self._model_info = (
            {
                "model_name": "test_model",
                "alias": "test_alias",
                "version": 1,
                "run_id": "test_run_123",
                "description": "Test model for unit tests",
                "package_version": "1.0.0",
                "commit_sha": "abc123def456",
                "model_features": "a,b,c",
                "model_architecture": "RandomForest",
            }
            if is_ready
            else {}
        )
        self._status = status
        self._error_message = error_message

    def predict(self, input_df):
        if not self.is_ready:
            raise ModelNotAvailableError()
        return self._model.predict(input_df)

    @property
    def metadata(self):
        if not self.is_ready:
            raise ModelNotAvailableError()
        return self._model_info

    @property
    def is_ready(self):
        return self._status == ModelLoadingStatus.READY

    @property
    def status(self):
        return self._status

    @property
    def error_message(self):
        return self._error_message


# ------------------ Mock Dependency Overrides for Authentication and Model Store ------------------
def override_store():
    return DummyStore()


def override_store_not_ready():
    return DummyStore(is_ready=False, status=ModelLoadingStatus.LOADING)


def mock_require_user():
    return {"user_id": "test_user", "username": "testuser"}


def mock_require_role():
    def _mock_role():
        return {"user_id": "test_admin", "role": "admin"}

    return _mock_role


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    # Clean up after tests
    app.dependency_overrides.clear()


# Test predict endpoint
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_user] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    request_payload = {"inputs": {"a": [1.0, 3.0], "b": [2.0, 4.0]}}
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 200
    assert response.json() == {"predictions": ["class_a", "class_a"]}


# Test predict endpoint with models not ready
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_model_not_ready():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_user] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store_not_ready

    client = TestClient(app)
    request_payload = {"inputs": {"a": [1.0, 3.0], "b": [2.0, 4.0]}}
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 503
    assert response.json()["code"] == ErrorCodes.ML_MODEL.value


# Test predict endpoint with missing features
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_missing_feature():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_user] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0]
            # Missing feature 'b'
        }
    }
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 400
    assert response.json()["code"] == ErrorCodes.ML_MODEL.value


# Test predict endpoint with extra features
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_extra_feature():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_user] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0],
            "b": [2.0, 4.0],
            "c": [5.0, 6.0],  # Extra feature 'c'
        }
    }
    response = client.post("/model/predict", json=request_payload)
    print(response.json())
    assert response.status_code == 400
    assert response.json()["code"] == ErrorCodes.ML_MODEL.value


# Test model info endpoint when models not ready
def test_model_info_endpoint_not_ready():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store_not_ready

    client = TestClient(app)
    response = client.get("/model/metadata")
    assert response.status_code == 503
    assert response.json()["code"] == ErrorCodes.ML_MODEL.value


# Test model info endpoint - when ready
def test_model_info_endpoint():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    response = client.get("/model/metadata")
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert response.json()["model_name"] == "test_model"


# Test model status endpoint - loading
def test_model_status_endpoint_loading():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_user] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store_not_ready

    client = TestClient(app)
    response = client.get("/model/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "loading"
    assert data["is_ready"] is False


# Test model endpoints unauthorized
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_model_endpoints_unauthorized():
    """Test that model endpoints require authentication."""
    # Don't override auth dependencies - should fail
    app.dependency_overrides.clear()
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)

    # Test predict endpoint
    request_payload = {"inputs": {"a": [1.0, 3.0], "b": [2.0, 4.0]}}
    predict_response = client.post("/model/predict", json=request_payload)

    # Test status endpoint
    status_response = client.get("/model/status")

    # Test metadata endpoint
    metadata_response = client.get("/model/metadata")

    # All endpoints should require authentication
    assert predict_response.status_code in [401, 422]
    assert status_response.status_code in [401, 422]
    assert metadata_response.status_code in [
        401,
        422,
        403,
    ]  # 403 for admin-required endpoint
