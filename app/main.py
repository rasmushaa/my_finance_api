"""Application entrypoint and FastAPI app factory.

This module wires lifecycle hooks, router registration, and global exception handling.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.container import (
    get_services_requiring_shutdown,
    get_services_requiring_startup,
)
from app.core.errors.base_error import AppError
from app.core.errors.handlers import app_error_handler
from app.core.setup_logging import setup_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance.

    The factory configures:
    - logging setup
    - startup lifecycle loading of services that expose ``load()``
    - shutdown lifecycle cleanup for services that expose ``cleanup()``
    - v1 router registration
    - global ``AppError`` exception handling

    Returns
    -------
    FastAPI
        Fully configured FastAPI application.
    """
    setup_logging(level=logging.INFO)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifecycle context manager."""
        logger.info("Starting up application...")

        # Resolve startup-capable services from container.
        startup_services = get_services_requiring_startup()

        # Run startup tasks synchronously.
        # Cloud Run request-based billing does not guarantee background thread progress
        # while idle, so loading is done during startup to make model availability explicit.
        for service in startup_services:
            if hasattr(service, "load"):
                logger.info(f"Loading {service.__class__.__name__}")
                service.load()

        try:
            yield
        finally:
            # Run shutdown cleanup hooks when present.
            logger.info("Shutting down application...")
            shutdown_services = get_services_requiring_shutdown()
            for shutdown_service in shutdown_services:
                if hasattr(shutdown_service, "cleanup"):
                    logger.info(f"Cleaning up {shutdown_service.__class__.__name__}")
                    shutdown_service.cleanup()

    application = FastAPI(title="MyFinance ML API", lifespan=lifespan)
    application.include_router(v1_router)
    application.add_exception_handler(AppError, app_error_handler)
    return application


# -- Application ---------------------------------------------
app = create_app()
