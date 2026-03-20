"""Health check endpoint router module.

This module defines the API router for health check endpoints, which are used to verify
that the application is running and responsive.
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def health(request: Request):
    return {"status": "ok"}
