from .base import AppError, ErrorCodes


class ModelArtifactsError(AppError):
    def __init__(self, details: dict = {}):
        super().__init__(
            status_code=500,
            code=ErrorCodes.ML_ERROR.value,
            message="Model artifacts are missing or invalid.",
            details=details,
        )


class ModelInputError(AppError):
    def __init__(self, details: dict = {}):
        super().__init__(
            status_code=400,
            code=ErrorCodes.ML_ERROR.value,
            message="Invalid input features provided.",
            details=details,
        )
