from .base import AppError, ErrorCodes


class UnknownFileTypeError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=400,
            code=ErrorCodes.ML_ERROR.value,
            message="Not able to process the file. The file type is not recognized.",
            details=details,
        )


class DMLError(AppError):
    def __init__(self, details: dict | None = None):
        super().__init__(
            status_code=400,
            code=ErrorCodes.DATA_ERROR.value,
            message="DML processing error. Please check the input data and try again.",
            details=details,
        )
