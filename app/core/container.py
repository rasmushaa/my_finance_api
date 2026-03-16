from typing import Any, Callable, Protocol

from app.core.database_client import GoogleCloudAPI
from app.services.categories import CategoriesService
from app.services.google_oauth import GoogleOAuthService
from app.services.jwt import AppJwtService
from app.services.model import ModelService
from app.services.users import UsersService


# ------------------- Protocols for Type Hinting ------------------
class StartupService(Protocol):
    async def load(self) -> None: ...


class ShutdownService(Protocol):
    async def cleanup(self) -> None: ...


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


def setup_container():
    """Set up the dependency injection container with all services and clients.

    This function is called once at application startup to register all dependencies.
    The container uses lazy providers, so actual instances are only created when
    resolved, allowing for efficient resource management and easy mocking in tests.
    """

    # Cloud clients - register as singletons since they manage their own connections and state
    container.register("cloud_client", lambda: GoogleCloudAPI(), singleton=True)

    # Generic factory for services requiring a database client
    def create_service_with_db_client(service_class):
        def provider():
            cloud_client = container.resolve("cloud_client")
            return service_class(db_client=cloud_client)

        return provider

    # Database services
    container.register(
        "categories_service", create_service_with_db_client(CategoriesService)
    )
    container.register("users_service", create_service_with_db_client(UsersService))

    # JWT service - singleton for performance
    container.register(
        "jwt_service",
        lambda: AppJwtService(user_client=container.resolve("users_service")),
        singleton=True,
    )

    # OAuth services - singletons for performance
    container.register(
        "google_oauth_service", lambda: GoogleOAuthService(), singleton=True
    )

    # Model service - singleton because it loads heavy ML models
    container.register("model_store", lambda: ModelService(), singleton=True)


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
