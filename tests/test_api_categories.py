"""Test FastAPI categories endpoints using DI container pattern."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.providers import get_categories_service, get_require_user
from app.main import app
from app.services.categories import CategoriesService


# --------------- Mock Database Client and Service for Testing ----------------
class MockDatabaseClient:
    """Mock database client that mimics the real database interface."""

    def __init__(self, dataset: str = "test_dataset"):
        self.dataset = dataset
        self._sql_responses: dict[str, pd.DataFrame] = {}

    def sql_to_pandas(self, sql: str) -> pd.DataFrame:
        """Mock SQL execution that returns predefined DataFrames."""
        # Simple pattern matching for different query types
        if "Type = 'transaction'" in sql:
            return self._sql_responses.get("expenditure", pd.DataFrame({"Name": []}))
        elif "Type = 'asset'" in sql:
            return self._sql_responses.get("asset", pd.DataFrame({"Name": []}))
        else:
            return pd.DataFrame({"Name": []})

    def set_response(self, query_type: str, response_df: pd.DataFrame):
        """Configure mock response for specific query type."""
        self._sql_responses[query_type] = response_df


class MockCategoriesService:
    """Mock categories service that implements the same interface as the real
    service."""

    def __init__(self, expenditure_categories=None, asset_categories=None):
        self.expenditure_categories = (
            expenditure_categories
            if expenditure_categories is not None
            else ["Food", "Transport"]
        )
        self.asset_categories = (
            asset_categories if asset_categories is not None else ["Stocks", "Bonds"]
        )

    def get_expenditure_categories(self) -> list[str]:
        return self.expenditure_categories

    def get_asset_categories(self) -> list[str]:
        return self.asset_categories


# ------------------ Mock Dependency Overrides ------------------
def override_categories_service():
    return MockCategoriesService()


def override_categories_service_empty():
    return MockCategoriesService(expenditure_categories=[], asset_categories=[])


def override_categories_service_custom():
    return MockCategoriesService(
        expenditure_categories=["Food", "Transport", "Entertainment"],
        asset_categories=["Stocks", "Bonds", "Real Estate"],
    )


def mock_require_user():
    return {"user_id": "test_user", "username": "testuser"}


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Ensure clean dependency state for each test."""
    yield
    # Clean up after tests
    app.dependency_overrides.clear()


# -------------------------- Tests --------------------------
def test_get_expenditure_categories_endpoint():
    """Test the expenditure categories API endpoint with mocked service."""
    # Override auth and service dependencies
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_categories_service] = override_categories_service

    client = TestClient(app)
    response = client.get("/data/categories/expenditures")
    print(response.json())
    assert response.status_code == 200
    assert response.json() == {"categories": ["Food", "Transport"]}


def test_get_asset_categories_endpoint():
    """Test the asset categories API endpoint with mocked service."""
    # Override dependencies
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_categories_service] = override_categories_service

    client = TestClient(app)
    response = client.get("/data/categories/assets")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data == {"categories": ["Stocks", "Bonds"]}


def test_expenditure_categories_empty_response():
    """Test expenditure categories endpoint when service returns empty list."""
    # Override dependencies
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_categories_service] = override_categories_service_empty

    client = TestClient(app)
    response = client.get("/data/categories/expenditures")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data == {"categories": []}


def test_asset_categories_empty_response():
    """Test asset categories endpoint when service returns empty list."""
    # Override dependencies
    app.dependency_overrides[get_require_user] = mock_require_user
    app.dependency_overrides[get_categories_service] = override_categories_service_empty

    client = TestClient(app)
    response = client.get("/data/categories/assets")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data == {"categories": []}


def test_categories_endpoints_unauthorized():
    """Test that endpoints require authentication."""
    # Don't override auth dependency - should fail
    app.dependency_overrides.clear()
    app.dependency_overrides[get_categories_service] = override_categories_service

    client = TestClient(app)

    # Both endpoints should require authentication
    expenditure_response = client.get("/data/categories/expenditures")
    asset_response = client.get("/data/categories/assets")

    # Should return 401 or 422 depending on auth implementation
    assert expenditure_response.status_code in [401, 422]
    assert asset_response.status_code in [401, 422]


# -------------------------- Integration Tests with Mock Database --------------------------
def test_categories_service_with_mock_database():
    """Test CategoriesService directly with mock database client."""
    # Create mock database client
    mock_db = MockDatabaseClient()

    # Configure responses
    expenditure_df = pd.DataFrame({"Name": ["Food", "Transport", "Shopping"]})
    asset_df = pd.DataFrame({"Name": ["Stocks", "Crypto", "Bonds"]})

    mock_db.set_response("expenditure", expenditure_df)
    mock_db.set_response("asset", asset_df)

    # Create service with mock database
    service = CategoriesService(db_client=mock_db)

    # Test service methods
    expenditure_cats = service.get_expenditure_categories()
    asset_cats = service.get_asset_categories()

    assert expenditure_cats == ["Food", "Transport", "Shopping"]
    assert asset_cats == ["Stocks", "Crypto", "Bonds"]
    assert mock_db.dataset == "test_dataset"
