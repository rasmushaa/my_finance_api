from fastapi import APIRouter, Depends

from app.api.dependencies.providers import get_google_oauth_service, get_jwt_service
from app.schemas.auth import GoogleCodeExchangeRequest, GoogleCodeExchangeResponse
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService as JWTService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google/code", response_model=GoogleCodeExchangeResponse)
async def auth_google_code(
    request: GoogleCodeExchangeRequest,
    google_oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> GoogleCodeExchangeResponse:
    """Exchange a Google authorization code for an access token and user info.

    This endpoint accepts a Google authorization code obtained from the client-side
    OAuth flow. It uses the GoogleOAuthService to exchange the code for an access token,
    retrieves the user's profile information, and returns a minted JWT for authentication in the application.

    **Parameters:**
    - **request** (GoogleCodeExchangeRequest): The request body containing the authorization code.
    - **google_oauth_service** (GoogleOAuthService): The service used to handle Google OAuth operations.
    - **jwt_service** (JWTService): The service used to handle JWT operations.

    **Returns:**
    - **GoogleCodeExchangeResponse**: The response containing the access token and user info.

    **Raises:**
    - **HTTPException**: If the code exchange fails or if the provided code is invalid.
    """
    info = google_oauth_service.exchange_code_for_id_token(
        request.code, request.redirect_uri
    )

    jwt_token = await jwt_service.auth_with_delay(email=info["sub"])

    return GoogleCodeExchangeResponse(
        access_token=jwt_token,
        token_type="Bearer",
    )
