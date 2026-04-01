"""API dependency providers.

This module defines functions that provide dependencies for API endpoints, that can be
injected using FastAPI's Depends system. These functions typically resolve resolve
services from the application's dependency injection container, allowing for loose
coupling between API endpoints and service implementations.
"""

from app.core.container import container
from app.core.security import require_role, require_user
from app.services.assets import AssetService
from app.services.categories import CategoriesService
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService
from app.services.model import ModelService
from app.services.transactions import TransactionService
from app.services.users import UsersService

# -- Security -----------------------------------------------------------------
get_require_user = require_user
get_require_admin = require_role("admin")


# -- Services -----------------------------------------------------------------
def get_categories_service() -> CategoriesService:
    return container.resolve("categories_service")


def get_model_store() -> ModelService:
    return container.resolve("model_store")


def get_users_service() -> UsersService:
    return container.resolve("users_service")


def get_google_oauth_service() -> GoogleOAuthService:
    return container.resolve("google_oauth_service")


def get_jwt_service() -> AppJwtService:
    return container.resolve("jwt_service")


def get_transaction_service() -> TransactionService:
    return container.resolve("transaction_service")


def get_asset_service() -> AssetService:
    return container.resolve("asset_service")
