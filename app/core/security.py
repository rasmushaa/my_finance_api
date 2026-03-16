from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.container import container
from app.core.exceptions.auth import MissingBearerTokenError, UserNotAuthorizedError

security = HTTPBearer(
    auto_error=False
)  # HTTPBearer extracts `Authorization: Bearer <token>`


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Dependency function to require a valid JWT for protected endpoints.

    This function decodes the JWT and returns its payload if valid.

    Raises
    ------
    AppError
        If the token is missing, invalid, or expired, a 401 Unauthorized error is raised

    Parameters
    ----------
    creds : HTTPAuthorizationCredentials | None
        The credentials extracted from the Authorization header by HTTPBearer.
        Can be None if no Authorization header is present.

    Returns
    -------
    dict
        The decoded JWT payload containing user information and claims.
    """
    # Check if credentials are provided
    if not creds:
        raise MissingBearerTokenError()

    token = creds.credentials
    payload = container.resolve("jwt_service").decode_jwt(token)
    return payload


def require_role(role: str):
    """Dependency factory to require a specific role in the JWT claims for protected
    endpoints.

    This function returns a dependency that checks if
    the decoded JWT payload contains the required role.

    Raises
    ------
    AppError
        If the JWT is valid but does not contain the required role, a 403 Forbidden error is raised.

    Parameters
    ----------
    role : str
        The required role (e.g., "admin") that must be present in the JWT claims for access to the endpoint.

    Returns
    -------
    function
        A dependency function that can be used with FastAPI's Depends to enforce role-based access control on endpoints.
    """

    def _checker(payload: dict = Depends(require_user)) -> dict:
        if payload.get("role") != role:
            raise UserNotAuthorizedError()
        return payload

    return _checker
