from io import StringIO

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.api.dependencys import (
    get_require_admin,
    get_require_user,
    get_transaction_service,
)
from app.schemas.error import ErrorResponse
from app.schemas.transactions import (
    CSVImportRequest,
    CSVImportResponse,
    FileTypeAppendRequest,
    FileTypeDeleteRequest,
    TransactionLabelResponse,
)
from app.services.transactions import TransactionService

router = APIRouter(prefix="/transactions", tags=["User IO"])


# -- Transactions ----------------------------------------------------------------------
@router.get(
    "/labels",
    response_model=TransactionLabelResponse,
    responses={
        200: {
            "model": TransactionLabelResponse,
            "description": "Successfully retrieved transaction labels",
        },
    },
)
def get_transaction_labels(
    transaction_service: TransactionService = Depends(get_transaction_service),
    user: dict = Depends(get_require_user),
):
    labels = transaction_service.get_transaction_labels()
    return TransactionLabelResponse(labels=labels)


@router.post(
    "/transform",
    response_model=CSVImportResponse,
    responses={
        200: {
            "model": CSVImportResponse,
            "description": "Successfully processed the CSV file",
        },
        400: {"model": ErrorResponse, "description": "Invalid input file"},
    },
)
def transform_csv(
    file: UploadFile = File(...),
    transaction_service: TransactionService = Depends(get_transaction_service),
    user: dict = Depends(get_require_user),
):
    # Validate content type using CSVImportRequest contract
    CSVImportRequest(content_type=file.content_type or "")

    # Transform file and run predictions (handled together by TransactionService)
    transformed_df = transaction_service.transform_input_file(file.file)

    # Build and validate response metadata
    output_filename = f"processed_{file.filename}"
    response_meta = CSVImportResponse(
        filename=output_filename,
        row_count=len(transformed_df),
        columns=list(transformed_df.columns),
    )

    # Convert transformed DataFrame back to CSV text for response streaming
    buffer = StringIO()
    transformed_df.to_csv(buffer, index=False)
    csv_text = buffer.getvalue()

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{response_meta.filename}"',
            "X-Row-Count": str(response_meta.row_count),
            "X-Columns": ",".join(response_meta.columns),
        },
    )


@router.post(
    "/upload",
    responses={
        200: {"description": "CSV data appended to table successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid input file or table name",
        },
    },
)
def upload_transactions(
    file: UploadFile = File(...),
    transaction_service: TransactionService = Depends(get_transaction_service),
    user: dict = Depends(get_require_user),
):
    # Validate content type using CSVImportRequest contract
    CSVImportRequest(content_type=file.content_type or "")

    transaction_service.upload_transactions(file.file, user_email=user["sub"])
    return Response(status_code=200, content="CSV data appended to table successfully")


# -- File types ----------------------------------------------------------------------
@router.post(
    "/register-filetype",
    responses={
        200: {"description": "File type registered successfully"},
        400: {"model": ErrorResponse, "description": "Invalid file type information"},
    },
)
def register_filetype(
    payload: FileTypeAppendRequest,
    transaction_service: TransactionService = Depends(get_transaction_service),
    user: dict = Depends(get_require_admin),
):
    transaction_service.add_filetype_to_database(**payload.model_dump())
    return Response(status_code=200, content="File type registered successfully")


@router.post(
    "/delete-filetype",
    responses={
        200: {"description": "File type deleted successfully"},
        400: {"model": ErrorResponse, "description": "File type not found"},
    },
)
def delete_filetype(
    payload: FileTypeDeleteRequest,
    transaction_service: TransactionService = Depends(get_transaction_service),
    user: dict = Depends(get_require_admin),
):
    transaction_service.delete_filetype_from_database(payload.file_name)
    return Response(
        status_code=200, content=f"File type deleted successfully {payload.file_name}"
    )
