"""
Testes for the ModelStore class in app.model_store module.
"""

from pyexpat import features
from unittest.mock import Mock, patch, mock_open
import pytest
import asyncio
from app.model_store import ModelStore, ModelLoadingStatus
import os
import numpy as np
import pandas as pd

# Mock the whole loaded mlflow.pyfunc module
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


def test_initialize_model_store():
    """ Smoke test to verify that ModelStore initializes with correct default values. """
    store = ModelStore()
    assert store.status == ModelLoadingStatus.NOT_STARTED
    assert not store.is_ready
    assert store.model is None
    assert store.model_info == {}


@patch("app.model_store.CANONICAL_FEATURES", ["a", "b"])
@patch("app.model_store.mlflow.pyfunc.load_model")
@patch("app.model_store.ModelStore._load_model_metadata")
@patch("app.model_store.ModelStore._validate_model_package_version")
@pytest.mark.asyncio
async def test_load_model(mock_validate_package, mock_load_model_metadata, mock_load_model):
    """ Test the async load method of ModelStore with successful loading scenario. """
    # Setup mock return values
    mock_validate_package.return_value = None  # Skip validation
    mock_load_model_metadata.return_value = {"version": "1", "alias": "prod"}
    mock_load_model.return_value = MockModel(signature=["a", "b"])

    store = ModelStore()
    await store.load()  # Call async method properly

    print(f"Status: {store.status}")
    print(f"Is Ready: {store.is_ready}")
    print(f"Metadata: {store.metadata}")
    print(f"Error: {store.error_message}")

    assert store.is_ready
    assert store.status == ModelLoadingStatus.READY
    assert store.metadata == {"version": "1", "alias": "prod"}
    assert store.predict(pd.DataFrame({"a": [1], "b": [2]})) == [0]  # MockModel returns [0] for any input


@patch("app.model_store.CANONICAL_FEATURES", ["a", "b"])
@patch("app.model_store.ModelStore._validate_model_package_version")
@patch("app.model_store.ModelStore._load_model_metadata")
@patch("app.model_store.mlflow.pyfunc.load_model")
@pytest.mark.asyncio
async def test_load_model_signature_failure(mock_load_model, mock_load_metadata, mock_validate_package):
    # Setup mocks
    mock_validate_package.return_value = None
    mock_load_metadata.return_value = {"version": "1"}
    mock_load_model.return_value = MockModel(signature=["a", "c"])  # Missing required feature 'b'

    with pytest.raises(ValueError, match="Model requires features not in canonical"):
        store = ModelStore()
        await store.load()


# Tests for _validate_model_package_version method
@patch("app.model_store.version")
@patch("app.model_store.os.path.exists")
def test_validate_model_package_version_success(mock_exists, mock_version):
    """Test successful validation when polymodel versions match."""
    # Mock requirements.txt exists
    mock_exists.return_value = True
    # Mock runtime version
    mock_version.return_value = "1.2.3"
    
    # Mock requirements.txt content with matching polymodel version
    requirements_content = "numpy==1.21.0\npolymodel~=1.2.3\npandas==1.3.0"
    
    with patch("builtins.open", mock_open(read_data=requirements_content)):
        store = ModelStore()
        # Should not raise any exception
        store._validate_model_package_version()


@patch("app.model_store.version")
@patch("app.model_store.os.path.exists") 
def test_validate_model_package_version_mismatch(mock_exists, mock_version):
    """Test validation fails when polymodel versions don't match.""" 
    mock_exists.return_value = True
    mock_version.return_value = "1.2.3"
    
    # Mock requirements.txt with different polymodel version
    requirements_content = "numpy==1.21.0\npolymodel==2.0.0\npandas==1.3.0"
    
    with patch("builtins.open", mock_open(read_data=requirements_content)):
        store = ModelStore()
        with pytest.raises(ValueError, match="Incompatible polymodel version: model requires 2.0.0, but runtime has 1.2.3"):
            store._validate_model_package_version()


@patch("app.model_store.version")
@patch("app.model_store.os.path.exists")
def test_validate_model_package_version_runtime_error(mock_exists, mock_version):
    """Test validation fails when runtime version cannot be determined."""
    mock_exists.return_value = True
    mock_version.side_effect = Exception("Package not found")
    
    requirements_content = "polymodel==1.2.3"
    
    with patch("builtins.open", mock_open(read_data=requirements_content)):
        store = ModelStore()
        with pytest.raises(ValueError, match="Could not determine runtime polymodel version"):
            store._validate_model_package_version()


