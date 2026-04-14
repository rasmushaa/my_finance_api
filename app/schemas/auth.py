"""Authentication API schemas."""

from pydantic import BaseModel, Field


class GoogleCodeExchangeRequest(BaseModel):
    """Request payload for Google OAuth code exchange.

    Attributes
    ----------
    code : str
        Single-use authorization code received from Google OAuth redirect.
    redirect_uri : str
        Redirect URI used when obtaining the authorization code.
    """

    code: str = Field(
        ...,
        description="Single-use Google authorization code from frontend OAuth flow.",
        examples=["4/0AeaYSHC..."],
    )
    redirect_uri: str = Field(
        ...,
        description="Redirect URI used in the original Google OAuth request.",
        examples=["http://localhost:8501"],
    )


class GoogleCodeExchangeResponse(BaseModel):
    """Response payload for successful Google OAuth code exchange.

    Attributes
    ----------
    encoded_jwt_token : str
        Signed API token used in ``Authorization: Bearer <token>`` headers.
    user_name : str
        Display name extracted from verified Google identity payload.
    user_picture_url : str
        Profile image URL extracted from verified Google identity payload.
    user_role : str
        Effective user role from API credentials table (for example ``"admin"`` or
        ``"user"``).
    """

    encoded_jwt_token: str = Field(
        ..., description="The JWT token for authenticating API requests"
    )
    user_name: str = Field(
        ..., description="Name of the authenticated user from their Google profile"
    )
    user_picture_url: str = Field(
        ...,
        description="URL of the authenticated user's profile picture from their Google profile",
    )
    user_role: str = Field(
        ...,
        description="Role of the authenticated user (e.g., 'admin', 'user') used in UI to hide/show admin features which are already protected by backend authorization checks",
    )
