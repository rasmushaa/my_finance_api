"""Tests for typed runtime settings."""

import pytest

from app.core.settings import BigQueryConfig, GoogleOAuthConfig, JWTConfig


def test_jwt_config_from_env_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_JWT_SECRET", "secret")
    monkeypatch.setenv("APP_JWT_EXP_DELTA_MINUTES", "60")

    config = JWTConfig.from_env()
    assert config.secret == "secret"
    assert config.token_expire_minutes == 60
    assert config.algorithm == "HS256"


def test_jwt_config_requires_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("APP_JWT_SECRET", raising=False)
    monkeypatch.setenv("APP_JWT_EXP_DELTA_MINUTES", "60")

    with pytest.raises(KeyError):
        JWTConfig.from_env()


def test_jwt_config_requires_integer_ttl(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_JWT_SECRET", "secret")
    monkeypatch.setenv("APP_JWT_EXP_DELTA_MINUTES", "not-an-int")

    with pytest.raises(ValueError):
        JWTConfig.from_env()


def test_google_oauth_config_defaults_token_uri(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.delenv("GOOGLE_OAUTH_TOKEN_URI", raising=False)

    config = GoogleOAuthConfig.from_env()
    assert config.token_uri == "https://oauth2.googleapis.com/token"


def test_google_oauth_config_requires_non_empty_client_id(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")

    with pytest.raises(ValueError):
        GoogleOAuthConfig.from_env()


def test_bigquery_config_builds_dataset_suffix(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("GCP_BQ_DATASET", "my_dataset")
    monkeypatch.setenv("GCP_LOCATION", "europe-north1")
    monkeypatch.setenv("GCP_BUCKET_NAME", "my-model-bucket")
    monkeypatch.setenv("ENV", "stg")

    config = BigQueryConfig.from_env()
    assert config.project_id == "my-project"
    assert config.location == "europe-north1"
    assert config.dataset == "my_dataset_stg"


def test_bigquery_config_defaults_env_to_dev(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("GCP_BQ_DATASET", "my_dataset")
    monkeypatch.setenv("GCP_LOCATION", "europe-north1")
    monkeypatch.setenv("GCP_BUCKET_NAME", "my-model-bucket")
    monkeypatch.delenv("ENV", raising=False)

    config = BigQueryConfig.from_env()
    assert config.dataset == "my_dataset_dev"
