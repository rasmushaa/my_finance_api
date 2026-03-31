"""API router module.

This module defines the main API router and includes all sub-routers for different
endpoint groups (e.g., model, data, auth), and can be used directly in the main
application.
"""

from .auth import router as auth_router
from .categories import router as categories_router
from .health import router as health_router
from .io import router as io_router
from .model import router as model_router

routers = [
    health_router,
    model_router,
    categories_router,
    auth_router,
    io_router,
]
