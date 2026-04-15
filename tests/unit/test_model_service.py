"""Tests for ModelService and ModelObject in app.services.model module."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from app.core.errors.domain import ModelArtifactsError, ModelInputError
from app.services.model import CANONICAL_FEATURES, ModelObject, ModelService


# -- Helpers -------------------------------
class MockInput:
    def __init__(self, name: str):
        self.name = name


class MockSignature:
    def __init__(self, features: list[str]):
        self.inputs = [MockInput(name) for name in features]


class MockMetadata:
    def __init__(self, features: list[str]):
        self.signature = MockSignature(features)


class MockModel:
    def __init__(self, features: list[str]):
        self.metadata = MockMetadata(features)

    def predict(self, df):
        return np.array(["cat_a"] * len(df))


def _make_service(client=None):
    """Create a ModelService with a mock client."""
    return ModelService(db_client=client or Mock())


# -- ModelObject.predict() ---------------------------------
def test_predict_returns_list():
    """Predict() returns the model output as a plain list."""
    obj = ModelObject(model=MockModel(["a", "b"]), metadata={"version": "1"})
    result = obj.predict(pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    assert result == ["cat_a", "cat_a"]


def test_predict_case_insensitive_column_matching():
    """Predict() maps input columns to model features case-insensitively."""
    obj = ModelObject(model=MockModel(["a", "B"]), metadata={"version": "1"})
    result = obj.predict(pd.DataFrame({"A": [1], "b": [2]}))
    assert result == ["cat_a"]


def test_predict_missing_feature_raises():
    """Predict() raises ModelInputError when a required model feature is absent."""
    obj = ModelObject(model=MockModel(["a", "b"]), metadata={"version": "1"})
    with pytest.raises(ModelInputError):
        obj.predict(pd.DataFrame({"a": [1], "c": [2]}))


def test_predict_extra_columns_ignored():
    """Predict() ignores extra columns not required by the model."""
    obj = ModelObject(model=MockModel(["a"]), metadata={"version": "1"})
    result = obj.predict(pd.DataFrame({"a": [1], "extra": [2]}))
    assert result == ["cat_a"]


# -- ModelObject properties --------------------------------
def test_model_property_raises_when_none():
    """Accessing .model raises ModelArtifactsError when model is None."""
    obj = ModelObject(model=None, metadata={})
    with pytest.raises(ModelArtifactsError, match="not loaded"):
        _ = obj.model


def test_metadata_property_raises_when_none():
    """Accessing .metadata raises ModelArtifactsError when metadata was set to None."""
    obj = ModelObject(model=MockModel(["a"]), metadata=None)
    with pytest.raises(ModelArtifactsError, match="not loaded"):
        _ = obj.metadata


# -- ModelService.load() -----------------------------------
@patch("app.services.model.ModelService._clear_temp_files")
@patch("app.services.model.ModelService._load_model")
@patch("app.services.model.ModelService._load_manifest_from_gcs")
def test_load_calls_manifest_and_both_envs(mock_manifest, mock_load_model, mock_clear):
    """Load() fetches manifest then loads prod and stg models, then cleans temp
    files."""
    store = _make_service()
    store.load()

    mock_manifest.assert_called_once()
    assert mock_load_model.call_count == 2
    mock_load_model.assert_any_call(model_env="prod")
    mock_load_model.assert_any_call(model_env="stg")
    mock_clear.assert_called_once()


@patch("app.services.model.ModelService._validate_model_features")
@patch("app.services.model.mlflow.pyfunc.load_model")
@patch("app.services.model.ModelService._validate_model_package_version")
@patch("app.services.model.ModelService._load_model_artifacts_from_gcs")
def test_load_model_success_stores_model_with_empty_error(
    mock_gcs, mock_pkg, mock_mlflow, mock_feat
):
    """_load_model() stores ModelObject with error='' on success.

    Even if the model loading and validation steps succeed, the ModelObject's metadata
    must include an 'error' key with an empty string to indicate no errors occurred.
    """
    mock_gcs.return_value = "/tmp/artifacts"
    mock_mlflow.return_value = MockModel(["a"])

    store = _make_service()
    store._ModelService__manifest = {"prod": {"version": "1", "model_name": "test"}}
    store._load_model(model_env="prod")

    model_obj = store._ModelService__models["prod"]
    assert model_obj.metadata == {
        "version": "1",
        "model_name": "test",
        "error": "",
    }, "Model metadata must always include an 'error' key, even if empty on success."


@patch("app.services.model.ModelService._load_model_artifacts_from_gcs")
def test_load_model_failure_stores_none_model_with_error(mock_gcs):
    """_load_model() stores ModelObject(model=None) with error in metadata on
    failure."""
    mock_gcs.side_effect = ModelArtifactsError(message="download failed")

    store = _make_service()
    store._ModelService__manifest = {"prod": {"version": "1"}}
    store._load_model(model_env="prod")

    model_obj = store._ModelService__models["prod"]
    assert "download failed" in model_obj.metadata["error"]
    with pytest.raises(ModelArtifactsError, match="not loaded"):
        _ = model_obj.model


# -- ModelService properties -------------------------------
def test_champion_and_challengers():
    """Champion returns the prod model, challengers returns non-prod models."""
    store = _make_service()
    prod = ModelObject(model=MockModel(["a"]), metadata={"env": "prod"})
    stg = ModelObject(model=MockModel(["a"]), metadata={"env": "stg"})
    store._ModelService__models = {"prod": prod, "stg": stg}

    assert store.champion is prod
    assert store.challengers == [stg]


# -- _validate_model_package_version() ---------------------
@patch("app.services.model.version", return_value="1.0.0")
def test_validate_package_version_compatible(mock_ver):
    """No error when runtime polymodel version satisfies the model requirement."""
    store = _make_service()
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("polymodel==1.0.0\nnumpy>=1.21\n")
        store._validate_model_package_version(d)  # should not raise


@patch("app.services.model.version", return_value="2.0.0")
def test_validate_package_version_incompatible_raises(mock_ver):
    """Raises ModelArtifactsError when runtime version doesn't match requirement."""
    store = _make_service()
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("polymodel==1.0.0\n")
        with pytest.raises(ModelArtifactsError, match="Incompatible"):
            store._validate_model_package_version(d)


