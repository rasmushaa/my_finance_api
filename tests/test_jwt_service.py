"""Test JWT service functionality and security features."""

import os
import time
from unittest.mock import patch

import pytest
from jose import jwt

# Set environment variables BEFORE importing JWT service
os.environ["APP_JWT_SECRET"] = "test-secret-key-for-jwt-testing"
os.environ["APP_JWT_EXP_DELTA_MINUTES"] = "60"

from app.core.exceptions.auth import UserNotFoundError
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
    assert service._AppJwtService__secret_key == "test-secret-key-for-jwt-testing"
    assert service._AppJwtService__algorithm == "HS256"
    assert service._AppJwtService__token_expire_minutes == 60


# Authentication Tests
@pytest.mark.asyncio
async def test_successful_authentication_user_role(jwt_service):
    """Test successful authentication for user role."""
    token = await jwt_service.auth_with_delay("user@example.com")

    # Verify token is a string
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify token payload
    payload = jwt.decode(
        token,
        "test-secret-key-for-jwt-testing",
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


@pytest.mark.asyncio
async def test_successful_authentication_admin_role(jwt_service):
    """Test successful authentication for admin role."""
    token = await jwt_service.auth_with_delay("admin@example.com")

    payload = jwt.decode(
        token,
        "test-secret-key-for-jwt-testing",
        algorithms=["HS256"],
        audience="my-finance-api-users",
        issuer="my-finance-api",
    )

    assert payload["sub"] == "admin@example.com"
    assert payload["role"] == "admin"


@pytest.mark.asyncio
async def test_token_expiration_time(jwt_service):
    """Test JWT token has correct expiration time."""
    start_time = int(time.time())
    token = await jwt_service.auth_with_delay("user@example.com")

    payload = jwt.decode(
        token,
        "test-secret-key-for-jwt-testing",
        algorithms=["HS256"],
        audience="my-finance-api-users",
        issuer="my-finance-api",
    )

    # Verify expiration is approximately 60 minutes (3600 seconds) from now
    exp_time = payload["exp"]
    iat_time = payload["iat"]

    assert exp_time - iat_time == 3600  # 60 minutes * 60 seconds
    assert iat_time >= start_time
    assert iat_time <= int(time.time()) + 1  # Allow 1 second tolerance


# Security Features Tests
@pytest.mark.asyncio
async def test_user_not_found_raises_exception(empty_user_client):
    """Test authentication fails for non-existent user."""
    service = AppJwtService(empty_user_client)

    with pytest.raises(UserNotFoundError):
        await service.auth_with_delay("nonexistent@example.com")


@pytest.mark.asyncio
async def test_timing_attack_protection_delay(empty_user_client):
    """Test that authentication failure includes timing protection delay."""
    service = AppJwtService(empty_user_client)

    # Mock numpy.random.uniform to return predictable delay
    with patch("app.services.jwt.np.random.uniform", return_value=1.0):
        with patch("app.services.jwt.asyncio.sleep") as mock_sleep:

            with pytest.raises(UserNotFoundError):
                await service.auth_with_delay("nonexistent@example.com")

            # Verify sleep was called with the mocked delay
            mock_sleep.assert_called_once_with(1.0)


@pytest.mark.asyncio
async def test_no_delay_for_existing_user(jwt_service):
    """Test no timing delay for successful authentication."""
    start_time = time.time()

    await jwt_service.auth_with_delay("user@example.com")

    elapsed_time = time.time() - start_time

    # Should complete quickly (under 1 second)
    assert elapsed_time < 1.0
