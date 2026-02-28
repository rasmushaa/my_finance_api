from fastapi import FastAPI
from fastapi import Depends
from app.schemas import PredictRequest, PredictResponse
from app.model_store import ModelStore
from app.dependencies import get_model_store
from contextlib import asynccontextmanager
import logging
from app.setup_logging import setup_logging

setup_logging(level=logging.DEBUG)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application...")
    store = get_model_store()
    store.load()
    yield
    logger.info("Shutting down application...")


app = FastAPI(title="MyFinance ML API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(
    request: PredictRequest,
    store: ModelStore = Depends(get_model_store)
    ):
    df = request.to_dataframe()

    champion_pred = store.champion_model.predict(df)

    if store.challenger_models:
        for challenger in store.challenger_models:
            challenger.predict(df)

    return PredictResponse(predictions=champion_pred)


@app.get("/model/info")
def get_model_info(
    store: ModelStore = Depends(get_model_store)
    ):
    return store.model_info