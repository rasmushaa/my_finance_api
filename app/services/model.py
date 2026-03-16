import asyncio
import json
import logging
import os
from enum import Enum
from importlib.metadata import version
from typing import Dict

import mlflow
import pandas as pd
from mlflow.pyfunc import PyFuncModel

from app.core.exceptions.model import ModelFileNotFoundError, ModelNotAvailableError
from app.schemas.model import CANONICAL_FEATURES

logger = logging.getLogger(__name__)


MODEL_ARTIFACTS_PATH = (
    "./model_artifacts"  # The artifacts are embedded in the container image
)


class ModelLoadingStatus(Enum):
    NOT_STARTED = "not_started"
    LOADING = "loading"
    READY = "ready"


class ModelService:
    """Class to manage local MlFlow models.

    This class handles loading the model artifacts, validating them, and providing an
    interface for making predictions. The model is loaded asynchronously at application
    startup, and the service maintains the loading status.
    """

    def __init__(self):
        self.__model: PyFuncModel | None = None
        self.__model_info: dict = {}
        self.__status: ModelLoadingStatus = ModelLoadingStatus.NOT_STARTED

    @property
    def status(self) -> ModelLoadingStatus:
        return self.__status

    @property
    def is_ready(self) -> bool:
        return self.__status == ModelLoadingStatus.READY

    @property
    def metadata(self) -> Dict[str, str]:
        """Return model custom metadata including tags.

        Raises
        ------
        ModelNotAvailableError
            If model is not ready and metadata is not available.
        """
        if not self.is_ready:
            raise ModelNotAvailableError(details={"model_status": self.status.value})
        return self.__model_info

    def predict(self, input_df: pd.DataFrame) -> list:
        """Make predictions using the loaded model.

        Only the features required by the model (as defined in its input schema) are used for prediction.
        MlFlow handles extra features gracefully, but this prevents warnings in the log.

        Raises
        ------
        ModelNotAvailableError
            If model is not ready and prediction cannot be made.

        Returns
        -------
        list
            List of predictions from the model.
        """
        if not self.is_ready:
            raise ModelNotAvailableError(details={"model_status": self.status.value})
        model_features = [f.name for f in self.__model.metadata.signature.inputs]
        used_data = input_df[model_features]
        return self.__model.predict(used_data).tolist()

    async def load(self) -> None:
        """Async load models from MLflow Model Registry into the store.

        This method updates the loading status. There is no error handling in this
        method since we want the application to fail to start if model loading fails, as
        the API cannot function without a model.
        """

        self.__status = ModelLoadingStatus.LOADING
        await asyncio.to_thread(self._load_model_artifacts)
        self.__status = ModelLoadingStatus.READY
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
            raise ModelFileNotFoundError(details={"file": meta_file})
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
            raise ModelFileNotFoundError(details={"file": requirements_file})

        with open(requirements_file) as f:
            requirements = f.read()

        polymodel_requirement = next(
            (line for line in requirements.split("\n") if "polymodel" in line.lower()),
            None,
        )

        if not polymodel_requirement:
            raise ModelFileNotFoundError(
                details={
                    "file": requirements_file,
                    "message": "polymodel requirement not found in model requirements.txt",
                }
            )

        required_version = polymodel_requirement.split("=")[-1].strip()
        try:
            runtime_version = version("polymodel")
        except Exception:
            raise ValueError("Could not determine runtime polymodel version")

        if required_version != runtime_version:
            raise ValueError(
                f"Incompatible polymodel version: model requires {required_version}, "
                f"but runtime has {runtime_version}"
            )

    def _validate_model_features(self) -> None:
        """Ensure loaded model is supported.

        The model must have an input schema defined in MLflow model metadata,
        and the runtime features must cover all features required by the model.

        Raises
        ------
        ValueError
            If model does not have input schema or required features are missing.
        """
        model_signature = self.__model.metadata.signature

        if model_signature is None:
            raise ValueError(f"Model does not have an input schema defined.")

        model_features = {f.name for f in self.__model.metadata.signature.inputs}
        available_features_set = set(CANONICAL_FEATURES)
        missing_features = model_features - available_features_set

        if missing_features:
            raise ValueError(
                f"Model requires features not in canonical feature set: {missing_features}"
            )
