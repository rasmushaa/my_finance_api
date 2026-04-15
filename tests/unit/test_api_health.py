"""Test health endpoint functionality and rate limiting."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_basic():
    """Test that health endpoint returns correct response."""
    client = TestClient(app)
    response = client.get("/app/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
