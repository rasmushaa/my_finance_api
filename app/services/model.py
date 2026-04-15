"""Model loading and inference services backed by MLflow artifacts in GCS."""

import json
import logging
import os
import shutil
import tempfile
from importlib.metadata import version
from typing import Any, Dict

import mlflow
import pandas as pd
from mlflow.pyfunc import PyFuncModel
from packaging.requirements import Requirement

from app.core.errors.domain import ModelArtifactsError, ModelInputError

logger = logging.getLogger(__name__)

CANONICAL_FEATURES = [
    "date",
    "receiver",
    "amount",
]


class ModelObject:
    """Container for one loaded model and its metadata.

    Encapsulates a loaded MLflow model and associated manifest metadata. Inference
    enforces required model features before calling MLflow prediction.
    """

    def __init__(
        self,
        model: PyFuncModel | None,
        metadata: Dict[str, Any],
        fail_silently: bool = False,
    ):
        """Initialize model container.

        Parameters
        ----------
        model : PyFuncModel | None
            Loaded MLflow model instance, or ``None`` when load failed.
        metadata : dict
            Model metadata, including load/validation error details when present.
        fail_silently : bool, optional
            Backward-compatible constructor argument. Kept for API stability.
        """
        self.__model: PyFuncModel | None = model
        self.__metadata: Dict[str, Any] = metadata

    @property
    def model(self) -> PyFuncModel:
        if self.__model is None:
            raise ModelArtifactsError(message="Model is not loaded yet.")
        return self.__model

    @property
    def metadata(self) -> Dict[str, Any]:
        if self.__metadata is None:
            raise ModelArtifactsError(message="Model metadata is not loaded yet.")
        return self.__metadata

    def predict(self, input_df: pd.DataFrame) -> list:
        """Make predictions using the loaded model.

        Only the features required by the model (as defined in its input schema) are used for prediction.
        MLflow handles extra features gracefully, but this prevents warnings in the log.
        All features are converted to lowercase to avoid case sensitivity issues.

        Returns
        -------
        list
            List of predictions from the model.
        """
        # Validate that all required model features are present in the input DataFrame in lowercase form.
        model_features = [f.name for f in self.__model.metadata.signature.inputs]
        input_col_map = {col.lower(): col for col in input_df.columns}
        missing = [f for f in model_features if f.lower() not in input_col_map]

        # Model can not make predictions if required features are missing, so we raise an error with details about the mismatch.
        if missing:
            raise ModelInputError(
                details={
                    "hint": "API and MLflow model inputs are not synced. Ensure the model is trained with the correct features and re-deploy the API.",
                    "required_features": model_features,
                    "input_features": list(input_df.columns),
                }
            )

        # Select only the required features for prediction, and rename them to match the model's expected feature names (case-sensitive).
        used_data = input_df[[input_col_map[f.lower()] for f in model_features]]
        used_data = used_data.set_axis(model_features, axis=1)

        # Make predictions using the model.
        return self.__model.predict(used_data).tolist()


