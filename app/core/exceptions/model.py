from .base import AppError, ErrorCodes


class ModelNotAvailableError(AppError):
    def __init__(self, details: dict = {}):
        super().__init__(
            status_code=503,
            code=ErrorCodes.ML_MODEL.value,
            message="Model has not been loaded yet. Please try again later.",
            details=details,
        )


class ModelFileNotFoundError(AppError):
    def __init__(self, details: dict = {}):
        super().__init__(
            status_code=500,
            code=ErrorCodes.ML_MODEL.value,
            message="Model file not found. Please check the model artifacts path.",
            details=details,
        )


class ModelInputError(AppError):
    def __init__(self, details: dict = {}):
        super().__init__(
            status_code=400,
            code=ErrorCodes.ML_MODEL.value,
            message="Invalid input features provided for prediction.",
            details=details,
        )
