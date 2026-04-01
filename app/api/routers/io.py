from io import StringIO

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.api.dependencies.providers import (
    get_io_service,
    get_require_admin,
    get_require_user,
)
from app.schemas.error import ErrorResponse
from app.schemas.io import (
    CSVImportRequest,
    CSVImportResponse,
    FileTypeAppendRequest,
    FileTypeDeleteRequest,
)
from app.services.io import IOService

router = APIRouter(prefix="/io", tags=["File IO"])


# -- Transactions ----------------------------------------------------------------------
@router.post(
    "/transform-csv",
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
    io_service: IOService = Depends(get_io_service),
    payload: dict = Depends(get_require_user),
):
    # Validate content type using CSVImportRequest contract
    CSVImportRequest(content_type=file.content_type or "")

    # Transform file and run predictions (handled together by IOService)
    transformed_df = io_service.transform_input_file(file.file)

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
    "/append-transactions",
    responses={
        200: {"description": "CSV data appended to table successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid input file or table name",
        },
    },
)
def append_transactions(
    file: UploadFile = File(...),
    io_service: IOService = Depends(get_io_service),
    payload: dict = Depends(get_require_user),
):
    # Validate content type using CSVImportRequest contract
    CSVImportRequest(content_type=file.content_type or "")

    io_service.append_transactions(file.file, user_email=payload["sub"])
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
    io_service: IOService = Depends(get_io_service),
    user: dict = Depends(get_require_admin),
):
    io_service.add_filetype_to_database(**payload.model_dump())
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
    io_service: IOService = Depends(get_io_service),
    user: dict = Depends(get_require_admin),
):
    io_service.delete_filetype_from_database(payload.file_name)
    return Response(
        status_code=200, content=f"File type deleted successfully {payload.file_name}"
    )
