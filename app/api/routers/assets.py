"""User asset snapshot endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.dependencies import get_asset_service, get_require_user
from app.schemas.assets import AssetEntryRequest
from app.services.assets import AssetService

router = APIRouter(prefix="/assets", tags=["Assets - User IO"])


# -- Upload ----------------------------------------------------------------------
@router.post(
    "/upload",
    responses={
        200: {
            "description": "Successfully uploaded the asset",
        },
    },
)
def upload_asset(
    payload: AssetEntryRequest,
    asset_service: AssetService = Depends(get_asset_service),
    user: dict = Depends(get_require_user),
):
    """Upload a user asset snapshot for a reporting date.

    ## Parameters
    - **payload** (`AssetEntryRequest`): Asset values and reporting date.
    - **asset_service** (`AssetService`): Service for persisting asset rows.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **Response**: Plain-text success response with HTTP 200.
    """
    asset_service.upload_assets(**payload.model_dump(), user_email=user["sub"])
    return Response(status_code=200, content="Asset uploaded successfully")


# -- Getters ----------------------------------------------------------------------
@router.get(
    "/latest-entry",
    response_model=AssetEntryRequest,
    responses={
        200: {
            "description": "Successfully retrieved the latest asset entry for the user.",
        },
    },
)
def get_latest_entry_stats(
    asset_service: AssetService = Depends(get_asset_service),
    user: dict = Depends(get_require_user),
):
    """Get the most recent full asset snapshot for the authenticated user.

    ## Parameters
    - **asset_service** (`AssetService`): Service for querying asset data.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **AssetEntryRequest**: Latest snapshot values mapped into API schema fields.
    """
    result = asset_service.get_latest_entry_stats(user_email=user["sub"])
    return AssetEntryRequest(**result)
