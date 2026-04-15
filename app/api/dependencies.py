"""API dependency providers.

This module defines functions that provide dependencies for API endpoints, that can be
injected using FastAPI's Depends system. These functions resolve services from the
application dependency injection container, allowing for loose coupling between API
endpoints and service implementations.
"""

from app.core.container import container
from app.core.database_client import GoogleCloudAPI
from app.core.security import require_role, require_user
from app.services.assets import AssetService
from app.services.file_types import FileTypesService
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService
from app.services.model import ModelService
from app.services.reporting import ReportingService
from app.services.transactions import TransactionService
from app.services.users import UsersService

# -- Security -----------------------------------------------------------------
get_require_user = require_user
get_require_admin = require_role("admin")


# -- Services -----------------------------------------------------------------
def get_model_store() -> ModelService:
    """Resolve the model service singleton from the container."""
    return container.resolve("model_store")


def get_users_service() -> UsersService:
    """Resolve the users service from the container."""
    return container.resolve("users_service")


def get_google_oauth_service() -> GoogleOAuthService:
    """Resolve the Google OAuth service singleton from the container."""
    return container.resolve("google_oauth_service")


def get_jwt_service() -> AppJwtService:
    """Resolve the JWT service singleton from the container."""
    return container.resolve("jwt_service")


def get_transaction_service() -> TransactionService:
    """Resolve the transaction service singleton from the container."""
    return container.resolve("transaction_service")


def get_asset_service() -> AssetService:
    """Resolve the asset service from the container."""
    return container.resolve("asset_service")


def get_reporting_service() -> ReportingService:
    """Resolve the reporting service from the container."""
    return container.resolve("reporting_service")


def get_db_client() -> GoogleCloudAPI:
    """Resolve the shared Google Cloud API client from the container."""
    return container.resolve("cloud_client")


def get_file_types_service() -> FileTypesService:
    """Resolve the file types service from the container."""
    return container.resolve("file_types_service")
