"""Test health endpoint functionality and rate limiting."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Ensure clean dependency state for each test."""
    yield
    # Clean up after tests
    app.dependency_overrides.clear()


def test_health_endpoint_basic():
    """Test that health endpoint returns correct response."""
    client = TestClient(app)
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
