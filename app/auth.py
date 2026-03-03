import os
import time
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import FastAPI, Depends
from app import schemas


APP_JWT_ALG = "HS256"
APP_JWT_TTL_MIN = int(os.environ["APP_JWT_EXP_DELTA_MINUTES"])
APP_JWT_SECRET = os.environ["APP_JWT_SECRET"]


def issue_app_jwt(email: str, role: str) -> str:
    """ Issue a JWT for the given user email and role. 
    
    The token will be valid for a duration defined by APP_JWT_TTL_MIN.
    
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
        "sub": email, # "sub" = subject (the user identifier in your app).
        "role": role, # App role used by protected endpoints.
        "iat": now, # "iat" = issued-at timestamp.
        "exp": now + APP_JWT_TTL_MIN * 60, # "exp" = expiration timestamp.
        "iss": "my-finance-api", # Issuer and audience are can seperate mutliple auth calls to the same oAuth2 provider.
        "aud": "my-finance-api-users",
    }
    return jwt.encode(payload, APP_JWT_SECRET, algorithm=APP_JWT_ALG)


security = HTTPBearer() # HTTPBearer extracts `Authorization: Bearer <token>`.
def require_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """ Dependency function to require a valid JWT for protected endpoints.
    
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
    token = creds.credentials
    try:
        payload = jwt.decode(
            token,
            APP_JWT_SECRET,
            algorithms=[APP_JWT_ALG],
            audience="my-finance-api-users",
            issuer="my-finance-api",
        )
    except JWTError:
        raise schemas.CustomHTTPException(status_code=401, error_code=schemas.ErrorCode.UNAUTHORIZED, message="Invalid or expired token")
    
    return payload


def require_role(role: str):
    """ Dependency factory to require a specific role in the JWT claims for protected endpoints.

    This function returns a dependency that checks if 
    the decoded JWT payload contains the required role.

    Raises
    ------
    HTTPException
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
            raise schemas.CustomHTTPException(status_code=403, error_code=schemas.ErrorCode.FORBIDDEN, message=f"Forbidden - Requires {role} role")
        return payload
    return _checker


# --------------- Dependency instances for endpoints ---------------
require_admin = require_role("admin")