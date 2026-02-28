from functools import lru_cache
from app.model_store import ModelStore

@lru_cache
def get_model_store() -> ModelStore:
    return ModelStore()