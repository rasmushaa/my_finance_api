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
    """Application factory to build FastAPI app with lifecycle hooks."""
    setup_logging(level=logging.INFO)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting up application...")

        # Get services that need startup tasks from container
        startup_services = get_services_requiring_startup()

        # Run startup tasks
        # Note: this used to be async thredads, but Cloud Run (with request based billing) does not process background threads.
        # The Cloud Run has 4min maximum startup time, so all startup tasks must be completed within that time frame.
        for service in startup_services:
            if hasattr(service, "load"):  # Protocol check for load method
                logger.info(f"Loading {service.__class__.__name__}")
                service.load()

        try:
            yield
        finally:
            # Cleanup on shutdown
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
