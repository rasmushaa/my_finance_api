"""Google OAuth service for handling authentication dependencies."""

import logging
import os
from typing import Any, Dict

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.exceptions.auth import (
    CodeExchangeError,
    InvalidIdTokenError,
    MissingEmailError,
    MissingIdTokenError,
)

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Service for handling Google OAuth operations."""

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        token_uri: str = None,
    ):
        """Initialize Google OAuth service.

        Parameters
        ----------
        client_id : str
            Google OAuth client ID (from environment if not provided)
        client_secret : str
            Google OAuth client secret (from environment if not provided)
        token_uri : str
            Google token exchange URI (from environment if not provided)
        """

        # OAuth configuration from environment variables or parameters
        self.client_id = client_id or os.environ.get("GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("GOOGLE_CLIENT_SECRET")
        self.token_uri = token_uri or os.environ.get(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        )

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Google OAuth client ID and secret must be provided via environment variables or parameters"
            )

        if not self.client_secret:
            raise ValueError(
                "Google OAuth client secret must be provided via environment variables or parameters"
            )

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
            logger.error(f"Google token exchange failed")
            raise CodeExchangeError()

        if "id_token" not in response.json():
            logger.error(f"Google token exchange response missing id_token")
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
            logger.error(f"Invalid token issuer: {info.get('iss')}")
            raise InvalidIdTokenError()

        if not info.get("email"):
            logger.error(f"Google ID token missing email")
            raise MissingEmailError()

        return info
