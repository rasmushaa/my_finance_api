"""Reusable fake services for endpoint and service tests."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.errors.auth import CodeExchangeError


class FakeGoogleOAuthService:
    """Fake Google OAuth service returning deterministic user info."""

    def __init__(
        self,
        user_info: dict[str, Any] | None = None,
        should_fail: bool = False,
        error: Exception | None = None,
    ):
        self.user_info = user_info or {
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }
        self.should_fail = should_fail
        self.error = error

    def exchange_code_for_id_token(
        self, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        if self.error:
            raise self.error
        if self.should_fail:
            raise CodeExchangeError()
        return self.user_info


class FakeJwtService:
    """Fake JWT service for endpoint tests."""

    def __init__(
        self,
        token: str = "mock-jwt-token-for-testing",
        error: Exception | None = None,
    ):
        self.token = token
        self.error = error
        self.calls: list[str] = []

    def authenticate(self, email: str) -> str:
        self.calls.append(email)
        if self.error:
            raise self.error
        return self.token


class FakeModelService:
    """Fake model service used by transaction/model endpoint tests."""

    def __init__(
        self,
        predictions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        error: Exception | None = None,
    ):
        self.predictions = predictions or ["Uncategorized"]
        self.error = error
        self._metadata = metadata or {
            "model_name": "test_model",
            "alias": "test_alias",
            "version": 1,
            "run_id": "test_run_123",
            "description": "Test model for unit tests",
            "package_version": "1.0.0",
            "commit_sha": "abc123def456",
            "model_features": "a,b,c",
            "model_architecture": "RandomForest",
        }

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata

    def predict(self, input_df: pd.DataFrame) -> list[str]:
        if self.error:
            raise self.error
        if len(self.predictions) == len(input_df):
            return self.predictions
        return [self.predictions[0]] * len(input_df)
