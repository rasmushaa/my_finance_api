from fastapi import FastAPI, Depends, HTTPException
from app.schemas import PredictRequest, PredictResponse
from app.model_store import ModelStore, ModelLoadingStatus
from app.dependencies import get_model_store
from contextlib import asynccontextmanager
import logging
import asyncio
from app.setup_logging import setup_logging

setup_logging(level=logging.DEBUG)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application...")
    
    # Start background model loading
    store = get_model_store()
    asyncio.create_task(store.load())
    
    yield
    logger.info("Shutting down application...")


# Initialize FastAPI app with lifespan for startup/shutdown events
app = FastAPI(title="MyFinance ML API", lifespan=lifespan)


# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}


# Prediction endpoint
@app.post("/model/predict", response_model=PredictResponse)
def predict(
    request: PredictRequest,
    store: ModelStore = Depends(get_model_store)
    ):
    # Check if model is ready before making predictions
    if not store.is_ready:
        status_msg = {
            ModelLoadingStatus.NOT_STARTED: "Model loading has not started",
            ModelLoadingStatus.LOADING: "Models are still loading, please try again shortly",
        }
        raise HTTPException(
            status_code=503, 
            detail=status_msg.get(store.status, "Models not available")
        )
    
    df = request.to_dataframe()
    preds = store.predict(df)
    return PredictResponse(predictions=preds)


# Model metadata endpoint
@app.get("/model/metadata")
def get_model_metadata(
    store: ModelStore = Depends(get_model_store)
    ):
    if not store.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Model metadata not available until model is ready"
        )
    return store.metadata


# Model status endpoint
@app.get("/model/status")
def get_model_status(
    store: ModelStore = Depends(get_model_store)
    ):
    response = {
        "status": store.status.value,
        "is_ready": store.is_ready,
        "error_message": store.error_message
    }  
    return response