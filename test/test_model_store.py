"""
Testes for the ModelStore class in app.model_store module.
"""

from pyexpat import features
from unittest.mock import Mock, patch
import pytest
from app.model_store import ModelStore
import os
import mlflow

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
        raise NotImplementedError("This is a mock model and does not implement predict.")


def test_initialize_model_store():
    store = ModelStore()
    assert store.champion_model is None
    assert store.challenger_models == []
    assert store.model_info == {}


@patch("app.model_store.RESOLVED_MODEL_ALIAS_VERSION", "1")
@patch("app.model_store.CANONICAL_FEATURES", ["a", "b"])
@patch("app.model_store.mlflow.pyfunc.load_model")
@patch("app.model_store.ModelStore._find_model_versions")
def test_load_models(mock_find_versions, mock_load_model):
    # Setup mock return values
    mock_find_versions.return_value = [
        {"version": "1", "tags": {}},
        {"version": "2", "tags": {"stage": "challenger"}},
        {"version": "3", "tags": {}},
    ]
    mock_load_model.side_effect = [
        MockModel(signature=["a", "b"]),  # Champion model
        MockModel(signature=["a", "b"]),  # Challenger model
    ]

    store = ModelStore()
    store.load()

    print(store.model_info)

    assert store.champion_model is not None, "Champion model should be loaded."
    assert len(store.challenger_models) == 1, "There should be one challenger model loaded according to the tags."
    assert "champion" in store.model_info
    assert "challengers" in store.model_info


@patch("app.model_store.RESOLVED_MODEL_ALIAS_VERSION", "1")
@patch("app.model_store.CANONICAL_FEATURES", ["a", "b"])
@patch("app.model_store.mlflow.pyfunc.load_model")
@patch("app.model_store.ModelStore._find_model_versions")
def test_load_models_champion_signature_mismatch(mock_find_versions, mock_load_model):
    # Setup mock return values
    mock_find_versions.return_value = [
        {"version": "1", "tags": {}},
        {"version": "2", "tags": {"stage": "challenger"}},
    ]
    # Missing feature 'c' in champion model
    mock_load_model.side_effect = [
        MockModel(signature=["a", "b", "c"]),    # Champion model with missing feature
        MockModel(signature=["a", "b", "c"]),    # Challenger model with missing feature, should not matter
    ]
    store = ModelStore()
    with pytest.raises(ValueError, match="Model features do not match the canonical feature set and misses: {'c'}"):
        store.load()

    # Not using all canonical features
    mock_load_model.side_effect = [
        MockModel(signature=["a"]),    # Champion model with only subset of features
        MockModel(signature=["a"]),    # Challenger model with only subset of features, should not matter
    ]
    store = ModelStore()
    store.load()  # Should not raise an error when model uses subset of canonical features
    assert store.champion_model is not None, "Champion model should be loaded even with subset of features."
    assert len(store.challenger_models) == 1, "There should be one challenger model loaded according to the tags."


@patch("app.model_store.RESOLVED_MODEL_ALIAS_VERSION", "1")
@patch("app.model_store.CANONICAL_FEATURES", ["a", "b"])
@patch("app.model_store.mlflow.pyfunc.load_model")
@patch("app.model_store.mlflow.tracking.MlflowClient.search_model_versions")
def test_load_models_missing_registry(mock_search_model_versions, mock_load_model):
    # Setup mock return values
    mock_search_model_versions.return_value = []
    store = ModelStore()
    with pytest.raises(mlflow.exceptions.MlflowException, match="The service cannot function without a valid model."):
        store.load()


@patch("app.model_store.RESOLVED_MODEL_ALIAS_VERSION", "1")
@patch("app.model_store.CANONICAL_FEATURES", ["a", "b"])
@patch("app.model_store.mlflow.pyfunc.load_model")
@patch("app.model_store.ModelStore._find_model_versions")
def test_load_models_challenger_can_fail(mock_find_versions, mock_load_model):
    # Setup mock return values
    mock_find_versions.return_value = [
        {"version": "1", "tags": {}},
        {"version": "2", "tags": {"stage": "challenger"}},
    ]
    # Champion model is valid
    mock_load_model.side_effect = [
        MockModel(signature=["a", "b"]),
        MockModel(signature=["a", "b", "c"]),
    ]

    store = ModelStore()
    store.load()

    value = store.challenger_models[0].predict(None)
    assert value is None, "Challenger model predict should not raise any error, and return None instead."