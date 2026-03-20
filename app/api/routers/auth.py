import logging

from fastapi import APIRouter, Depends

from app.api.dependencies.providers import get_google_oauth_service, get_jwt_service
from app.core.exceptions.auth import (
    AuthRateLimitExceededError,
    CodeExchangeError,
    InvalidIdTokenError,
    MissingEmailError,
    MissingIdTokenError,
    UserNotFoundError,
)
from app.core.rate_limiter import EmailRateLimiter
from app.schemas.auth import GoogleCodeExchangeRequest, GoogleCodeExchangeResponse
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService as JWTService

logger = logging.getLogger(__name__)

# Map all auth related failures to hide specific details from potential attackers
AUTH_FAILURE_EXCEPTIONS = (
    CodeExchangeError,
    MissingIdTokenError,
    InvalidIdTokenError,
    MissingEmailError,
    UserNotFoundError,
)

# User can try to log once to prevent spam to database, but this is still enough for legitimate users
_auth_limiter = EmailRateLimiter(max_requests=1, window_seconds=60)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google/code", response_model=GoogleCodeExchangeResponse)
def auth_google_code(
    request: GoogleCodeExchangeRequest,
    google_oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> GoogleCodeExchangeResponse:
    """Exchange a Google authorization code for an access token and user info.

    This endpoint accepts a Google authorization code obtained from the client-side
    OAuth flow. It uses the GoogleOAuthService to exchange the code for an access token,
    retrieves the user's profile information, and returns a minted JWT for authentication in the application.

    Rate limited by email (from Google's verified ID token) instead of by IP,
    since the Streamlit frontend proxies all requests through a single Cloud Run IP.

    ## Parameters
    - **request** (GoogleCodeExchangeRequest): The request body containing the authorization code.
    - **google_oauth_service** (GoogleOAuthService): The service used to handle Google OAuth operations.
    - **jwt_service** (JWTService): The service used to handle JWT operations.

    ## Returns
    - **GoogleCodeExchangeResponse**: The response containing the access token and user info.

    ## Raises
    - **AuthRateLimitExceededError**: If the email has exceeded the rate limit (429).
    - **CodeExchangeError**: For any possible failure during the code exchange process,
        including invalid code, token exchange failure, or user not found.
    """
    try:
        info = google_oauth_service.exchange_code_for_id_token(
            request.code, request.redirect_uri
        )

        email = info["email"]  # Rate limit by validated google email
        if not _auth_limiter.check(email):
            logger.warning(f"Auth rate limit exceeded for email: {email}")
            raise AuthRateLimitExceededError(
                cooldown_seconds=_auth_limiter.window_seconds
            )

        jwt_token = jwt_service.authenticate(email=email)

    except (
        AUTH_FAILURE_EXCEPTIONS
    ):  # Hide specific failure reasons to prevent information leakage
        raise CodeExchangeError()

    return GoogleCodeExchangeResponse(
        encoded_token=jwt_token,
        token_type="Bearer",
        user_name=info.get("name", ""),
        user_picture_url=info.get("picture", ""),
    )
