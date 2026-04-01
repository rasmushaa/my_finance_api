"""Typed runtime configuration loaded from environment variables.

This module defines dataclasses for different configuration sections (e.g. JWT, Google
OAuth, BigQuery) and helper functions to load these settings from environment variables.
The settings are designed to be immutable and provide clear error messages if required
environment variables are missing or invalid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# -- Helpers for vars --------------------------------------------------
def _required_env(name: str) -> str:
    """Return a required env var or raise a clear error."""
    value = os.getenv(name)
    if value is None:
        raise KeyError(name)
    if value == "":
        raise ValueError(f"{name} must not be empty")
    return value


def _int_env(name: str) -> int:
    raw = _required_env(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


# -- Settings --------------------------------------------------
@dataclass(frozen=True)
class JWTConfig:
    """JWT runtime settings.

    Attributes
    ----------
    secret: str
        The main internal sectret used for signing JWTs. Must be kept secure and not shared.
    token_expire_minutes: int
        How long JWT tokens issued by the app should be valid, in minutes.
    algorithm: str
        The signing algorithm to use for JWTs. Defaults to "HS256".
    """

    secret: str
    token_expire_minutes: int
    algorithm: str = "HS256"

    @classmethod
    def from_env(cls) -> JWTConfig:
        return cls(
            secret=_required_env("APP_JWT_SECRET"),
            token_expire_minutes=_int_env("APP_JWT_EXP_DELTA_MINUTES"),
        )


@dataclass(frozen=True)
class GoogleOAuthConfig:
    """Google OAuth runtime settings.

    Attributes
    ----------
    client_id: str
        The client ID for Google OAuth.
    client_secret: str
        The client secret for Google OAuth.
    token_uri: str
        The token URI for Google OAuth. Defaults to "https://oauth2.googleapis.com/token".
    """

    client_id: str
    client_secret: str
    token_uri: str = "https://oauth2.googleapis.com/token"

    @classmethod
    def from_env(cls) -> GoogleOAuthConfig:
        return cls(
            client_id=_required_env("GOOGLE_OAUTH_CLIENT_ID"),
            client_secret=_required_env("GOOGLE_OAUTH_CLIENT_SECRET"),
            token_uri=os.getenv("GOOGLE_OAUTH_TOKEN_URI")
            or "https://oauth2.googleapis.com/token",
        )


@dataclass(frozen=True)
class BigQueryConfig:
    """BigQuery runtime settings.

    Attributes
    ----------
    project_id: str | None
        The GCP project ID for BigQuery. Can be None if not set.
    dataset_base: str
        The base name for the BigQuery dataset.
    location: str | None
        The location for the BigQuery dataset. Can be None if not set.
    environment: str
        The environment suffix for the dataset. Defaults to "dev".
    """

    project_id: str | None
    dataset_base: str
    location: str | None
    environment: str = "dev"

    @property
    def dataset(self) -> str:
        """Dataset name suffixed by environment."""
        return f"{self.dataset_base}_{self.environment}"

    @classmethod
    def from_env(cls) -> BigQueryConfig:
        return cls(
            project_id=os.getenv("GCP_PROJECT_ID"),
            dataset_base=_required_env("GCP_BQ_DATASET"),
            location=os.getenv("GCP_LOCATION"),
            environment=os.getenv("ENV") or "dev",
        )
