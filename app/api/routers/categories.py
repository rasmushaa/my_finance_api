from fastapi import APIRouter, Depends

from app.api.dependencies.providers import get_categories_service, require_user
from app.schemas.database import CategoriesResponse
from app.schemas.error import ErrorResponse
from app.services.categories import CategoriesService

router = APIRouter(prefix="/data/categories", tags=["categories"])


@router.get(
    "/expenditures",
    response_model=CategoriesResponse,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized - Invalid or missing authentication credentials",
        },
    },
)
def get_expenditure_categories(
    payload: dict = Depends(require_user),
    categories_service: CategoriesService = Depends(get_categories_service),
):
    categories_list = categories_service.get_expenditure_categories()
    return CategoriesResponse(categories=categories_list)


@router.get(
    "/assets",
    response_model=CategoriesResponse,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized - Invalid or missing authentication credentials",
        },
    },
)
def get_asset_categories(
    payload: dict = Depends(require_user),
    categories_service: CategoriesService = Depends(get_categories_service),
):
    categories_list = categories_service.get_asset_categories()
    return CategoriesResponse(categories=categories_list)
