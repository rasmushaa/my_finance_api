"""Administrative endpoints for model metadata, manifest, and reload."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_model_store, get_require_admin
from app.schemas.error import ErrorResponse
from app.schemas.model import ModelMetadataResponse
from app.services.model import ModelService

router = APIRouter(prefix="/model", tags=["ML Model Endpoints"])


# -- Model Metadata Endpoint ----------------------------------------------------------------------
@router.get(
    "/metadata",
    response_model=ModelMetadataResponse,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Requires admin role",
        },
    },
)
def get_model_metadata(
    user: dict = Depends(get_require_admin),
    store: ModelService = Depends(get_model_store),
):
    """Return metadata for currently loaded champion and challenger models.

    ## Parameters
    - **user** (`dict`): Authenticated admin payload.
    - **store** (`ModelService`): Model service providing metadata.

    ## Returns
    - **ModelMetadataResponse**: Model versioning and provenance metadata.
    """
    return ModelMetadataResponse(**store.metadata)


# -- Model Manifest Endpoint ----------------------------------------------------------------------
@router.get(
    "/manifest",
    response_model=dict,
    responses={
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Requires admin role",
        },
    },
)
def get_model_manifest(
    user: dict = Depends(get_require_admin),
    store: ModelService = Depends(get_model_store),
):
    """Return the manifest of the currently loaded ML model.

    ## Parameters
    - **user** (`dict`): Authenticated admin payload.
    - **store** (`ModelService`): Model service providing manifest.

    ## Returns
    - **dict**: Manifest payload loaded from GCS, including active model versions.
    """
    return store.manifest


# -- Model force reload endpoint ----------------------------------------------------------------------
@router.post(
    "/reload",
    responses={
        200: {
            "description": "Model reload process completed",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "example": {
                            "message": "Model reloaded process completed. Note: models may not have updated, if the process failed. Check logs, and metadata endpoint for details."
                        },
                    }
                }
            },
        },
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Requires admin role",
        },
    },
)
def reload_model(
    user: dict = Depends(get_require_admin),
    store: ModelService = Depends(get_model_store),
):
    """Force a manifest refresh and model reload from artifact storage.

    ## Parameters
    - **user** (`dict`): Authenticated admin payload.
    - **store** (`ModelService`): Model service to perform reload.

    ## Returns
    - **dict**: Confirmation message after reload attempt.
    """
    store.load()  # Force reload the model
    return {
        "message": "Model reloaded process completed. Note: models may not have updated, if the process failed. Check logs, and metadata endpoint for details."
    }
