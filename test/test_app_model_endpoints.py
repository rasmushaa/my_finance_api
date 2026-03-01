from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.dependencies import get_model_store
from app.main import app
from app.model_store import ModelLoadingStatus
import pytest

client = TestClient(app)

# Clean up dependency overrides after each test
@pytest.fixture(autouse=True)
def cleanup():
    yield
    app.dependency_overrides.clear()


# Mock classes and functions for testing
class DummyModel:
    def predict(self, df):
        return ['class_a'] * len(df)

class DummyStore:
    def __init__(self, is_ready=True, status=ModelLoadingStatus.READY, error_message=None):
        self._model = DummyModel() if is_ready else None
        self._model_info = {"version": "1"} if is_ready else {}
        self._status = status
        self._error_message = error_message

    def predict(self, input_df):
        if not self.is_ready:
            raise ValueError("Model is not ready, prediction cannot be made")
        return self._model.predict(input_df)
    
    @property
    def metadata(self):
        if not self.is_ready:
            raise ValueError("Model is not ready, metadata not available")
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


# Dependency override functions
def override_store():
    return DummyStore()

def override_store_not_ready():
    return DummyStore(is_ready=False, status=ModelLoadingStatus.LOADING)


# Test health check endpoint
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# Test predict endpoint
@patch("app.schemas.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint():
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0],
            "b": [2.0, 4.0]
        }
    }
    app.dependency_overrides[get_model_store] = override_store
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 200
    assert response.json() == {"predictions": ['class_a', 'class_a']}


# Test predict endpoint with models not ready
@patch("app.schemas.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_model_not_ready():
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0],
            "b": [2.0, 4.0]
        }
    }
    app.dependency_overrides[get_model_store] = override_store_not_ready
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 503
    assert "still loading" in response.json()["detail"]


# Test predict endpoint with missing features
@patch("app.schemas.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_missing_feature():
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0]
            # Missing feature 'b'
        }
    }
    app.dependency_overrides[get_model_store] = override_store
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 400
    assert "Missing required features" in response.json()["detail"]


# Test predict endpoint with extra features
@patch("app.schemas.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_extra_feature():
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0],
            "b": [2.0, 4.0],
            "c": [5.0, 6.0]  # Extra feature 'c'
        }
    }
    app.dependency_overrides[get_model_store] = override_store
    response = client.post("/model/predict", json=request_payload)
    assert response.status_code == 400
    assert "Unexpected features provided" in response.json()["detail"]


# Test model info endpoint when models not ready
def test_model_info_endpoint_not_ready():
    app.dependency_overrides[get_model_store] = override_store_not_ready
    response = client.get("/model/metadata")
    assert response.status_code == 503
    assert "not available" in response.json()["detail"]


# Test model info endpoint - when ready
def test_model_info_endpoint():
    app.dependency_overrides[get_model_store] = override_store
    response = client.get("/model/metadata")
    assert response.status_code == 200
    assert response.json()["version"] == "1"


# Test model status endpoint - ready
def test_model_status_endpoint_ready():
    app.dependency_overrides[get_model_store] = override_store
    response = client.get("/model/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["is_ready"] is True


# Test model status endpoint - loading
def test_model_status_endpoint_loading():
    app.dependency_overrides[get_model_store] = override_store_not_ready
    response = client.get("/model/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "loading"
    assert data["is_ready"] is False
