"""Shared pytest fixtures for stable test setup across the suite."""

import pytest

TEST_JWT_SECRET = "test-secret-key-for-jwt-testing"
TEST_JWT_EXP_DELTA_MINUTES = "60"


@pytest.fixture(autouse=True)
def default_test_env(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """Set baseline env vars for non-integration tests.

    Integration tests manage their own environment and credentials.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return

    monkeypatch.setenv("APP_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_JWT_EXP_DELTA_MINUTES", TEST_JWT_EXP_DELTA_MINUTES)
    yield


@pytest.fixture(autouse=True)
def reset_fastapi_state():
    """Ensure FastAPI dependency overrides and auth limiter state do not leak."""
    yield

    from app.main import app

    app.dependency_overrides.clear()

    # Auth tests mutate this limiter directly through endpoint calls.
    from app.api.routers.auth import _auth_limiter

    _auth_limiter._requests.clear()
