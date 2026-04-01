"""Test JWT service functionality and security features."""

import os
import time

import pytest
from jose import jwt

# Set test environment variables BEFORE importing JWT service
os.environ["APP_JWT_SECRET"] = "test-secret-key-for-jwt-testing"
os.environ["APP_JWT_EXP_DELTA_MINUTES"] = "60"

# Test constants matching the environment variables above
JWT_TEST_SECRET = "test-secret-key-for-jwt-testing"
JWT_EXP_MINUTES = 60

from app.core.errors.auth import UserNotFoundError
from app.services.jwt import AppJwtService


class MockUserClient:
    """Mock user client for testing JWT service."""

    def __init__(self, users_db=None):
        self.users_db = users_db or {}

    def get_user_by_email(self, email: str) -> dict:
        """Mock implementation of user lookup."""
        return self.users_db.get(email)


@pytest.fixture
def mock_user_client():
    """Fixture providing a mock user client with test users."""
    users = {
        "user@example.com": {"role": "user", "id": "1"},
        "admin@example.com": {"role": "admin", "id": "2"},
    }
    return MockUserClient(users)


@pytest.fixture
def empty_user_client():
    """Fixture providing an empty user client (no users)."""
    return MockUserClient({})


@pytest.fixture
def jwt_service(mock_user_client):
    """Fixture providing a JWT service with mock user client."""
    return AppJwtService(mock_user_client)


# Initialization Tests
def test_initialization_with_user_client(mock_user_client):
    """Test JWT service initializes correctly with user client."""
    service = AppJwtService(mock_user_client)

    assert service.user_client == mock_user_client
    assert service.config.secret == JWT_TEST_SECRET
    assert service.config.algorithm == "HS256"
    assert service.config.token_expire_minutes == JWT_EXP_MINUTES


# Authentication Tests
def test_successful_authentication_user_role(jwt_service):
    """Test successful authentication for user role."""
    token = jwt_service.authenticate("user@example.com")

    # Verify token is a string
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify token payload
    payload = jwt.decode(
        token,
        JWT_TEST_SECRET,
        algorithms=["HS256"],
        audience="my-finance-api-users",
        issuer="my-finance-api",
    )

    assert payload["sub"] == "user@example.com"
    assert payload["role"] == "user"
    assert payload["iss"] == "my-finance-api"
    assert payload["aud"] == "my-finance-api-users"
    assert "iat" in payload
    assert "exp" in payload


def test_successful_authentication_admin_role(jwt_service):
    """Test successful authentication for admin role."""
    token = jwt_service.authenticate("admin@example.com")

    payload = jwt.decode(
        token,
        JWT_TEST_SECRET,
        algorithms=["HS256"],
        audience="my-finance-api-users",
        issuer="my-finance-api",
    )

    assert payload["sub"] == "admin@example.com"
    assert payload["role"] == "admin"


def test_token_expiration_time(jwt_service):
    """Test JWT token has correct expiration time."""
    start_time = int(time.time())
    token = jwt_service.authenticate("user@example.com")

    payload = jwt.decode(
        token,
        JWT_TEST_SECRET,
        algorithms=["HS256"],
        audience="my-finance-api-users",
        issuer="my-finance-api",
    )

    # Verify expiration is correct number of minutes from now
    exp_time = payload["exp"]
    iat_time = payload["iat"]
    expected_duration = JWT_EXP_MINUTES * 60  # Convert minutes to seconds

    assert exp_time - iat_time == expected_duration
    assert iat_time >= start_time
    assert iat_time <= int(time.time()) + 1  # Allow 1 second tolerance


# Security Features Tests
def test_user_not_found_raises_exception(empty_user_client):
    """Test authentication fails for non-existent user."""
    service = AppJwtService(empty_user_client)

    with pytest.raises(UserNotFoundError):
        service.authenticate("nonexistent@example.com")
