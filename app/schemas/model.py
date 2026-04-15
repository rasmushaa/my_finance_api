"""ML model metadata API schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class ModelMetadata(BaseModel):
    """Metadata for one loaded model environment.

    Attributes
    ----------
    name : str
        Registered model name.
    aliases : list
        Alias list from manifest/registry metadata.
    version : int
        Active model version for the environment.
    run_id : str
        Tracking run identifier used for provenance.
    description : str
        Human-readable model description.
    package_version : str
        Runtime package version recorded in model metadata.
    commit_sha : str
        Source commit SHA captured at training/build time.
    commit_head_sha : str
        Head SHA from training branch context.
    model_features : str
        Serialized list/description of model input features.
    model_architecture : str
        Model family/architecture label.
    error : str
        Error details when model failed to load or validate.
    """

    name: str = Field(default="", description="The mlflow name of the model.")
    aliases: list = Field(default=[], description="The mlflow alias of the model.")
    version: int = Field(
        default=0, description="The mlflow version number of the model."
    )
    run_id: str = Field(default="", description="The mlflow run ID of the model.")
    description: str = Field(
        default="", description="A brief description of the model."
    )
    package_version: str = Field(
        default="", description="The package version used by the model."
    )
    commit_sha: str = Field(default="", description="The commit SHA of the model.")
    commit_head_sha: str = Field(
        default="",
        description="The head (latest commit before merge) commit SHA of the model.",
    )
    model_features: str = Field(
        default="", description="The list of features used by the model."
    )
    model_architecture: str = Field(
        default="", description="The architecture of the model."
    )
    error: str = Field(
        default="",
        description="Error message if the model is not ready for predictions.",
    )


class ModelMetadataResponse(BaseModel):
    """Aggregated metadata response for champion and challenger environments.

    Attributes
    ----------
    prod : ModelMetadata
        Production (champion) model metadata.
    stg : ModelMetadata | None
        Staging (challenger) model metadata when available.
    """

    prod: ModelMetadata = Field(..., description="Metadata of the production model.")
    stg: Optional[ModelMetadata] = Field(
        default=None, description="Metadata of the staging model."
    )