def test_validate_package_version_missing_requirements_raises():
    """Raises ModelArtifactsError when requirements.txt is missing."""
    store = _make_service()
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ModelArtifactsError):
            store._validate_model_package_version(d)


def test_validate_package_version_no_polymodel_raises():
    """Raises ModelArtifactsError when polymodel is not in requirements.txt."""
    store = _make_service()
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "requirements.txt"), "w") as f:
            f.write("numpy>=1.21\npandas>=1.3\n")
        with pytest.raises(ModelArtifactsError):
            store._validate_model_package_version(d)


# -- _validate_model_features() ---------------------------
def test_validate_features_subset_of_canonical_passes():
    """No error when model features are a subset of CANONICAL_FEATURES."""
    store = _make_service()
    model = MockModel(CANONICAL_FEATURES[:2])
    store._validate_model_features(model)  # should not raise


def test_validate_features_missing_features_raises():
    """Raises ModelArtifactsError when model requires features not in
    CANONICAL_FEATURES."""
    store = _make_service()
    model = MockModel(CANONICAL_FEATURES + ["unknown_feature"])
    with pytest.raises(ModelArtifactsError, match="missing"):
        store._validate_model_features(model)


def test_validate_features_no_signature_raises():
    """Raises ModelArtifactsError when model has no input signature."""
    store = _make_service()
    model = MockModel([])
    model.metadata.signature = None
    with pytest.raises(ModelArtifactsError, match="input schema"):
        store._validate_model_features(model)


# -- _load_manifest_from_gcs() ----------------------------
def test_load_manifest_parses_json_from_gcs():
    """_load_manifest_from_gcs downloads and parses manifest.json into self.manifest."""
    manifest_data = {"prod": {"version": "3"}, "stg": {"version": "4"}}

    mock_client = Mock()

    def fake_download(src, dest):
        with open(dest, "w") as f:
            json.dump(manifest_data, f)

    mock_client.download_to_filename.side_effect = fake_download

    store = _make_service(client=mock_client)
    store._load_manifest_from_gcs()

    assert store.manifest == manifest_data


def test_load_manifest_gcs_error_does_not_raise():
    """_load_manifest_from_gcs swallows GCS errors and leaves manifest empty."""
    mock_client = Mock()
    mock_client.download_to_filename.side_effect = Exception("GCS unreachable")

    store = _make_service(client=mock_client)
    store._load_manifest_from_gcs()  # should not raise
    assert store.manifest == {}


# -- _load_model_artifacts_from_gcs() ----------------------
def test_load_artifacts_no_blobs_raises():
    """_load_model_artifacts_from_gcs raises ModelArtifactsError when no blobs found."""
    mock_client = Mock()
    mock_client.list_blobs.return_value = []

    store = _make_service(client=mock_client)
    with pytest.raises(ModelArtifactsError):
        store._load_model_artifacts_from_gcs(model_env="prod", model_version="1")


# -- ModelService.metadata property -------------------------------
def test_metadata_returns_env_keyed_dict():
    """Metadata property returns dict keyed by environment."""
    store = _make_service()
    store._ModelService__models["prod"] = ModelObject(
        model=MockModel(["a"]),
        metadata={"version": "1"},
    )
    store._ModelService__models["stg"] = ModelObject(
        model=MockModel(["a"]),
        metadata={"version": "2"},
    )

    meta = store.metadata
    assert meta["prod"] == {"version": "1"}
    assert meta["stg"] == {"version": "2"}
