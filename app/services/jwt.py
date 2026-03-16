import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from jose import jwt

from app.core.exceptions.auth import InvalidIdTokenError, UserNotFoundError

logger = logging.getLogger(__name__)


class UserClientProtocol(Protocol):
    def get_user_by_email(self, email: str) -> dict:
        """Protocol method to get user by email.

        Should be implemented by the actual user client.
        """
        ...


@dataclass(frozen=True)
class JWTConfig:
    """Readonly configuration for JWT operations."""

    algorithm: str = "HS256"

    @property
    def secret(self) -> str:
        """Get JWT secret from environment variable."""
        return os.environ["APP_JWT_SECRET"]

    @property
    def token_expire_minutes(self) -> int:
        """Get JWT expiration time from environment variable.

        Details
        -------
        Using the key method mandates to have placed the variable at runtime,
        which does not allow to run profcution with default values.
        However, this requieres to inlclude the variables in every test module,
        which may not even use the JWT service directly,
        but only through the security dependencies.
        """
        return int(os.environ["APP_JWT_EXP_DELTA_MINUTES"])


class AppJwtService:
    def __init__(self, user_client: UserClientProtocol):
        """Initialize the JWT service.

        Attributes
        ----------
        user_client : UserClientProtocol
            A client that implements the UserClientProtocol for fetching user data.
        __config : JWTConfig
            The configuration object containing JWT settings.
        """
        self.user_client = user_client
        self.__config = JWTConfig()

    @property
    def config(self) -> JWTConfig:
        """Public property to access JWT configuration."""
        return self.__config

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

    def decode_jwt(self, token: str) -> dict:
        """Decode a JWT token and return its payload.

        Parameters
        ----------
        token : str
            The JWT token to decode.

        Returns
        -------
        dict
            The decoded JWT payload containing user information and claims.
        """
        try:
            payload = jwt.decode(
                token,
                self.__config.secret,
                algorithms=[self.__config.algorithm],
                audience="my-finance-api-users",
                issuer="my-finance-api",
            )
            return payload
        except jwt.JWTError as e:
            raise InvalidIdTokenError()

    def __issue_app_jwt(self, email: str, role: str) -> str:
        """Issue a JWT for the given user email and role.

        The token will be valid for a duration defined by jwt_config.token_expire_minutes.

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
            "exp": now + self.__config.token_expire_minutes * 60,
            "iss": "my-finance-api",
            "aud": "my-finance-api-users",
        }
        return jwt.encode(
            payload, self.__config.secret, algorithm=self.__config.algorithm
        )
