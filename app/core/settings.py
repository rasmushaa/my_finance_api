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
    """Return required env var parsed as integer."""
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
    secret : str
        Secret key used to sign and verify application JWTs.
    token_expire_minutes: int
        Token TTL in minutes.
    algorithm: str
        Signing algorithm used for JWTs. Defaults to ``"HS256"``.
    """

    secret: str
    token_expire_minutes: int
    algorithm: str = "HS256"

    @classmethod
    def from_env(cls) -> JWTConfig:
        """Load JWT configuration from environment variables."""
        return cls(
            secret=_required_env("APP_JWT_SECRET"),
            token_expire_minutes=_int_env("APP_JWT_EXP_DELTA_MINUTES"),
        )


@dataclass(frozen=True)
class GoogleOAuthConfig:
    """Google OAuth runtime settings.

    Attributes
    ----------
    client_id : str
        The client ID for Google OAuth.
    client_secret : str
        The client secret for Google OAuth.
    token_uri : str
        OAuth token exchange endpoint.
    """

    client_id: str
    client_secret: str
    token_uri: str = "https://oauth2.googleapis.com/token"

    @classmethod
    def from_env(cls) -> GoogleOAuthConfig:
        """Load Google OAuth configuration from environment variables."""
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
    project_id : str
        Google Cloud project ID used for BigQuery and GCS clients.
    dataset_base : str
        Base dataset name without environment suffix.
    location : str
        BigQuery location (for example ``"europe-north1"``).
    bucket_name : str
        GCS bucket name used for model artifacts and manifest loading.
    environment : str
        Environment suffix used for dataset partitioning. Defaults to ``"dev"``.
    """

    project_id: str
    dataset_base: str
    location: str
    bucket_name: str
    environment: str = "dev"

    @property
    def dataset(self) -> str:
        """Dataset name suffixed by environment."""
        return f"{self.dataset_base}_{self.environment}"

    @classmethod
    def from_env(cls) -> BigQueryConfig:
        """Load BigQuery + GCS runtime configuration from environment variables."""
        return cls(
            project_id=_required_env("GCP_PROJECT_ID"),
            dataset_base=_required_env("GCP_BQ_DATASET"),
            location=_required_env("GCP_LOCATION"),
            environment=os.getenv("ENV", "dev"),
            bucket_name=_required_env("GCP_BUCKET_NAME"),
        )


# -- Model Artifactory settings --------------------------------------------------
@dataclass(frozen=True)
class ModelArtifactoryConfig:
    """Model Artifactory runtime settings.

    Attributes
    ----------
    gcs_bucket_name : str
        GCS bucket where model artifacts and manifest are stored.
    mlflow_tracking_uri : str
        MLflow tracking server URI.
    """

    gcs_bucket_name: str
    mlflow_tracking_uri: str
    model_name: str = "BankingModel"

    @classmethod
    def from_env(cls) -> ModelArtifactoryConfig:
        """Load model-artifact tooling configuration from environment variables."""
        return cls(
            gcs_bucket_name=_required_env("GCP_BUCKET_NAME"),
            mlflow_tracking_uri=_required_env("MLFLOW_TRACKING_URI"),
        )
