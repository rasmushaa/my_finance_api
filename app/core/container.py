from typing import Any, Callable, Protocol

from app.core.database_client import GoogleCloudAPI
from app.services.assets import AssetService
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService
from app.services.model import ModelService
from app.services.transactions import TransactionService
from app.services.users import UsersService


# ------------------- Protocols for Type Hinting ------------------
class StartupService(Protocol):
    def load(self) -> None: ...


class ShutdownService(Protocol):
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
    """

    def provider():
        resolved_deps = {
            param: container.resolve(dep_name)
            for param, dep_name in dependencies.items()
        }
        return service_class(**resolved_deps)

    return provider


def setup_container():
    """Set up the dependency injection container with all services and clients."""

    # Cloud clients - register as singletons
    container.register("cloud_client", lambda: GoogleCloudAPI(), singleton=True)

    # Database services
    container.register(
        "users_service",
        create_service_provider(UsersService, db_client="cloud_client"),
    )

    # JWT service - singleton
    container.register(
        "jwt_service",
        create_service_provider(AppJwtService, user_client="users_service"),
        singleton=True,
    )

    # OAuth services - singleton
    container.register(
        "google_oauth_service",
        lambda: GoogleOAuthService(),
        singleton=True,
    )

    # Model service - singleton
    container.register("model_store", lambda: ModelService(), singleton=True)

    # Transaction service - depends on cloud_client and model_store
    container.register(
        "transaction_service",
        create_service_provider(
            TransactionService,
            db_client="cloud_client",
            model_service="model_store",
        ),
        singleton=True,
    )

    # Assets service
    container.register(
        "asset_service",
        create_service_provider(AssetService, db_client="cloud_client"),
    )


setup_container()


# ----------------------- Utility Functions for Lifecycle Management -----------------------
def get_services_requiring_startup() -> list[StartupService]:
    """Get services that need startup tasks (e.g., background loading).

    These are intended to be called in FastAPI's startup event
    to ensure they are ready before handling requests.

    Returns: List[StartupService]
        List of services having a `load()` method that should be called on startup.
    """
    model_store = container.resolve("model_store")
    return [model_store]


def get_services_requiring_shutdown() -> list[ShutdownService]:
    """Get services that need cleanup on shutdown.

    Returns: List[ShutdownService]
        List of service instances that need cleanup.
    """
    return []
