from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.dependencys import get_asset_service, get_require_user
from app.schemas.assets import AssetUploadRequest
from app.services.assets import AssetService

router = APIRouter(prefix="/assets", tags=["User IO"])


@router.post(
    "/upload",
    response_model=AssetUploadRequest,
    responses={
        200: {
            "description": "Successfully uploaded the asset",
        },
    },
)
def upload_asset(
    payload: AssetUploadRequest,
    asset_service: AssetService = Depends(get_asset_service),
    user: dict = Depends(get_require_user),
):
    """Upload a user asset snapshot for a reporting date.

    ## Parameters
    - **payload** (`AssetUploadRequest`): Asset values and reporting date.
    - **asset_service** (`AssetService`): Service for persisting asset rows.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **Response**: Success message with HTTP 200.
    """
    asset_service.upload_assets(**payload.model_dump(), user_email=user["sub"])
    return Response(status_code=200, content="Asset uploaded successfully")
