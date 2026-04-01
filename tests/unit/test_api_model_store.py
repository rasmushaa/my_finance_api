import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencys import get_model_store, get_require_admin
from app.core.errors.base_error import ErrorCode
from app.main import app

# Container needs JWT, which needs environment variables
os.environ["APP_JWT_SECRET"] = "test-secret-key-for-jwt-testing"
os.environ["APP_JWT_EXP_DELTA_MINUTES"] = "60"


# --------------- Mock Model Store and Dummy Model for Testing ----------------
class DummyModel:
    def predict(self, df):
        return ["class_a"] * len(df)


class DummyStore:
    def __init__(self, is_ready=True, error_message=None):
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

    def predict(self, input_df):
        return self._model.predict(input_df)

    @property
    def metadata(self):
        return self._model_info


# ------------------ Mock Dependency Overrides for Authentication and Model Store ------------------
def override_store():
    return DummyStore()


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
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    request_payload = {"inputs": {"a": [1.0, 3.0], "b": [2.0, 4.0]}}
    response = client.post("/app/v1/model/predict", json=request_payload)
    assert response.status_code == 200
    assert response.json() == {"predictions": ["class_a", "class_a"]}


# Test predict endpoint with missing features
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_missing_feature():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0]
            # Missing feature 'b'
        }
    }
    response = client.post("/app/v1/model/predict", json=request_payload)
    assert response.status_code == 400
    assert response.json()["code"] == ErrorCode.INVALID_INPUT


# Test predict endpoint with extra features
@patch("app.schemas.model.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_extra_feature():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0],
            "b": [2.0, 4.0],
            "c": [5.0, 6.0],  # Extra feature 'c'
        }
    }
    response = client.post("/app/v1/model/predict", json=request_payload)
    print(response.json())
    assert response.status_code == 400
    assert response.json()["code"] == ErrorCode.INVALID_INPUT


# Test model info endpoint - when ready
def test_model_info_endpoint():
    # Override auth and model dependencies
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    response = client.get("/app/v1/model/metadata")
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert response.json()["model_name"] == "test_model"


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
    predict_response = client.post("/app/v1/model/predict", json=request_payload)

    # Test metadata endpoint
    metadata_response = client.get("/app/v1/model/metadata")

    # All endpoints should require authentication
    assert predict_response.status_code in [401, 422]
    assert metadata_response.status_code in [
        401,
        422,
        403,
    ]  # 403 for admin-required endpoint
