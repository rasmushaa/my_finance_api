"""Administrative endpoints for file-type registry management."""

import logging

from fastapi import APIRouter, Depends

from app.api.dependencies import get_file_types_service, get_require_admin
from app.schemas.error import ErrorResponse
from app.schemas.filetypes import (
    FileTypeAppendRequest,
    FileTypeDeleteRequest,
    FileTypeListResponse,
)
from app.services.file_types import FileTypesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filetypes", tags=["Transactions - File Types"])


# -- List types --------------------------------
@router.get(
    "/list",
    responses={
        200: {
            "model": FileTypeListResponse,
            "description": "List of supported file types",
        },
        400: {"model": ErrorResponse, "description": "Error retrieving file types"},
    },
)
def list_filetypes(
    file_types_service: FileTypesService = Depends(get_file_types_service),
    user: dict = Depends(get_require_admin),
):
    """List the supported file types that are registered in the database.

    ## Parameters
    - **file_types_service** (`FileTypesService`): Service that reads registered schemas.
    - **user** (`dict`): Authenticated admin payload.

    ## Returns
    - **FileTypeListResponse**: File-type rows ordered by newest registration first.
    """
    filetypes_df = file_types_service.list_filetypes()
    return FileTypeListResponse(filetypes=filetypes_df.to_dict(orient="records"))


# -- Register new --------------------------------
@router.post(
    "/register",
    responses={
        200: {
            "description": "File type registered successfully",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "example": {"message": "File type registered successfully"},
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Invalid file type information"},
    },
)
def register_filetype(
    payload: FileTypeAppendRequest,
    file_types_service: FileTypesService = Depends(get_file_types_service),
    user: dict = Depends(get_require_admin),
):
    """Register a new input CSV schema mapping for transformation.

    ## Parameters
    - **payload** (`FileTypeAppendRequest`): File type mapping definition.
    - **file_types_service** (`FileTypesService`): File type registration service.
    - **user** (`dict`): Authenticated admin payload.

    ## Returns
    - **dict**: Success message with HTTP 200.
    """
    file_types_service.add_filetype_to_database(**payload.model_dump())
    return {"message": "File type registered successfully"}


# -- Delete existing --------------------------------
@router.post(
    "/delete",
    responses={
        200: {
            "description": "File type deleted successfully",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "example": {
                            "message": "File type deleted successfully: my_bank.csv"
                        },
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "File type not found"},
    },
)
def delete_filetype(
    payload: FileTypeDeleteRequest,
    file_types_service: FileTypesService = Depends(get_file_types_service),
    user: dict = Depends(get_require_admin),
):
    """Soft-delete a registered file type by file name.

    ## Parameters
    - **payload** (`FileTypeDeleteRequest`): File type delete request.
    - **file_types_service** (`FileTypesService`): File type deletion service.
    - **user** (`dict`): Authenticated admin payload.

    ## Returns
    - **dict**: Success message with deleted file name.
    """
    file_types_service.delete_filetype_from_database(payload.file_name)
    return {"message": f"File type deleted successfully: {payload.file_name}"}
