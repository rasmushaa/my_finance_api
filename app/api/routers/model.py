"""ML model endpoint router module.

This module defines the API router for ML model endpoints, which are used to interact
with and retrieve information about the machine learning model.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies.providers import (
    get_model_store,
    get_require_admin,
    get_require_user,
)
from app.schemas.error import ErrorResponse
from app.schemas.model import (
    ModelMetadataResponse,
    ModelStatusResponse,
    PredictRequest,
    PredictResponse,
)
from app.services.model import ModelService

router = APIRouter(prefix="/model", tags=["model"])


@router.post(
    "/predict",
    response_model=PredictResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Bad Request - Invalid input features",
        },
        503: {
            "model": ErrorResponse,
            "description": "Service Unavailable - Model not ready",
        },
    },
)
def predict(
    request: PredictRequest,
    payload: dict = Depends(get_require_user),
    store: ModelService = Depends(get_model_store),
):
    df = request.to_dataframe()
    preds = store.predict(df)
    return PredictResponse(predictions=preds)


@router.get(
    "/status",
    response_model=ModelStatusResponse,
    responses={
        503: {
            "model": ErrorResponse,
            "description": "Service Unavailable - Model not ready",
        },
    },
)
def model_status(
    payload: dict = Depends(get_require_user),
    store: ModelService = Depends(get_model_store),
):
    return ModelStatusResponse(status=store.status, is_ready=store.is_ready)


@router.get(
    "/metadata",
    response_model=ModelMetadataResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Requires admin role",
        },
        503: {
            "model": ErrorResponse,
            "description": "Service Unavailable - Model not ready",
        },
    },
)
def get_model_metadata(
    payload: dict = Depends(get_require_admin),
    store: ModelService = Depends(get_model_store),
):
    return ModelMetadataResponse(**store.metadata)
