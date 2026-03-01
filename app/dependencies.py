from app.model_store import ModelStore
from typing import Optional

# Global singleton instance
_model_store_instance: Optional[ModelStore] = None

def get_model_store() -> ModelStore:
    """Get the singleton ModelStore instance.
    
    This function maintains compatibility with FastAPI's dependency_overrides
    pattern used in testing, while providing proper singleton management
    for the async ModelStore.
    """
    global _model_store_instance
    if _model_store_instance is None:
        _model_store_instance = ModelStore()
    return _model_store_instance

def create_model_store() -> ModelStore:
    """Factory function to create a new ModelStore instance.
    
    Used primarily for testing to create fresh instances.
    """
    return ModelStore()