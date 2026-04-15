"""Transaction ingestion and transformation endpoints."""

import hashlib
import logging
from io import StringIO

import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response

from app.api.dependencies import (
    get_db_client,
    get_model_store,
    get_require_user,
    get_transaction_service,
)
from app.schemas.error import ErrorResponse
from app.schemas.transactions import (
    CSVImportRequest,
    CSVImportResponse,
    TransactionLabelResponse,
)
from app.services.model import ModelService
from app.services.transactions import TransactionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions - User IO"])


# -- Labels  ----------------------------------
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
    """Return supported transaction labels and descriptions.

    ## Parameters
    - **transaction_service** (`TransactionService`): Service providing label mapping.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **TransactionLabelResponse**: Label dictionary used by clients/UI.
    """
    labels = transaction_service.get_transaction_labels()
    return TransactionLabelResponse(labels=labels)


# -- Latest Entry --------------------------------
@router.get(
    "/latest-entry",
    responses={
        200: {
            "description": "Successfully retrieved the date of the latest transaction entry for the user.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"latest_entry_date": {"type": "string"}},
                        "example": {"latest_entry_date": "2024-01-31"},
                    }
                }
            },
        },
    },
)
def get_latest_entry_date(
    transaction_service: TransactionService = Depends(get_transaction_service),
    user: dict = Depends(get_require_user),
):
    """Get the date of the latest transaction entry for the user.

    ## Parameters
    - **transaction_service** (`TransactionService`): Service for querying transaction data.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **JSONResponse**: JSON object containing the latest entry date.
    """
    latest_date = transaction_service.get_latest_entry_date(user_email=user["sub"])
    return JSONResponse(status_code=200, content={"latest_entry_date": latest_date})


# -- Transform --------------------------------
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
    model_store: ModelService = Depends(get_model_store),
    db_client=Depends(get_db_client),
    user: dict = Depends(get_require_user),
):
    """Normalize an input CSV and attach predicted transaction categories.

    ## Parameters
    - **file** (`UploadFile`): Input CSV file.
    - **transaction_service** (`TransactionService`): CSV transform and prediction service.
    - **model_store** (`ModelService`): Model service used for inference.
    - **db_client**: Database client for logging predictions and metadata.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **Response**: CSV attachment containing normalized transactions with predicted `Category`
      and generated `RowProcessingID` values.

    ## Raises
    - **InputValidationError**: If uploaded content type is invalid.
    - **UnknownFileTypeError**: If schema is not registered in known file types.
    """
    # Validate content type using CSVImportRequest contract
    CSVImportRequest(content_type=file.content_type or "")

    # Transform file into expected format (CSV normalization only)
    transformed_df = transaction_service.transform_input_file(file.file)

    # Create a unique processing ID per row based on normalized values and current timestamp.
    hash_id = transformed_df.apply(
        lambda row: int.from_bytes(
            hashlib.sha256(str(tuple(row) + (pd.Timestamp.now(),)).encode()).digest()[
                :8
            ],
            "big",
        )
        & 0x7FFFFFFFFFFFFFFF,
        axis=1,
    ).to_list()

    def run_inference_and_log(model, df) -> list[str]:
        """Run model inference and persist prediction metadata.

        Falls back to null predictions for unavailable or failing models to avoid
        interrupting user-facing transformation flows.
        """
        # The model store has not finished loading yet.
        if model is None:
            logger.warning(
                "Model store returned None model. The model is not 'failing' per se, but it is not available for inference. Returning empty predictions."
            )
            return [None] * len(df)

        # Guard inference errors so we still return transformed output.
        try:
            preds = model.predict(df)
        except Exception as e:
            logger.error(
                f"Error during model inference for {model.metadata.get('name', 'unknown')} v({model.metadata.get('version', 'unknown')}): {e}"
            )
            preds = [None] * len(df)

        # Log predictions and model metadata to the database
        values = {
            "PredictedCategory": preds,
            "ModelName": model.metadata.get("name", "unknown"),
            "ModelAlias": (
                ",".join(model.metadata.get("aliases", []))
                if isinstance(model.metadata.get("aliases"), list)
                else model.metadata.get("aliases", "unknown")
            ),
            "ModelVersion": model.metadata.get("version", "unknown"),
            "ModelCommitSHA": model.metadata.get("commit_sha", "unknown"),
            "ModelCommitHeadSHA": model.metadata.get("commit_head_sha", "unknown"),
            "ModelArchitecture": model.metadata.get("model_architecture", "unknown"),
            "RowProcessingID": hash_id,
        }
        df = pd.DataFrame(values)
        db_client.append_pandas_to_table(df, "f_predictions")

        # Return actual or fallback predictions
        return preds

    # Run challenger model inference and log predictions, but do not return these to client.
    for challenger in model_store.challengers:
        _ = run_inference_and_log(challenger, transformed_df)

    # Run champion model inference, persist metadata, and return these predictions to client.
    preds = run_inference_and_log(model_store.champion, transformed_df)
    transformed_df["Category"] = preds
    transformed_df["RowProcessingID"] = hash_id

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


# -- Upload -------------------------------------------------
@router.post(
    "/upload",
    responses={
        200: {
            "description": "CSV data appended to table successfully",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "example": {
                            "message": "CSV data appended to table successfully"
                        },
                    }
                }
            },
        },
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
    """Upload already-transformed transactions into the main table.

    ## Parameters
    - **file** (`UploadFile`): Input CSV file in normalized transaction format.
    - **transaction_service** (`TransactionService`): Upload service.
    - **user** (`dict`): Authenticated user payload.

    ## Returns
    - **JSONResponse**: Success message with HTTP 200 after rows are appended.
    """
    # Validate content type using CSVImportRequest contract
    CSVImportRequest(content_type=file.content_type or "")

    transaction_service.upload_transactions(file.file, user_email=user["sub"])
    return JSONResponse(
        status_code=200, content={"message": "CSV data appended to table successfully"}
    )
