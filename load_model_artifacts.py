from mlflow.tracking import MlflowClient
import mlflow
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "BankingModel-main"
RESOLVED_MODEL_ALIAS_VERSION = "1"
DST = "./model_artifacts"

def load_model_artifacts():

    client = MlflowClient()

    mv = client.get_model_version(
        name=MODEL_NAME,
        version=RESOLVED_MODEL_ALIAS_VERSION,
    )

    mlflow.artifacts.download_artifacts(
        artifact_uri=mv.source,
        dst_path=DST,
    )

    logger.info(f"Downloaded artifacts for {MODEL_NAME}V{RESOLVED_MODEL_ALIAS_VERSION} to {DST}")


