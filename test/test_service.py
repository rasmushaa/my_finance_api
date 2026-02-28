from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from app.dependencies import get_model_store
from app.main import app

client = TestClient(app)


class DummyModel:
    def predict(self, df):
        print(['class_a'] * len(df))
        return ['class_a'] * len(df)

class DummyStore:
    champion_model = DummyModel()
    challenger_models = [DummyModel()]
    model_info = {'champion': {'version': '1'}, 'challengers': [{'version': '2'}]}

def override_store():
    return DummyStore()


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
    response = client.post("/predict", json=request_payload)
    assert response.status_code == 200
    assert response.json() == {"predictions": ['class_a', 'class_a']}

@patch("app.schemas.CANONICAL_FEATURES", ["a", "b"])
def test_predict_endpoint_missing_feature():
    request_payload = {
        "inputs": {
            "a": [1.0, 3.0]
            # Missing feature 'b'
        }
    }
    app.dependency_overrides[get_model_store] = override_store
    response = client.post("/predict", json=request_payload)
    assert response.status_code == 400
    assert "Missing required features" in response.json()["detail"]

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
    response = client.post("/predict", json=request_payload)
    assert response.status_code == 400
    assert "Unexpected features provided" in response.json()["detail"]


# Test model info endpoint
def test_model_info_endpoint():
    app.dependency_overrides[get_model_store] = override_store
    response = client.get("/model/info")
    assert response.status_code == 200
    assert response.json() == {'champion': {'version': '1'}, 'challengers': [{'version': '2'}]}