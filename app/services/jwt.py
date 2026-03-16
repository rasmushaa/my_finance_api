import asyncio
import logging
import os
import time
from typing import Protocol

import numpy as np
from jose import jwt

from app.core.exceptions.auth import UserNotFoundError

logger = logging.getLogger(__name__)


APP_JWT_ALG = "HS256"
APP_JWT_TTL_MIN = int(os.environ["APP_JWT_EXP_DELTA_MINUTES"])
APP_JWT_SECRET = os.environ["APP_JWT_SECRET"]


class UserClientProtocol(Protocol):
    def get_user_by_email(self, email: str) -> dict:
        """Protocol method to get user by email.

        Should be implemented by the actual user client.
        """
        ...


class AppJwtService:
    def __init__(self, user_client: UserClientProtocol):
        """Initialize the JWT service.

        Attributes
        ----------
        user_client : UserClientProtocol
            A client that implements the UserClientProtocol for fetching user data.
        __secret_key : str
            The secret key used for signing JWTs, loaded from environment variable.
        __algorithm : str
            The algorithm used for signing JWTs, set to HS256.
        __token_expire_minutes : int
            The expiration time for JWTs in minutes, loaded from environment variable.
        """
        self.user_client = user_client
        self.__secret_key = APP_JWT_SECRET
        self.__algorithm = APP_JWT_ALG
        self.__token_expire_minutes = APP_JWT_TTL_MIN

    async def auth_with_delay(self, email: str) -> str:
        """Authenticate user and issue app JWT.

        The email is matched against the user database.
        If the user is not found,
        a random delay is introduced before raising an exception to mitigate timing attacks.

        Parameters
        ----------
        email : str
            The email of the user to authenticate.

        Returns
        -------
        str
            A JWT token as a string if authentication is successful.
        """
        user = self.user_client.get_user_by_email(email)
        if not user:
            await asyncio.sleep(np.random.uniform(3.0, 6.0))
            raise UserNotFoundError()
        return self.__issue_app_jwt(email=email, role=user["role"])

    def __issue_app_jwt(self, email: str, role: str) -> str:
        """Issue a JWT for the given user email and role.

        The token will be valid for a duration defined by APP_JWT_TTL_MIN.

        Parameters
        ----------
        email : str
            The email of the user for whom the token is being issued.
        role : str
            The role of the user (e.g., "user", "admin") to be included in the token claims.

        Details
        -------
        - sub (subject) claim is set to the user's email, which serves as the unique identifier for the user in the application.
        - role claim is included to facilitate role-based access control in protected endpoints.
        - iat (issued-at) claim is set to the current timestamp, indicating when the token was issued.
        - exp (expiration) claim is set to the current timestamp plus the configured TTL, defining how long the token is valid.
        - iss (issuer) and aud (audience) claims are set to identify the source and intended audience of the token,
          which can help in validating the token in multi-tenant scenarios or when using multiple authentication providers.

        Returns
        -------
        str
            A JWT token as a string.
        """
        now = int(time.time())
        payload = {
            "sub": email,
            "role": role,
            "iat": now,
            "exp": now + self.__token_expire_minutes * 60,
            "iss": "my-finance-api",
            "aud": "my-finance-api-users",
        }
        return jwt.encode(payload, self.__secret_key, algorithm=self.__algorithm)
