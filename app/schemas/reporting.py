"""Reporting API schemas."""

from typing import List

from pydantic import BaseModel, Field


class ModelAccuracyRow(BaseModel):
    """Single model-accuracy row returned by reporting endpoint.

    Attributes
    ----------
    year_month : str
        Aggregation period in ``YYYY-MM`` format.
    category : str
        Transaction category key (``"ALL"`` for micro-average row).
    accuracy : float
        Accuracy value in range ``[0, 1]``.
    model_name : str
        Model name associated with prediction rows.
    model_alias : str
        Alias string attached to model version.
    model_version : str
        Model version identifier.
    model_commit_sha : str
        Commit SHA captured in model metadata.
    model_commit_head_sha : str
        Head SHA captured in model metadata.
    model_architecture : str
        Model architecture label.
    """

    year_month: str = Field(
        ..., examples=["2023-01"], description="Year and month in YYYY-MM format"
    )
    category: str = Field(
        ..., examples=["FOOD"], description="Category of the transaction"
    )
    accuracy: float = Field(
        ...,
        examples=[0.85],
        description="Precision (correct predictions vs total predictions) of the model for the given category and month",
    )
    model_name: str = Field(..., examples=["MyModel"], description="Name of the model")
    model_alias: str = Field(
        ..., examples=["my_model_v1"], description="Alias of the model"
    )
    model_version: str = Field(
        ..., examples=["1.0.0"], description="Version of the model"
    )
    model_commit_sha: str = Field(
        ..., examples=["abc123"], description="Commit SHA of the model"
    )
    model_commit_head_sha: str = Field(
        ..., examples=["def456"], description="Commit head SHA of the model"
    )
    model_architecture: str = Field(
        ..., examples=["RandomForest"], description="Architecture of the model"
    )


class ModelAccuracyResponse(BaseModel):
    """Response payload for model-accuracy reporting endpoint.

    Attributes
    ----------
    rows : list[ModelAccuracyRow]
        Flattened table rows for visualization and downstream analysis.
    """

    rows: List[ModelAccuracyRow] = Field(
        ...,
        description="List of model accuracy rows.",
    )
