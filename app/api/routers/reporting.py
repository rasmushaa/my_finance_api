"""Administrative reporting endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_reporting_service, get_require_admin
from app.schemas.reporting import ModelAccuracyResponse
from app.services.reporting import ReportingService

router = APIRouter(prefix="/reporting", tags=["Reporting Endpoints"])


@router.get(
    "/model-accuracy",
    response_model=ModelAccuracyResponse,
    responses={
        200: {
            "description": "Successfully retrieved the model accuracy data.",
        },
    },
)
def get_model_accuracy(
    starting_from: str,
    payload: dict = Depends(get_require_admin),
    reporting_service: ReportingService = Depends(get_reporting_service),
):
    """Return monthly model accuracy statistics from a start date onward.

    ## Parameters
    - **starting_from** (`str`): Lower date bound in `YYYY-MM-DD` format.
    - **payload** (`dict`): Authenticated admin JWT payload.
    - **reporting_service** (`ReportingService`): Service that builds the accuracy table.

    ## Returns
    - **ModelAccuracyResponse**: List of monthly accuracy rows for each model/category.
    """
    df = reporting_service.get_model_accuracy_table(starting_from)
    return ModelAccuracyResponse(rows=df.to_dict(orient="records"))
