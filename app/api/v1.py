"""API verions router module.

This module defines the API router for version <N> of the API, which includes all the
endpoint groups (e.g., model, data, auth) under the /app/v<N> prefix.

The main module (app/main.py) must include all version router collections to be
accessible in the application.
"""

from fastapi import APIRouter

from .routers.assets import router as assets_router
from .routers.auth import router as auth_router
from .routers.health import router as health_router
from .routers.model import router as model_router
from .routers.transactions import router as transactions_router

router = APIRouter(prefix="/app/v1")

router.include_router(health_router)
router.include_router(model_router)
router.include_router(auth_router)
router.include_router(transactions_router)
router.include_router(assets_router)
