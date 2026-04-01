from typing import Any, Dict, List

import pandas as pd
from pydantic import BaseModel, Field

from app.core.errors.domain import ModelInputError

CANONICAL_FEATURES = [
    "date",
    "receiver",
    "amount",
]


class PredictRequest(BaseModel):
    """A Pydantic model for the prediction request payload.

    This model expects a dictionary of input features matching the canonical features list.
    The `to_dataframe` method converts this dictionary into a pandas DataFrame
    with the specified columns needed for prediction.
    """

    inputs: Dict[str, List[Any]] = Field(
        ...,
        description="A dictionary of input features where keys are feature names and values are lists of feature values.",
    )

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the input dictionary to a pandas DataFrame with with canonical
        columns.

        Input features are validated before conversion.

        ## Returns
        - **pd.DataFrame**: A DataFrame constructed from the input dictionary.
        """
        self.__validate_features()
        sorted_inputs = {col: self.inputs[col] for col in CANONICAL_FEATURES}
        df = pd.DataFrame.from_dict(sorted_inputs)
        return df

    def __validate_features(self) -> None:
        """Validate that all canonical features are present in the input."""
        missing = set(CANONICAL_FEATURES) - self.inputs.keys()
        extra = self.inputs.keys() - set(CANONICAL_FEATURES)
        if missing:
            raise ModelInputError(details={"missing_features": list(missing)})
        if extra:
            raise ModelInputError(details={"unexpected_features": list(extra)})


class PredictResponse(BaseModel):
    """A Pydantic model for the prediction response payload.

    The model raises an error if it is not ready to provide predictions, and end user
    should validate the model status endpoint before making prediction requests.
    """

    predictions: List[str] = Field(
        ..., description="A list of predictions returned by the model."
    )


class ModelMetadataResponse(BaseModel):
    """A Pydantic model for the model metadata response payload.

    This model defines the structure of the metadata information returned by the
    /model/metadata endpoint.
    """

    model_name: str = Field(..., description="The name of the model.")
    alias: str = Field(..., description="The alias of the model.")
    version: int = Field(..., description="The MLFlow version of the model.")
    run_id: str = Field(..., description="The run ID of the model.")
    description: str = Field(
        default="", description="A brief description of the model."
    )
    package_version: str = Field(
        ..., description="The package version used by the model."
    )
    commit_sha: str = Field(..., description="The commit SHA of the model.")
    model_features: str = Field(
        ..., description="The list of features used by the model."
    )
    model_architecture: str = Field(..., description="The architecture of the model.")
