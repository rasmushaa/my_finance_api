"""Reusable fake services for endpoint and service tests."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.errors.auth import CodeExchangeError


# -- Google OAuth ----------------------------------------
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


# -- JWT Token ----------------------------------------
class FakeJwtService:
    """Fake JWT service for endpoint tests."""

    def __init__(
        self,
        token: str = "mock-jwt-token-for-testing",
        error: Exception | None = None,
        role: str = "user",
    ):
        self.token = token
        self.error = error
        self.role = role
        self.calls: list[str] = []

    def authenticate(self, email: str) -> tuple[str, str]:
        self.calls.append(email)
        if self.error:
            raise self.error
        return self.token, self.role


# -- Model ----------------------------------------
class FakeModelObject:
    """Fake ModelObject - mimics app.services.model.ModelObject for tests."""

    def __init__(
        self,
        predictions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        error: Exception | None = None,
    ):
        self._predictions = predictions or ["Uncategorized"]
        self._metadata = metadata or {}
        self._error = error

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata

    def predict(self, input_df: pd.DataFrame) -> list[str]:
        if self._error:
            raise self._error
        if len(self._predictions) == len(input_df):
            return self._predictions
        return [self._predictions[0]] * len(input_df)


_DEFAULT_PROD_METADATA: dict[str, Any] = {
    "model_name": "test_model",
    "aliases": ["prod"],
    "version": 1,
    "run_id": "test_run_123",
    "description": "Test model for unit tests",
    "package_version": "1.0.0",
    "commit_sha": "abc123def456",
    "commit_head_sha": "abc123def456head",
    "model_features": "a,b,c",
    "model_architecture": "RandomForest",
}

_DEFAULT_STG_METADATA: dict[str, Any] = {
    "model_name": "test_model",
    "aliases": ["stg"],
    "version": 2,
    "run_id": "test_run_456",
    "description": "Test staging model for unit tests",
    "package_version": "1.0.0",
    "commit_sha": "def456abc789",
    "commit_head_sha": "def456abc789head",
    "model_features": "a,b,c",
    "model_architecture": "RandomForest",
}


class FakeModelService:
    """Fake model service used by transaction/model endpoint tests.

    Mirrors the prod/stg environment structure of ModelService.
    """

    def __init__(
        self,
        predictions: list[str] | None = None,
        prod_metadata: dict[str, Any] | None = None,
        stg_metadata: dict[str, Any] | None = None,
    ):
        self._predictions = predictions or ["Uncategorized"]
        self._prod_metadata = prod_metadata or _DEFAULT_PROD_METADATA
        self._stg_metadata = stg_metadata or _DEFAULT_STG_METADATA
        self._champion = FakeModelObject(
            predictions=self._predictions,
            metadata=self._prod_metadata,
        )
        self._challengers = [
            FakeModelObject(
                predictions=self._predictions,
                metadata=self._stg_metadata,
            )
        ]

    def predict(self, df: pd.DataFrame) -> dict[str, list]:
        preds = (
            self._predictions
            if len(self._predictions) == len(df)
            else [self._predictions[0]] * len(df)
        )
        row_ids = list(range(1, len(df) + 1))
        return {"predictions": preds, "RowProcessingID": row_ids}

    @property
    def manifest(self) -> dict[str, Any]:
        return {"prod": self._prod_metadata, "stg": self._stg_metadata}

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "prod": self._prod_metadata,
            "stg": self._stg_metadata,
        }

    @property
    def champion(self) -> FakeModelObject:
        return self._champion

    @property
    def challengers(self) -> list[FakeModelObject]:
        return self._challengers


# -- FileTypes ----------------------------------------
class FakeFileTypesService:
    """Fake FileTypesService backed by an in-memory dict for unit/endpoint tests."""

    def __init__(
        self,
        filetypes: dict[str, dict[str, str]] | None = None,
    ):
        self._filetypes: dict[str, dict[str, str]] = filetypes or {}

    def generate_filetype_id(self, cols: list[str]) -> str:
        """Create a unique identifier from column names, matching the real
        implementation."""
        import re

        sanitized = [re.sub(r"[^a-zA-Z0-9_ .]", "_", col.strip()) for col in cols]
        return "-".join(sanitized)

    def get_filetype(self, id: str) -> dict:
        """Return file type info or raise UnknownFileTypeError."""
        from app.core.errors.domain import UnknownFileTypeError

        if id not in self._filetypes:
            raise UnknownFileTypeError(details={"file_schema": id})
        return self._filetypes[id]

    def add_filetype_to_database(
        self,
        cols: list[str],
        file_name: str,
        date_col: str,
        date_col_format: str,
        amount_col: str,
        receiver_col: str,
    ) -> None:
        """Store a file type in the in-memory dict."""
        fid = self.generate_filetype_id(cols)
        self._filetypes[fid] = {
            "FileID": fid,
            "FileName": file_name,
            "DateColumn": date_col,
            "DateColumnFormat": date_col_format,
            "AmountColumn": amount_col,
            "ReceiverColumn": receiver_col,
        }

    def list_filetypes(self) -> pd.DataFrame:
        """Return all registered file types as a DataFrame."""
        if not self._filetypes:
            return pd.DataFrame()
        return pd.DataFrame(self._filetypes.values())

    def delete_filetype_from_database(self, filename: str) -> None:
        """Remove a file type by filename."""
        from app.core.errors.domain import DatabaseQueryError

        key = next(
            (k for k, v in self._filetypes.items() if v["FileName"] == filename),
            None,
        )
        if key is None:
            raise DatabaseQueryError(
                message=f"File type with name '{filename}' not found or already deleted.",
                details={"file_name": filename},
            )
        del self._filetypes[key]
