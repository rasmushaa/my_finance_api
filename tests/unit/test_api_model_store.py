from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_model_store, get_require_admin
from app.main import app
from tests.helpers.fake_services import FakeModelService


# --- Mock Dependency Overrides for Authentication and Model Store ------------------
def override_store():
    return FakeModelService(predictions=["class_a"])


# -- Endpoints Tests ----------------------------------------
def test_model_info_endpoint():
    """Mock values are unmeaningful, but we can test that the endpoint pydantic
    validation and response structure works."""
    # Override auth and model dependencies
    app.dependency_overrides[get_require_admin] = lambda: {"user_id": "test_user"}
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)
    response = client.get("/app/v1/model/metadata")
    assert response.status_code == 200
    assert response.json()["prod"]["version"] == 1
    assert response.json()["prod"]["aliases"] == ["prod"]
    assert response.json()["prod"]["commit_head_sha"] == "abc123def456head"
    assert response.json()["stg"]["version"] == 2
    assert response.json()["stg"]["aliases"] == ["stg"]
    assert response.json()["stg"]["commit_head_sha"] == "def456abc789head"


# -- Auth and Authorization Tests ----------------------------------------
@patch("app.services.model.CANONICAL_FEATURES", ["a", "b"])
def test_model_endpoints_unauthorized():
    """Test that model endpoints require authentication."""
    # Don't override auth dependencies - should fail
    app.dependency_overrides.clear()
    app.dependency_overrides[get_model_store] = override_store

    client = TestClient(app)

    # Test metadata endpoint
    metadata_response = client.get("/app/v1/model/metadata")
    assert metadata_response.status_code in [
        401,
    ]
