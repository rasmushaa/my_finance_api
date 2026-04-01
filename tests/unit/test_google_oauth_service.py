"""Unit tests for GoogleOAuthService behavior and edge cases."""

from unittest.mock import Mock, patch

import pytest

from app.core.errors.auth import (
    CodeExchangeError,
    InvalidIdTokenError,
    MissingEmailError,
    MissingIdTokenError,
)
from app.services.google_oauth import GoogleOAuthService


def make_response(status_code: int, payload: dict) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


@pytest.fixture
def oauth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")


def test_google_oauth_init_requires_client_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "secret")

    with pytest.raises(KeyError):
        GoogleOAuthService()


def test_google_oauth_init_rejects_empty_client_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "secret")

    with pytest.raises(ValueError):
        GoogleOAuthService()


@patch("app.services.google_oauth.google_id_token.verify_oauth2_token")
@patch("app.services.google_oauth.requests.post")
def test_exchange_code_success(mock_post: Mock, mock_verify: Mock, oauth_env):
    mock_post.return_value = make_response(
        200, {"id_token": "signed-google-id-token-value"}
    )
    mock_verify.return_value = {
        "iss": "https://accounts.google.com",
        "email": "user@example.com",
        "name": "Test User",
    }

    service = GoogleOAuthService()
    info = service.exchange_code_for_id_token(
        code="auth-code",
        redirect_uri="http://localhost/callback",
    )

    assert info["email"] == "user@example.com"
    mock_post.assert_called_once_with(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "code": "auth-code",
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost/callback",
        },
        timeout=15,
    )
    assert mock_verify.call_count == 1
    assert mock_verify.call_args.args[0] == "signed-google-id-token-value"
    assert mock_verify.call_args.args[2] == "test-client-id"


@patch("app.services.google_oauth.google_id_token.verify_oauth2_token")
@patch("app.services.google_oauth.requests.post")
def test_exchange_code_uses_custom_token_uri(
    mock_post: Mock, mock_verify: Mock, oauth_env, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_URI", "https://custom.example/token")
    mock_post.return_value = make_response(200, {"id_token": "id-token"})
    mock_verify.return_value = {
        "iss": "accounts.google.com",
        "email": "user@example.com",
    }

    service = GoogleOAuthService()
    service.exchange_code_for_id_token("auth-code", "http://localhost/callback")

    assert mock_post.call_args.args[0] == "https://custom.example/token"


@patch("app.services.google_oauth.requests.post")
def test_exchange_code_non_200_raises_code_exchange_error(mock_post: Mock, oauth_env):
    mock_post.return_value = make_response(400, {"error": "invalid_grant"})
    service = GoogleOAuthService()

    with pytest.raises(CodeExchangeError):
        service.exchange_code_for_id_token("bad-code", "http://localhost/callback")


@patch("app.services.google_oauth.requests.post")
def test_exchange_code_missing_id_token_raises_missing_id_token_error(
    mock_post: Mock, oauth_env
):
    mock_post.return_value = make_response(200, {"access_token": "only-access-token"})
    service = GoogleOAuthService()

    with pytest.raises(MissingIdTokenError):
        service.exchange_code_for_id_token("auth-code", "http://localhost/callback")


@patch("app.services.google_oauth.google_id_token.verify_oauth2_token")
@patch("app.services.google_oauth.requests.post")
def test_exchange_code_invalid_issuer_raises_invalid_id_token_error(
    mock_post: Mock, mock_verify: Mock, oauth_env
):
    mock_post.return_value = make_response(200, {"id_token": "id-token"})
    mock_verify.return_value = {
        "iss": "https://malicious-issuer.example",
        "email": "user@example.com",
    }
    service = GoogleOAuthService()

    with pytest.raises(InvalidIdTokenError):
        service.exchange_code_for_id_token("auth-code", "http://localhost/callback")


@patch("app.services.google_oauth.google_id_token.verify_oauth2_token")
@patch("app.services.google_oauth.requests.post")
def test_exchange_code_missing_email_raises_missing_email_error(
    mock_post: Mock, mock_verify: Mock, oauth_env
):
    mock_post.return_value = make_response(200, {"id_token": "id-token"})
    mock_verify.return_value = {
        "iss": "https://accounts.google.com",
        # no email
    }
    service = GoogleOAuthService()

    with pytest.raises(MissingEmailError):
        service.exchange_code_for_id_token("auth-code", "http://localhost/callback")
