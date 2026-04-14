"""API version router module.

This module composes all v1 endpoint groups under the `/app/v1` prefix.

Notes
-----
The main application entrypoint (`app/main.py`) includes this router collection.
"""

from fastapi import APIRouter

from .routers.assets import router as assets_router
from .routers.auth import router as auth_router
from .routers.filetypes import router as filetypes_router
from .routers.health import router as health_router
from .routers.model import router as model_router
from .routers.reporting import router as reporting_router
from .routers.transactions import router as transactions_router

router = APIRouter(prefix="/app/v1")

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(model_router)
router.include_router(assets_router)
router.include_router(transactions_router)
router.include_router(filetypes_router)
router.include_router(reporting_router)
