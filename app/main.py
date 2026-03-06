import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app import schemas
from app.auth import require_admin, require_login
from app.services.categories import CategoriesService
from app.services.container import (
    get_categories_service,
    get_model_store,
    get_services_requiring_shutdown,
    get_services_requiring_startup,
)
from app.services.model_store import ModelLoadingStatus, ModelStore
from app.setup_logging import setup_logging

setup_logging(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ---------------------------- Application Lifespan ---------------------------
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


app = FastAPI(title="MyFinance ML API", lifespan=lifespan)


# --------------------------- Health Check Endpoint ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------- Model Endpoints ---------------------------
@app.post(
    "/model/predict",
    response_model=schemas.PredictResponse,
    responses={
        400: {
            "model": schemas.ErrorResponse,
            "description": "Bad Request - Invalid input features",
        },
        503: {
            "model": schemas.ErrorResponse,
            "description": "Service Unavailable - Model not ready",
        },
    },
)
def predict(
    request: schemas.PredictRequest,
    payload: dict = Depends(require_login),
    store: ModelStore = Depends(get_model_store),
):
    # Check if model is ready before making predictions
    if not store.is_ready:
        status_msg = {
            ModelLoadingStatus.NOT_STARTED: "Model loading has not started",
            ModelLoadingStatus.LOADING: "Models are still loading, please try again shortly",
        }
        raise schemas.CustomHTTPException(
            status_code=503,
            error_code=schemas.ErrorCode.MODEL_NOT_READY,
            message=status_msg.get(
                store.status, "Model is not ready for unknown reasons"
            ),
            details={"model_status": store.status.value},
        )

    df = request.to_dataframe()
    preds = store.predict(df)
    return schemas.PredictResponse(predictions=preds)


@app.get(
    "/model/metadata",
    response_model=schemas.ModelMetadataResponse,
    responses={
        403: {
            "model": schemas.ErrorResponse,
            "description": "Forbidden - Requires admin role",
        },
        503: {
            "model": schemas.ErrorResponse,
            "description": "Service Unavailable - Model not ready",
        },
    },
)
def get_model_metadata(
    payload: dict = Depends(require_admin), store: ModelStore = Depends(get_model_store)
):
    # Check if model is ready before making predictions
    if not store.is_ready:
        status_msg = {
            ModelLoadingStatus.NOT_STARTED: "Model loading has not started",
            ModelLoadingStatus.LOADING: "Models are still loading, please try again shortly",
        }
        raise schemas.CustomHTTPException(
            status_code=503,
            error_code=schemas.ErrorCode.MODEL_NOT_READY,
            message=status_msg.get(
                store.status, "Model is not ready for unknown reasons"
            ),
            details={"model_status": store.status.value},
        )
    return schemas.ModelMetadataResponse(**store.metadata)


@app.get(
    "/model/status",
    response_model=schemas.ModelStatusResponse,
    responses={
        403: {
            "model": schemas.ErrorResponse,
            "description": "Forbidden - Requires admin role",
        }
    },
)
def get_model_status(
    payload: dict = Depends(require_login), store: ModelStore = Depends(get_model_store)
):
    response = {
        "status": store.status.value,
        "is_ready": store.is_ready,
        "error_message": store.error_message or "",
    }
    return schemas.ModelStatusResponse(**response)


# -------------------------- Data Endpoints --------------------------
@app.get("/data/categories/expenditure", response_model=schemas.CategoriesResponse)
def get_expenditure_categories(
    payload: dict = Depends(require_login),
    categories_service: CategoriesService = Depends(get_categories_service),
):
    categories_list = categories_service.get_expenditure_categories()
    return schemas.CategoriesResponse(categories=categories_list)


@app.get("/data/categories/asset", response_model=schemas.CategoriesResponse)
def get_asset_categories(
    payload: dict = Depends(require_login),
    categories_service: CategoriesService = Depends(get_categories_service),
):
    categories_list = categories_service.get_asset_categories()
    return schemas.CategoriesResponse(categories=categories_list)
