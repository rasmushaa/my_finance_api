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
    asset_service.upload_assets(**payload.model_dump(), user_email=user["sub"])
    return Response(status_code=200, content="Asset uploaded successfully")
