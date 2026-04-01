from .base_error import AppError, ErrorCode


# -- IO errors -------------------------------------------
class UnknownFileTypeError(AppError):
    def __init__(
        self,
        message: str = "Not able to process the file. The file type is not recognized.",
        details: dict = {},
    ):
        super().__init__(
            status_code=400,
            code=ErrorCode.INVALID_INPUT,
            message=message,
            details=details,
        )


class DatabaseQueryError(AppError):
    """Exception raised for errors during Data Manipulation Language (DML) operations.

    This exception is used to indicate that an error occurred while performing DML
    operations such as inserting, updating, or deleting data in the database. The error
    could be due to issues with the input data, constraints violations, or other
    problems that prevent the DML operation from being completed successfully.
    """

    def __init__(
        self,
        message: str = "DML processing error. Please check the input data and try again.",
        details: dict = {},
    ):
        super().__init__(
            status_code=400,
            code=ErrorCode.DATA_PROCESSING_FAILED,
            message=message,
            details=details,
        )


# -- ML model errors -------------------------------------------
class ModelArtifactsError(AppError):
    def __init__(
        self,
        message: str = "Model artifacts are missing or invalid.",
        details: dict = {},
    ):
        super().__init__(
            status_code=500,
            code=ErrorCode.DATA_PROCESSING_FAILED,
            message=message,
            details=details,
        )


class ModelInputError(AppError):
    def __init__(
        self, message: str = "Invalid input features provided.", details: dict = {}
    ):
        super().__init__(
            status_code=400,
            code=ErrorCode.INVALID_INPUT,
            message=message,
            details=details,
        )
