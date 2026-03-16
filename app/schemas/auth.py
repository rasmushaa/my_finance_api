from pydantic import BaseModel


class GoogleCodeExchangeRequest(BaseModel):
    """Pydantic model for the request body of the Google OAuth2 code exchange endpoint.

    This model defines the expected structure of the JSON payload that clients must send
    when exchanging an authorization code for an access token.
    """

    code: str
    redirect_uri: str


class GoogleCodeExchangeResponse(BaseModel):
    """Pydantic model for the response body of the Google OAuth2 code exchange endpoint.

    This model defines the structure of the JSON response that the server will return
    after successfully exchanging an authorization code for an access token.
    """

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str = None  # Optional, may not be present in all responses
