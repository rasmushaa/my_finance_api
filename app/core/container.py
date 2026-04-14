"""Dependency injection container and service wiring.

This module centralizes object construction for runtime services and infrastructure
clients. The container is intentionally lightweight to keep wiring explicit and easy to
test.
"""

from typing import Any, Callable, Protocol

from app.core.database_client import GoogleCloudAPI
from app.core.settings import (
    BigQueryConfig,
    GoogleOAuthConfig,
    JWTConfig,
    ModelArtifactoryConfig,
)
from app.services.assets import AssetService
from app.services.file_types import FileTypesService
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService
from app.services.model import ModelService
from app.services.reporting import ReportingService
from app.services.transactions import TransactionService
from app.services.users import UsersService


# ------------------- Protocols for Type Hinting ------------------
class StartupService(Protocol):
    """Protocol for services that require startup loading."""

    def load(self) -> None: ...


class ShutdownService(Protocol):
    """Protocol for services that require shutdown cleanup."""

    def cleanup(self) -> None: ...


# ------------------ Dependency Injection Container ------------------
class Container:
    """Simple Dependency Injection container.

    This handles registration and resolution of dependencies, allowing for easy mocking
    in tests and clean separation of concerns.
    """

    def __init__(self) -> None:
        self.__providers: dict[str, tuple[Callable[[], Any], bool]] = {}
        self.__singletons: dict[str, Any] = {}

    def register(
        self, name: str, provider: Callable[[], Any], singleton: bool = False
    ) -> None:
        """Register a provider for a dependency.

        Parameters
        ----------
        name : str
            The name of the dependency.
        provider : Callable[[], Any]
            A function that returns an instance of the dependency.
        singleton : bool, optional
            Whether to treat this dependency as a singleton (default is False).
        """
        self.__providers[name] = (provider, singleton)

    def resolve(self, name: str) -> Any:
        """Resolve a dependency by name.

        Parameters
        ----------
        name : str
            The name of the dependency to resolve.

        Returns
        -------
        Any
            The resolved dependency instance.
        """
        if name in self.__singletons:
            return self.__singletons[name]

        if name not in self.__providers:
            raise ValueError(f"No provider registered for '{name}'")

        provider, singleton = self.__providers[name]
        instance = provider()

        if singleton:
            self.__singletons[name] = instance

        return instance


# ---------------------- Container Setup and Dependency Functions ----------------------
container = Container()


def create_service_provider(service_class, **dependencies):
    """Generic provider factory for services with dependencies.

    Parameters
    ----------
    service_class : type
        The service class to instantiate.
    **dependencies : dict
        Mapping of parameter names to container dependency names.
        Example: create_service_provider(MyService, db_client="cloud_client", model="model_store")

    Returns
    -------
    Callable[[], Any]
        Provider function that resolves dependencies lazily from container and
        instantiates ``service_class``.
    """

    def provider():
        """Construct service class by resolving named container dependencies."""
        resolved_deps = {
            param: container.resolve(dep_name)
            for param, dep_name in dependencies.items()
        }
        return service_class(**resolved_deps)

    return provider


def setup_container():
    """Register all runtime providers in the global container.

    The setup is intentionally explicit to keep startup behavior easy to audit and to
    simplify test-time overrides.
    """

    # Typed settings
    container.register("gcp_config", lambda: BigQueryConfig.from_env(), singleton=True)
    container.register("jwt_config", lambda: JWTConfig.from_env(), singleton=True)
    container.register(
        "google_oauth_config",
        lambda: GoogleOAuthConfig.from_env(),
        singleton=True,
    )
    container.register(
        "model_artifactory_config",
        lambda: ModelArtifactoryConfig.from_env(),
        singleton=True,
    )

    # Cloud clients - register as singletons
    container.register(
        "cloud_client",
        create_service_provider(GoogleCloudAPI, config="gcp_config"),
        singleton=True,
    )

    # Database services
    container.register(
        "users_service",
        create_service_provider(UsersService, db_client="cloud_client"),
    )

    # JWT service - singleton
    container.register(
        "jwt_service",
        create_service_provider(
            AppJwtService,
            user_client="users_service",
            config="jwt_config",
        ),
        singleton=True,
    )

    # OAuth services - singleton
    container.register(
        "google_oauth_service",
        create_service_provider(
            GoogleOAuthService,
            config="google_oauth_config",
        ),
        singleton=True,
    )

    # Model service - singleton
    container.register(
        "model_store",
        create_service_provider(ModelService, db_client="cloud_client"),
        singleton=True,
    )

    # File types service
    container.register(
        "file_types_service",
        create_service_provider(FileTypesService, db_client="cloud_client"),
    )

    # Transaction service
    container.register(
        "transaction_service",
        create_service_provider(
            TransactionService,
            db_client="cloud_client",
            file_types_service="file_types_service",
        ),
        singleton=True,
    )

    # Assets service
    container.register(
        "asset_service",
        create_service_provider(AssetService, db_client="cloud_client"),
    )

    # Reporting service
    container.register(
        "reporting_service",
        create_service_provider(ReportingService, db_client="cloud_client"),
    )


setup_container()


# ----------------------- Utility Functions for Lifecycle Management -----------------------
def get_services_requiring_startup() -> list[StartupService]:
    """Get services that need startup tasks (e.g., background loading).

    These are intended to be called in FastAPI's startup event
    to ensure they are ready before handling requests.

    Returns
    -------
    list[StartupService]
        Services that should be preloaded before handling requests.
    """
    model_store = container.resolve("model_store")
    return [model_store]


def get_services_requiring_shutdown() -> list[ShutdownService]:
    """Get services that need cleanup on shutdown.

    Returns
    -------
    list[ShutdownService]
        Services that should be cleaned up during shutdown.
    """
    return []
