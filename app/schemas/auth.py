from pydantic import BaseModel, Field


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

    ## Attributes
    - **encoded_token** (str): The JWT token that can be used for authenticating subsequent requests to the API.
    - **token_type** (str): The type of the token, typically "Bearer".
    - **user_name** (str): The name of the authenticated user, extracted from their Google profile.
    - **user_picture_url** (str): The URL of the authenticated user's profile photo, extracted from their Google profile.
    """

    encoded_token: str = Field(
        ..., description="The JWT token for authenticating API requests"
    )
    token_type: str = Field(
        ..., description="The type of the token, typically 'Bearer'"
    )
    user_name: str = Field(
        ..., description="Name of the authenticated user from their Google profile"
    )
    user_picture_url: str = Field(
        ...,
        description="URL of the authenticated user's profile picture from their Google profile",
    )
