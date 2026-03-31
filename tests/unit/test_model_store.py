"""Tests for the ModelService class in app.services.model_store module."""

from unittest.mock import mock_open, patch

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions.model import ModelArtifactsError, ModelInputError
from app.services.model import ModelService


# --------------------------- Mock Classes for MlFlow --------------------------
class MockInput:
    def __init__(self, name: str):
        self.name = name


class MockSignature:
    def __init__(self, signature: list[str]):
        self.inputs = [MockInput(name) for name in signature]


class MockMetadata:
    def __init__(self, signature: list[str]):
        self.signature = MockSignature(signature)


class MockModel:
    def __init__(self, signature: list[str]):
        self.metadata = MockMetadata(signature)

    def predict(self, df):
        return np.array([0] * len(df))


# --------------------------- Test Cases for ModelService --------------------------
@patch("app.services.model.CANONICAL_FEATURES", ["a", "b"])
@patch("app.services.model.mlflow.pyfunc.load_model")
@patch("app.services.model.ModelService._load_model_metadata")
@patch("app.services.model.ModelService._validate_model_package_version")
def test_load_model(mock_validate_package, mock_load_model_metadata, mock_load_model):
    """Test the async load method of ModelService with successful loading scenario."""
    # Setup mock return values
    mock_validate_package.return_value = None  # Skip validation
    mock_load_model_metadata.return_value = {"version": "1", "alias": "prod"}
    mock_load_model.return_value = MockModel(signature=["a", "b"])

    store = ModelService()
    store.load()
    print(f"Metadata: {store.metadata}")

    assert store.metadata == {"version": "1", "alias": "prod"}
    assert store.predict(pd.DataFrame({"a": [1], "b": [2]})) == [
        0
    ]  # MockModel returns [0] for any input


@patch("app.services.model.CANONICAL_FEATURES", ["a", "b"])
@patch("app.services.model.ModelService._validate_model_package_version")
@patch("app.services.model.ModelService._load_model_metadata")
@patch("app.services.model.mlflow.pyfunc.load_model")
def test_load_model_signature_failure(
    mock_load_model, mock_load_metadata, mock_validate_package
):
    # Setup mocks
    mock_validate_package.return_value = None
    mock_load_metadata.return_value = {"version": "1"}
    mock_load_model.return_value = MockModel(
        signature=["a", "c"]
    )  # Missing required feature 'b'

    with pytest.raises(ModelArtifactsError, match="missing or invalid"):
        store = ModelService()
        store.load()


# Tests for _validate_model_package_version method
@patch("app.services.model.version")
@patch("app.services.model.os.path.exists")
def test_validate_model_package_version_success(mock_exists, mock_version):
    """Test successful validation when polymodel versions match."""
    # Mock requirements.txt exists
    mock_exists.return_value = True
    # Mock runtime version
    mock_version.return_value = "1.2.3"

    # Mock requirements.txt content with matching polymodel version
    requirements_content = "numpy==1.21.0\npolymodel~=1.2.3\npandas==1.3.0"

    with patch("builtins.open", mock_open(read_data=requirements_content)):
        store = ModelService()
        # Should not raise any exception
        store._validate_model_package_version()


@patch("app.services.model.version")
@patch("app.services.model.os.path.exists")
def test_validate_model_package_version_mismatch(mock_exists, mock_version):
    """Test validation fails when polymodel versions don't match."""
    mock_exists.return_value = True
    mock_version.return_value = "1.2.3"

    # Mock requirements.txt with different polymodel version
    requirements_content = "numpy==1.21.0\npolymodel==2.0.0\npandas==1.3.0"

    with patch("builtins.open", mock_open(read_data=requirements_content)):
        store = ModelService()
        with pytest.raises(
            ModelArtifactsError,
        ):
            store._validate_model_package_version()


@patch("app.services.model.version")
@patch("app.services.model.os.path.exists")
def test_validate_model_package_version_runtime_error(mock_exists, mock_version):
    """Test validation fails when runtime version cannot be determined."""
    mock_exists.return_value = True
    mock_version.side_effect = Exception("Package not found")

    requirements_content = "polymodel==1.2.3"

    with patch("builtins.open", mock_open(read_data=requirements_content)):
        store = ModelService()
        with pytest.raises(ModelArtifactsError):
            store._validate_model_package_version()


@patch("app.services.model.CANONICAL_FEATURES", ["a", "b"])
@patch("app.services.model.ModelService._validate_model_package_version")
@patch("app.services.model.ModelService._load_model_metadata")
@patch("app.services.model.mlflow.pyfunc.load_model")
def test_predict_mismatching_columns(
    mock_load_model, mock_load_metadata, mock_validate_package
):
    """Test that predict raises an error when input DataFrame has mismatching column
    names."""
    # Setup mocks
    mock_validate_package.return_value = None
    mock_load_metadata.return_value = {"version": "1"}
    mock_load_model.return_value = MockModel(signature=["a", "b"])

    store = ModelService()
    store.load()

    # Try to predict with mismatching column names
    with pytest.raises(ModelInputError):
        store.predict(pd.DataFrame({"a": [1], "c": [2]}))
