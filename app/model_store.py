import logging
import os
import mlflow
from mlflow.pyfunc import PyFuncModel
from app.schemas import CANONICAL_FEATURES

logger = logging.getLogger(__name__)


MODEL_NAME = os.getenv('MODEL_NAME')
RESOLVED_MODEL_ALIAS_VERSION = os.getenv("RESOLVED_MODEL_ALIAS_VERSION")


class ModelPredictionWrapper:
    """ A wrapper used for shadow testing of challenger models.
    
    Shaddow models are allowed to fail without impacting the main service,
    to enable safe and agile testing of new models in production.
    """
    def __init__(self, model: PyFuncModel):
        self.model = model

    def predict(self, df):
        try:
            predictions = self.model.predict(df)
            return predictions
        except Exception as e:
            logger.error(f"Model prediction failed: {e}")
            return None


class ModelStore:
    def __init__(self):
        self.champion_model: PyFuncModel | None = None
        self.challenger_models: list[PyFuncModel] = []
        self.model_info: dict = {}

    def load(self) -> None:
        """ Load models from MLflow Model Registry into the store.
        
        The production champion model is loaded according to the pinned version,
        and validated to ensure it meets the required feature schema.
        Challenger models are loaded based on their tags, but not validated.
        """
        models = self._find_model_versions(MODEL_NAME)

        for model_details in models:   

            # Find and load production champion model, only this one is validated and fails the service if invalid
            version = model_details["version"]
            if version == RESOLVED_MODEL_ALIAS_VERSION:
                logger.info(f"Loading production champion model version {version}.")
                model = mlflow.pyfunc.load_model(
                    model_uri=f"models:/{MODEL_NAME}/{version}"
                )
                self._validate_model_features(model, CANONICAL_FEATURES)
                self.champion_model = model
                self.model_info["champion"] = model_details

            # Load all unpinned challenger models according to their tags. These are not validated!
            if model_details["tags"].get("stage") == "challenger":
                logger.info(f"Loading challenger model version {version}.")
                model = mlflow.pyfunc.load_model(
                    model_uri=f"models:/{MODEL_NAME}/{version}"
                )
                wrapped_model = ModelPredictionWrapper(model)
                self.challenger_models.append(wrapped_model)
                self.model_info.setdefault("challengers", []).append(model_details)

    def _find_model_versions(self, model_name: str) -> list[dict]:
        """ Find all versions of a registered model in MLflow Model Registry.
        
        Parameters
        ----------
        model_name : str
            Name of the registered model on the MLflow Model Registry.
        
        Returns
        -------
        list[dict]
            List of model version details including version number, run ID, aliases, and tags.

        Raises
        ------
        mlflow.exceptions.MlflowException
            If no versions are found for the specified model.
        """
        client = mlflow.tracking.MlflowClient()
        
        model_versions = []
        for mv in client.search_model_versions(f"name='{model_name}'"):
            model_versions.append({
                "version": mv.version,
                "run_id": mv.run_id,
                "aliases": mv.aliases,
                "tags": mv.tags,
            })
            
        if not model_versions:
            raise mlflow.exceptions.MlflowException(
                f"No versions found for model '{model_name}' in MLflow Model Registry. The service cannot function without a valid model."
            )
        
        logger.info(f"Found {len(model_versions)} versions for model '{model_name}'.")
        return model_versions
    
    def _validate_model_features(self, model: PyFuncModel, availeable_features: list[str]) -> None:
        """ Ensure loaded model is supported
        
        The model must have an input schema defined in MLflow model metadata,
        and the runtime features must cover all features required by the model.

        Raises
        ------
        ValueError
            If model does not have input schema or required features are missing.
        """
        model_signature = model.metadata.signature

        if model_signature is None:
            raise ValueError(f"Model does not have an input schema defined.")
    
        model_features = [f.name for f in model.metadata.signature.inputs]
        missing_features = set(model_features) - set(availeable_features)
        if missing_features:
            raise ValueError(f"Model features do not match the canonical feature set and misses: {missing_features}")