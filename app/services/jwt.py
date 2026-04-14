"""JWT authentication service."""

import logging
import time
from typing import Protocol, Tuple

from jose import jwt

from app.core.errors.auth import (
    ExpiredIdTokenError,
    InvalidIdTokenError,
    UserNotFoundError,
)
from app.core.settings import JWTConfig

logger = logging.getLogger(__name__)


class UserClientProtocol(Protocol):
    """Protocol for user lookup dependencies used by JWT service."""

    def get_user_by_email(self, email: str) -> dict:
        """Return user record for provided email, or empty dict when missing."""
        ...


class AppJwtService:
    """Issue and validate application JWT tokens."""

    def __init__(
        self,
        user_client: UserClientProtocol,
        config: JWTConfig | None = None,
    ):
        """Initialize the JWT service.

        Parameters
        ----------
        user_client : UserClientProtocol
            Dependency used to resolve user role by email.
        config : JWTConfig | None
            Runtime JWT configuration. Loaded from env when omitted.
        """
        self.user_client = user_client
        self.__config = config or JWTConfig.from_env()

    @property
    def config(self) -> JWTConfig:
        """Public property to access JWT configuration."""
        return self.__config

    def authenticate(self, email: str) -> Tuple[str, str]:
        """Authenticate user and issue app JWT.

        The email is matched against the user database.
        Rate limiting is handled at the router level using the email as key.

        Parameters
        ----------
        email : str
            The email of the user to authenticate.

        Returns
        -------
        Tuple[str, str]
            Tuple of encoded token and resolved role.
        """
        user = self.user_client.get_user_by_email(email)
        if not user:
            raise UserNotFoundError()

        token = self.__issue_app_jwt(email=email, role=user["role"])
        return token, user["role"]

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

        except jwt.ExpiredSignatureError:
            raise ExpiredIdTokenError()

        except jwt.JWTError:
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
