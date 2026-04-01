"""Google OAuth service for handling authentication dependencies."""

import logging
from typing import Any, Dict

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.errors.auth import (
    CodeExchangeError,
    InvalidIdTokenError,
    MissingEmailError,
    MissingIdTokenError,
)
from app.core.settings import GoogleOAuthConfig

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Service for handling Google OAuth operations."""

    def __init__(self, config: GoogleOAuthConfig | None = None):
        """Initialize Google OAuth service."""

        oauth_config = config or GoogleOAuthConfig.from_env()
        self.client_id = oauth_config.client_id
        self.client_secret = oauth_config.client_secret
        self.token_uri = oauth_config.token_uri

    def exchange_code_for_id_token(
        self, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for Google user info.

        The Google code is exchanged for an ID token,
        which is then verified and decoded to extract user information.

        Parameters
        ----------
        code : str
            Authorization code from Google OAuth flow
        redirect_uri : str
            Redirect URI used in the OAuth flow

        Returns
        -------
        Dict[str, Any]
            User information extracted from the ID token, including email and other claims
        """

        # Exhange and get id_token from Google OAuth token endpoint
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        response = requests.post(self.token_uri, data=data, timeout=15)

        if response.status_code != 200:
            logger.debug(f"Google token exchange failed")
            raise CodeExchangeError()

        if "id_token" not in response.json():
            logger.debug(f"Google token exchange response missing id_token")
            raise MissingIdTokenError()

        id_token = response.json()["id_token"]

        # Decode and verify the ID token to extract user info
        info = google_id_token.verify_oauth2_token(
            id_token, google_requests.Request(), self.client_id
        )

        if info.get("iss") not in (
            "accounts.google.com",
            "https://accounts.google.com",
        ):
            logger.debug(f"Invalid token issuer: {info.get('iss')}")
            raise InvalidIdTokenError()

        if not info.get("email"):
            logger.debug(f"Google ID token missing email")
            raise MissingEmailError()

        return info
