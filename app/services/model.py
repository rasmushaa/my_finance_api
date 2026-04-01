import json
import logging
import os
from importlib.metadata import version
from typing import Dict

import mlflow
import pandas as pd
from mlflow.pyfunc import PyFuncModel

from app.core.errors.domain import ModelArtifactsError, ModelInputError
from app.schemas.model import CANONICAL_FEATURES

logger = logging.getLogger(__name__)


MODEL_ARTIFACTS_PATH = (
    "./model_artifacts"  # The artifacts are embedded in the container image
)


class ModelService:
    """Class to manage local MlFlow models.

    This class handles loading the model artifacts, validating them, and providing an
    interface for making predictions. The model is loaded asynchronously at application
    startup, and the service maintains the loading status.
    """

    def __init__(self):
        self.__model: PyFuncModel | None = None
        self.__model_info: dict = {}

    @property
    def metadata(self) -> Dict[str, str]:
        """Return model custom metadata including tags.

        Returns
        -------
        dict
            Dictionary containing model metadata such as version and alias.
        """
        return self.__model_info

    def predict(self, input_df: pd.DataFrame) -> list:
        """Make predictions using the loaded model.

        Only the features required by the model (as defined in its input schema) are used for prediction.
        MlFlow handles extra features gracefully, but this prevents warnings in the log.
        All featues are converted to lowercase to avoid case sensitivity issues.

        Returns
        -------
        list
            List of predictions from the model.
        """
        model_features = [f.name for f in self.__model.metadata.signature.inputs]
        # Map lowercased input column name -> original input column name
        input_col_map = {col.lower(): col for col in input_df.columns}
        missing = [f for f in model_features if f.lower() not in input_col_map]
        if missing:
            raise ModelInputError(
                details={
                    "hint": "API and Mlflwo model inputs are not synced. Ensure the model is trained with the correct features and re-deploy the API.",
                    "required_features": model_features,
                    "input_features": list(input_df.columns),
                }
            )
        # Select columns by their original name in input_df and rename to model's casing
        used_data = input_df[[input_col_map[f.lower()] for f in model_features]]
        used_data = used_data.set_axis(model_features, axis=1)
        return self.__model.predict(used_data).tolist()

    def load(self) -> None:
        """Load models from MLflow Model Registry into the store.

        This method updates the loading status. There is no error handling in this
        method since we want the application to fail to start if model loading fails, as
        the API cannot function without a model.
        """
        self._load_model_artifacts()
        logger.info(f"Successfully loaded model info: {self.__model_info}")

    def _load_model_artifacts(self) -> None:
        """Load a model from MLflow Model Registry and validate its features.

        This method is intended to be run in a separate thread to avoid blocking the
        event loop.
        """
        self._validate_model_package_version()
        self.__model = mlflow.pyfunc.load_model(model_uri=MODEL_ARTIFACTS_PATH)
        self.__model_info = self._load_model_metadata()
        self._validate_model_features()

    def _load_model_metadata(self) -> dict:
        """Load model metadata such as version and feature requirements."""
        meta_file = os.path.join(MODEL_ARTIFACTS_PATH, "model_metadata.json")
        if not os.path.exists(meta_file):
            raise ModelArtifactsError(details={"missing_file": meta_file})
        with open(meta_file) as f:
            metadata = json.load(f)
        return metadata

    def _validate_model_package_version(self) -> None:
        """Validate that the model's package version is compatible with the runtime.

        Reads requirements.txt from the model artifacts and compares the polymodel
        version with the currently loaded version.

        Raises
        ------
        ValueError
            If polymodel version in model requirements is incompatible with runtime.
        """
        requirements_file = os.path.join(MODEL_ARTIFACTS_PATH, "requirements.txt")

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

        required_version = polymodel_requirement.split("=")[-1].strip()
        try:
            runtime_version = version("polymodel")
        except Exception:
            raise ModelArtifactsError(
                details={"message": "Could not determine runtime polymodel version"}
            )

        if required_version != runtime_version:
            raise ModelArtifactsError(
                details={
                    "required_version": required_version,
                    "runtime_version": runtime_version,
                    "message": f"Incompatible polymodel version: model requires {required_version}, "
                    f"but runtime has {runtime_version}",
                }
            )

    def _validate_model_features(self) -> None:
        """Ensure loaded model is supported.

        The model must have an input schema defined in MLflow model metadata,
        and the runtime features must cover all features required by the model.

        Raises
        ------
        ModelArtifactsError
            If model does not have input schema or required features are missing.
        """
        model_signature = self.__model.metadata.signature

        if model_signature is None:
            raise ModelArtifactsError(
                details={"message": "Model does not have an input schema defined."}
            )

        model_features = {f.name for f in self.__model.metadata.signature.inputs}
        available_features_set = set(CANONICAL_FEATURES)
        missing_features = model_features - available_features_set

        if missing_features:
            raise ModelArtifactsError(
                details={"missing_features": list(missing_features)}
            )
