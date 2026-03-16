import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import routers
from app.core.container import (
    get_services_requiring_shutdown,
    get_services_requiring_startup,
)
from app.core.exceptions.base import AppError
from app.core.handlers import app_error_handler
from app.core.setup_logging import setup_logging

setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ---------------------------- Lifespan ---------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application...")

    # Get services that need startup tasks from container
    startup_services = get_services_requiring_startup()

    # Start background tasks for each service
    tasks = []
    for service in startup_services:
        if hasattr(service, "load"):  # Protocol check for load method
            task = asyncio.create_task(service.load())
            tasks.append(task)
            logger.info(f"Started background task for {service.__class__.__name__}")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down application...")
    shutdown_services = get_services_requiring_shutdown()
    for shutdown_service in shutdown_services:
        if hasattr(shutdown_service, "cleanup"):
            await shutdown_service.cleanup()
            logger.info(f"Cleaned up {shutdown_service.__class__.__name__}")


# ---------------------------- Application ---------------------------
app = FastAPI(title="MyFinance ML API", lifespan=lifespan)

# Include all routers from the API router module
for router in routers:
    app.include_router(router)

# Handlers
app.add_exception_handler(AppError, app_error_handler)
