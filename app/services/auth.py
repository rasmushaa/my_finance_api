"""Authentication service following DI container pattern."""

import os
import time
from typing import Dict, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app import schemas


class AuthService:
    """Authentication service for JWT token management and validation.

    This service handles JWT token issuance and validation, providing role-based access
    control for API endpoints.
    """

    def __init__(
        self,
        jwt_secret: Optional[str] = None,
        jwt_ttl_minutes: Optional[int] = None,
        jwt_algorithm: str = "HS256",
    ):
        """Initialize AuthService with JWT configuration.

        Parameters
        ----------
        jwt_secret : str, optional
            JWT secret key. Defaults to APP_JWT_SECRET environment variable.
        jwt_ttl_minutes : int, optional
            JWT time-to-live in minutes. Defaults to APP_JWT_EXP_DELTA_MINUTES environment variable.
        jwt_algorithm : str
            JWT algorithm to use for signing/verification. Defaults to HS256.
        """
        self.jwt_secret = jwt_secret or os.environ["APP_JWT_SECRET"]
        self.jwt_ttl_minutes = jwt_ttl_minutes or int(
            os.environ["APP_JWT_EXP_DELTA_MINUTES"]
        )
        self.jwt_algorithm = jwt_algorithm
        self.issuer = "my-finance-api"
        self.audience = "my-finance-api-users"

        # HTTPBearer for extracting Authorization header
        self.security = HTTPBearer()

    def issue_jwt(self, email: str, role: str) -> str:
        """Issue a JWT for the given user email and role.

        The token will be valid for a duration defined by jwt_ttl_minutes.

        Parameters
        ----------
        email : str
            The email of the user for whom the token is being issued.
        role : str
            The role of the user (e.g., "user", "admin") to be included in the token claims.

        Returns
        -------
        str
            A JWT token as a string.
        """
        now = int(time.time())
        payload = {
            "sub": email,  # "sub" = subject (the user identifier in your app).
            "role": role,  # App role used by protected endpoints.
            "iat": now,  # "iat" = issued-at timestamp.
            "exp": now + self.jwt_ttl_minutes * 60,  # "exp" = expiration timestamp.
            "iss": self.issuer,  # Issuer and audience can separate multiple auth calls to the same oAuth2 provider.
            "aud": self.audience,
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def validate_jwt(self, token: str) -> Dict:
        """Validate and decode a JWT token.

        Parameters
        ----------
        token : str
            The JWT token to validate.

        Returns
        -------
        Dict
            The decoded JWT payload containing user information and claims.

        Raises
        ------
        CustomHTTPException
            If the token is invalid, expired, or malformed.
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
                audience=self.audience,
                issuer=self.issuer,
            )
            return payload
        except JWTError:
            raise schemas.CustomHTTPException(
                status_code=401,
                error_code=schemas.ErrorCode.UNAUTHORIZED,
                message="Invalid or expired token",
            )

    def validate_role(self, payload: Dict, required_role: str) -> Dict:
        """Validate that a JWT payload contains the required role.

        Parameters
        ----------
        payload : Dict
            The decoded JWT payload.
        required_role : str
            The required role that must be present in the JWT claims.

        Returns
        -------
        Dict
            The payload if role validation passes.

        Raises
        ------
        CustomHTTPException
            If the payload does not contain the required role.
        """
        if payload.get("role") != required_role:
            raise schemas.CustomHTTPException(
                status_code=403,
                error_code=schemas.ErrorCode.FORBIDDEN,
                message=f"Forbidden - Requires {required_role} role",
            )
        return payload

    def create_user_dependency(self):
        """Create a FastAPI dependency for user authentication.

        Returns
        -------
        function
            A dependency function that validates JWT tokens.
        """

        def require_user(
            creds: HTTPAuthorizationCredentials = Depends(self.security),
        ) -> Dict:
            """Dependency function to require a valid JWT for protected endpoints.

            This function decodes the JWT and returns its payload if valid.

            Raises
            ------
            HTTPException
                If the token is missing, invalid, or expired, a 401 Unauthorized error is raised

            Parameters
            ----------
            creds : HTTPAuthorizationCredentials
                The credentials extracted from the Authorization header by HTTPBearer.

            Returns
            -------
            dict
                The decoded JWT payload containing user information and claims.
            """
            return self.validate_jwt(creds.credentials)

        return require_user

    def create_role_dependency(self, role: str):
        """Create a FastAPI dependency for role-based access control.

        Parameters
        ----------
        role : str
            The required role for access.

        Returns
        -------
        function
            A dependency function that validates both JWT and role.
        """
        require_user = self.create_user_dependency()

        def require_role(payload: Dict = Depends(require_user)) -> Dict:
            return self.validate_role(payload, role)

        return require_role

    def create_admin_dependency(self):
        """Create a FastAPI dependency for admin access control.

        Returns
        -------
        function
            A dependency function that requires admin role.
        """
        return self.create_role_dependency("admin")
