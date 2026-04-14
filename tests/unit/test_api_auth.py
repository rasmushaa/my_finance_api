"""Test auth endpoint functionality and email-based rate limiting."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_google_oauth_service, get_jwt_service
from app.core.errors.auth import UserNotFoundError
from app.core.errors.base_error import ErrorCode
from app.main import app
from tests.helpers.fake_services import FakeGoogleOAuthService, FakeJwtService


# ------------------ Mock Dependency Overrides ------------------
def override_google_oauth_service():
    return FakeGoogleOAuthService()


def override_google_oauth_service_failing():
    return FakeGoogleOAuthService(should_fail=True)


def override_jwt_service():
    return FakeJwtService()


VALID_AUTH_PAYLOAD = {"code": "mock-google-code", "redirect_uri": "http://localhost"}


# -------------------------- Tests --------------------------
def test_auth_google_code_success():
    """Test successful Google code exchange returns JWT token and user info."""
    app.dependency_overrides[get_google_oauth_service] = override_google_oauth_service
    app.dependency_overrides[get_jwt_service] = override_jwt_service

    client = TestClient(app)
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["encoded_jwt_token"] == "mock-jwt-token-for-testing"
    assert data["user_name"] == "Test User"
    assert data["user_picture_url"] == "https://example.com/photo.jpg"
    assert data["user_role"] == "user"


def test_auth_google_code_exchange_failure_returns_401():
    """Test that a Google OAuth failure returns generic 401 error."""
    app.dependency_overrides[get_google_oauth_service] = (
        override_google_oauth_service_failing
    )
    app.dependency_overrides[get_jwt_service] = override_jwt_service

    client = TestClient(app)
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)

    assert response.status_code == 401
    assert response.json()["code"] == ErrorCode.INVALID_TOKEN


def test_auth_google_code_user_not_found_returns_404():
    """If JWT auth cannot map email to a user, endpoint should return 404."""
    app.dependency_overrides[get_google_oauth_service] = override_google_oauth_service
    app.dependency_overrides[get_jwt_service] = lambda: FakeJwtService(
        error=UserNotFoundError()
    )

    client = TestClient(app)
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)

    assert response.status_code == 404
    assert response.json()["code"] == ErrorCode.UNAUTHORIZED.value


def test_auth_google_code_invalid_payload_returns_422():
    """Pydantic request validation should reject missing redirect_uri."""
    app.dependency_overrides[get_google_oauth_service] = override_google_oauth_service
    app.dependency_overrides[get_jwt_service] = override_jwt_service

    client = TestClient(app)
    response = client.post("/app/v1/auth/google/code", json={"code": "only-code"})

    assert response.status_code == 422


def test_auth_rate_limit_blocks_after_exceeded():
    """Test that the 6th request from the same email gets rate limited (429)."""
    app.dependency_overrides[get_google_oauth_service] = override_google_oauth_service
    app.dependency_overrides[get_jwt_service] = override_jwt_service

    client = TestClient(app)

    for i in range(1):
        response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
        assert (
            response.status_code == 200
        ), f"The {i+1} auth calls request should succeed"

    # 6th request should be rate limited
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
    assert response.status_code == 429, "The extra auth call should be rate limited"
    data = response.json()
    assert data["code"] == ErrorCode.RATE_LIMIT_EXCEEDED.value
    assert "cooldown_seconds" in data["details"]


def test_auth_rate_limit_blocks_before_jwt_authentication():
    """The rate-limited request should not call JWT minting."""
    jwt_service = FakeJwtService()
    app.dependency_overrides[get_google_oauth_service] = override_google_oauth_service
    app.dependency_overrides[get_jwt_service] = lambda: jwt_service

    client = TestClient(app)
    first = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
    second = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 429
    assert len(jwt_service.calls) == 1


def test_auth_rate_limit_is_per_email():
    """Test that rate limiting is scoped per email, not global."""
    user_a_info = {
        "email": "user_a@example.com",
        "name": "User A",
        "picture": "",
    }
    user_b_info = {
        "email": "user_b@example.com",
        "name": "User B",
        "picture": "",
    }

    app.dependency_overrides[get_jwt_service] = override_jwt_service
    client = TestClient(app)

    # Exhaust rate limit for user A
    app.dependency_overrides[get_google_oauth_service] = lambda: FakeGoogleOAuthService(
        user_info=user_a_info
    )
    for i in range(1):
        response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
        assert response.status_code == 200, f"User A's {i+1} auth calls should succeed"

    # User A is now rate limited
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
    assert (
        response.status_code == 429
    ), "User A should be rate limited after exceeding limit"

    # User B should still be allowed (different email key)
    app.dependency_overrides[get_google_oauth_service] = lambda: FakeGoogleOAuthService(
        user_info=user_b_info
    )
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
    assert (
        response.status_code == 200
    ), "User B should not be affected by User A's rate limit"


def test_auth_rate_limit_resets_after_window(monkeypatch):
    """Test that rate limit resets after the time window expires."""

    import app.core.rate_limiter as rl_module

    # Use a controllable clock for time.monotonic
    fake_time = [100.0]
    monkeypatch.setattr(
        rl_module,
        "time",
        type(
            "FakeTime",
            (),
            {
                "monotonic": staticmethod(lambda: fake_time[0]),
            },
        )(),
    )

    app.dependency_overrides[get_google_oauth_service] = override_google_oauth_service
    app.dependency_overrides[get_jwt_service] = override_jwt_service

    client = TestClient(app)

    # Exhaust rate limit
    for i in range(1):
        response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
        assert (
            response.status_code == 200
        ), f"The {i+1} auth calls request should succeed"

    # Should be blocked
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
    assert response.status_code == 429, "The extra auth call should be rate limited"

    # Advance time past the window (300 seconds)
    fake_time[0] = 100.0 + 301.0

    # Should be allowed again
    response = client.post("/app/v1/auth/google/code", json=VALID_AUTH_PAYLOAD)
    assert (
        response.status_code == 200
    ), "The auth call should succeed after the rate limit window resets"
