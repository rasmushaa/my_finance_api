import logging
import os
import mlflow
from mlflow.pyfunc import PyFuncModel
from app.schemas import CANONICAL_FEATURES
import asyncio
from enum import Enum
from typing import Dict, Optional
import polymodel
import json
import pandas as pd
from importlib.metadata import version

logger = logging.getLogger(__name__)


MODEL_ARTIFACTS_PATH = "model_artifacts" # The artifacts are embedded in the container image


class ModelLoadingStatus(Enum):
    NOT_STARTED = "not_started"
    LOADING = "loading"
    READY = "ready"


class ModelStore:
    def __init__(self):
        self.model: PyFuncModel | None = None
        self.model_info: dict = {}
        self._status: ModelLoadingStatus = ModelLoadingStatus.NOT_STARTED
        self._error_message: Optional[str] = None
        
    @property
    def status(self) -> ModelLoadingStatus:
        return self._status
        
    @property
    def is_ready(self) -> bool:
        return self._status == ModelLoadingStatus.READY
        
    @property
    def error_message(self) -> Optional[str]:
        return self._error_message
    
    @property
    def metadata(self) -> Dict[str, str]:
        """ Return model custom metadata including tags.

        Raises
        ------
        ValueError
            If model is not ready and metadata is not available.
        """
        if not self.is_ready:
            raise ValueError("Model is not ready, metadata not available")
        return self._model_info
    
    def predict(self, input_df: pd.DataFrame) -> list:
        """ Make predictions using the loaded model.
        
        Only the features required by the model (as defined in its input schema) are used for prediction.
        MlFlow handles extra features gracefully, but this prevents warnings in the log.

        Raises
        ------
        ValueError
            If model is not ready and prediction cannot be made.

        Returns
        -------
        list
            List of predictions from the model.
        """
        if not self.is_ready:
            raise ValueError("Model is not ready, prediction cannot be made")
        model_features = [f.name for f in self._model.metadata.signature.inputs]
        used_data = input_df[model_features]
        return self._model.predict(used_data).tolist()

    async def load(self) -> None:
        """ Async load models from MLflow Model Registry into the store.
        
        This method updates the loading status.
        There is no error handling in this method since we want the application to fail to start 
        if model loading fails, as the API cannot function without a model.
        """

        self._status = ModelLoadingStatus.LOADING
        logger.info(f"Starting async model loading...")
        await asyncio.to_thread(self._load_model_artifacts)  
        self._status = ModelLoadingStatus.READY
        logger.info(f"Successfully loaded models")

    def _load_model_artifacts(self) -> None:
        """ Load a model from MLflow Model Registry and validate its features.
        
        This method is intended to be run in a separate thread to avoid blocking the event loop.
        """
        self._validate_model_package_version()
        self._model = mlflow.pyfunc.load_model(model_uri=MODEL_ARTIFACTS_PATH)
        self._model_info = self._load_model_metadata()
        self._validate_model_features()

    def _load_model_metadata(self) -> dict:
        """ Load model metadata such as version and feature requirements.
        """
        meta_file = os.path.join(MODEL_ARTIFACTS_PATH, "model_metadata.json")
        if not os.path.exists(meta_file):
            raise ValueError("Model metadata file not found in artifacts")
        with open(meta_file, "r") as f:
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
            raise ValueError("Model requirements.txt not found in artifacts")
    
        with open(requirements_file, "r") as f:
            requirements = f.read()
        
        polymodel_requirement = next(
            (line for line in requirements.split("\n") if "polymodel" in line.lower()),
            None
        )
        
        if not polymodel_requirement:
            raise ValueError("polymodel requirement not found in model requirements.txt")
        
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
        """ Ensure loaded model is supported
        
        The model must have an input schema defined in MLflow model metadata,
        and the runtime features must cover all features required by the model.

        Raises
        ------
        ValueError
            If model does not have input schema or required features are missing.
        """
        model_signature = self._model.metadata.signature

        if model_signature is None:
            raise ValueError(f"Model does not have an input schema defined.")
    
        model_features = set(f.name for f in self._model.metadata.signature.inputs)
        available_features_set = set(CANONICAL_FEATURES)
        missing_features = model_features - available_features_set
        
        if missing_features:
            raise ValueError(f"Model requires features not in canonical feature set: {missing_features}")