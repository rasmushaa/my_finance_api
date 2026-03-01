import mlflow
import os
import json


ENV = os.getenv("ENV", "dev")
MODEL_NAME = "BankingModel"
MODEL_ALIAS = "prod" if ENV == "prod" else "stg" if ENV == "stg" else "dev"
DIST_PATH = "./model_artifacts"


def load_model_artifacts():
    """ Load the model artifacts for the specified model and alias from MLflow Model Registry.
    
    This function resolves the model version based on the provided alias, 
    downloads the model artifacts to a local directory, 
    and saves the model metadata for reference.
    """

    print(f"Loading model artifacts for {MODEL_NAME}@{MODEL_ALIAS}...")
    client = mlflow.tracking.MlflowClient()
    model_version = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS) # Raises INVALID_PARAMETER_VALUE if alias not found

    # Download the model artifacts for the resolved model version to a local directory
    mlflow.artifacts.download_artifacts(
        artifact_uri=model_version.source,
        dst_path=DIST_PATH,
    )
    print(f"Downloaded {MODEL_NAME}@{MODEL_ALIAS} (v{model_version.version}) artifacts to {DIST_PATH}.")

    # Save also the model metadata (version, run ID, tags) to a JSON file for reference
    model_metadata = {
        "model_name": MODEL_NAME,
        "alias": MODEL_ALIAS,
        "version": int(model_version.version),
        "run_id": str(model_version.run_id),
        "description": str(model_version.description),
        "package_version": str(model_version.tags["package.version"]),
        "commit_sha": str(model_version.tags["commit.sha"]),
        "model_features": str(model_version.tags["model.features"]),
        "model_architecture": str(model_version.tags["model.architecture"])
    }
    metadata_path = os.path.join(DIST_PATH, "model_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(model_metadata, f, indent=4)
    print(f"Saved model metadata to {metadata_path}.")


if __name__ == "__main__":
    load_model_artifacts()

