"""Health check endpoint router module.

This module defines the API router for health check endpoints, which are used to verify
that the application is running and responsive.
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
def health(request: Request):
    """Return a lightweight liveness signal for the API service.

    ## Returns
    - **dict**: Static `{ \"status\": \"ok\" }` payload when service is reachable.
    """
    return {"status": "ok"}