class ModelService:
    """Manage active MLflow models mirrored in GCS.

    Handles manifest fetch, artifact download, compatibility checks, and runtime model
    replacement for champion/challenger environments.
    """

    def __init__(self, db_client):
        self.__client = db_client
        self.__temp_dirs = []  # To keep track of temp directories for cleanup
        self.__manifest: Dict[str, Dict[str, Any]] = {}
        self.__models: Dict[str, ModelObject] = (
            {}
        )  # Key is model environment (prod, stg, dev)

    @property
    def metadata(self) -> dict:
        """Return model metadata keyed by environment."""
        return {env: model.metadata for env, model in self.__models.items()}

    @property
    def manifest(self) -> dict:
        """Return currently loaded manifest payload."""
        return self.__manifest

    @property
    def champion(self) -> ModelObject:
        """Return champion (``prod``) model object."""
        return self.__models.get("prod")

    @property
    def challengers(self) -> list[ModelObject]:
        """Return challenger model objects (non-``prod`` environments)."""
        return [model for env, model in self.__models.items() if env != "prod"]

    def load(self) -> None:
        """Load active model versions from manifest and refresh in-memory store.

        Called at startup and via explicit reload endpoint. Each environment entry is
        replaced even on failure, with errors exposed via metadata.
        """
        self._load_manifest_from_gcs()  # Contains active model versions and their metadata
        self._load_model(model_env="prod")
        self._load_model(model_env="stg")
        self._clear_temp_files()  # Clear GCS downloaded temp files after loading models

    def _load_model(self, model_env: str) -> None:
        """Load one environment model from GCS artifacts and validate compatibility.

        If loading/validation fails, model logic is set to ``None`` and error details
        are included in metadata.

        The model artifacts are expected to be organized in GCS as follows:
        model/
            prod/
                <version>/
                    model.pkl
                    requirements.txt
            stg/
                <version>/
                    model.pkl
                    requirements.txt

        Parameters
        ----------
        model_env : str
            The model environment to load, e.g. 'prod' or 'stg'.
        """
        model_metadata: Dict[str, Any] = {}
        try:
            model_metadata = self.__manifest.get(model_env) or {}
            if not model_metadata:
                raise ModelArtifactsError(
                    message=f"No manifest entry for environment '{model_env}'"
                )
            temp_path = self._load_model_artifacts_from_gcs(
                model_env=model_env, model_version=model_metadata["version"]
            )
            self._validate_model_package_version(temp_path)
            model = mlflow.pyfunc.load_model(model_uri=temp_path)
            self._validate_model_features(model)
            self.__models[model_env] = ModelObject(
                model=model, metadata={**model_metadata, "error": ""}
            )
            logger.info(
                f"Successfully loaded {model_env} model version {model_metadata.get('version', 'unknown')}"
            )

        except (
            Exception
        ) as e:  # Append the failed model without logic with the error details
            logger.warning(
                f"Failed to load model {model_env} version {model_metadata.get('version', 'unknown')}: {str(e)}"
            )
            self.__models[model_env] = ModelObject(
                model=None, metadata={**model_metadata, "error": str(e)}
            )

    def _validate_model_package_version(self, path: str) -> None:
        """Validate that model package requirements match runtime.

        Reads ``requirements.txt`` from model artifacts and compares `polymodel`
        version constraints to the runtime package version.

        Parameters
        ----------
        path : str
            The path to the model artifacts directory containing the requirements.txt file.

        Raises
        ------
        ModelArtifactsError
            If polymodel version in model requirements is incompatible with runtime.
        """
        requirements_file = os.path.join(path, "requirements.txt")

        if not os.path.exists(requirements_file):
            raise ModelArtifactsError(details={"missing_file": requirements_file})

        with open(requirements_file) as f:
            requirements = f.read()

        polymodel_requirement = next(
            (line for line in requirements.split("\n") if "polymodel" in line.lower()),
            None,
        )

        if not polymodel_requirement:
            raise ModelArtifactsError(
                details={
                    "file": requirements_file,
                    "message": "polymodel requirement not found in model requirements.txt",
                }
            )

        required_version = Requirement(polymodel_requirement).specifier
        try:
            runtime_version = version("polymodel")
        except Exception:
            raise ModelArtifactsError(
                message="Could not determine runtime polymodel version"
            )

        if not required_version.contains(runtime_version):
            raise ModelArtifactsError(
                message=f"Incompatible polymodel version: model requires {required_version}, but runtime has {runtime_version}",
                details={
                    "required_version": str(required_version),
                    "runtime_version": runtime_version,
                },
            )

    def _validate_model_features(self, model) -> None:
        """Ensure loaded model is supported.

        The model must have an input schema defined in MLflow model metadata,
        and the runtime features must cover all features required by the model.

        Parameters
        ----------
        model : PyFuncModel
            The loaded MLflow model to validate.

        Raises
        ------
        ModelArtifactsError
            If model does not have input schema or required features are missing.
        """
        model_signature = model.metadata.signature

        if model_signature is None:
            raise ModelArtifactsError(
                message="Model does not have an input schema defined",
                details={
                    "hint": "Define the model input schema when logging the model to MLflow, and re-deploy the API."
                },
            )

        model_features = {f.name for f in model.metadata.signature.inputs}
        available_features_set = set(CANONICAL_FEATURES)
        missing_features = model_features - available_features_set

        if missing_features:
            raise ModelArtifactsError(
                message="Model is missing required features",
                details={"missing_features": list(missing_features)},
            )

    def _load_model_artifacts_from_gcs(self, model_env: str, model_version: str) -> str:
        """Download model artifacts from GCS into a local temporary directory.

        Parameters
        ----------
        model_env : str
            Model environment key (for example ``"prod"`` or ``"stg"``).
        model_version : str
            Version string from manifest for selected environment.

        Returns
        -------
        str
            The path to the local temporary directory containing the model artifacts.
            Caller is responsible for cleanup via ``_clear_temp_files``.
        """

        prefix = f"model/{model_env}/{model_version}/"
        blobs = self.__client.list_blobs(prefix)

        if not blobs:
            raise ModelArtifactsError(
                details={
                    "message": f"No artifacts found in GCS at {prefix}",
                    "gcs_path": prefix,
                }
            )

        tmp_dir = tempfile.mkdtemp()
        for blob_path in blobs:
            # Strip the prefix to get the relative path within the model directory
            relative_path = blob_path[len(prefix) :]
            if not relative_path:
                continue
            local_path = os.path.join(tmp_dir, relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.__client.download_to_filename(blob_path, local_path)

        logger.debug(f"Downloaded model artifacts from GCS to {tmp_dir}")
        self.__temp_dirs.append(tmp_dir)  # Keep track of temp directory for cleanup
        return tmp_dir

    def _load_manifest_from_gcs(self) -> None:
        """Fetch active-model manifest from GCS.

        Manifest contains metadata for champion/challenger models and drives artifact
        path resolution and model metadata exposure.

        Example
        --------
        {
        "prod": {
            "version": 1,
            ...    },
        "stg": {
            "version": 2,
            ...    }
        }

        Notes
        -----
        On success, loaded manifest payload is written to ``self.__manifest``.
        """
        try:
            # Download manifest.json from GCS to a temp file
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_path = tmp.name
            self.__client.download_to_filename("manifest.json", tmp_path)

            # Load temp file to dict
            with open(tmp_path, encoding="utf-8") as f:
                manifest_data = json.load(f)

            # Clean and return
            os.remove(tmp_path)
            logger.debug(f"Fetched model manifest from GCS: {manifest_data}")
            self.__manifest = manifest_data

        except Exception as e:
            logger.error(f"Error fetching model manifest from GCS: {e}")

    def _clear_temp_files(self) -> None:
        """Remove temporary artifact directories created during model loading."""
        for path in self.__temp_dirs:
            try:
                shutil.rmtree(path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {path}: {str(e)}")
        self.__temp_dirs = []
