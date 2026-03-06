from typing import Any, Callable, Protocol

from app.database_client import GoogleCloudAPI
from app.services.categories import CategoriesService
from app.services.model_store import ModelStore


# ------------------- Protocols for Type Hinting ------------------
class DatabaseClient(Protocol):
    def sql_to_pandas(self, sql: str): ...
    @property
    def dataset(self) -> str: ...


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

    This function should be called once at application startup to register all
    dependencies. The container uses lazy providers, so actual instances are only
    created when resolved, allowing for efficient resource management and easy mocking
    in tests.
    """

    # Cloud clients - register as singletons since they manage their own connections and state
    container.register("cloud_client", lambda: GoogleCloudAPI(), singleton=True)

    # Database services
    def create_lazy_categories_service():
        cloud_client = container.resolve("cloud_client")
        return CategoriesService(db_client=cloud_client)

    container.register("categories_service", create_lazy_categories_service)

    # Model service - singleton because it loads heavy ML models
    container.register("model_store", lambda: ModelStore(), singleton=True)


# Automatically setup when module is imported
setup_container()


# ----------------------- Dependency Resolution Functions -----------------------
def get_categories_service() -> CategoriesService:
    return container.resolve("categories_service")


def get_model_store() -> ModelStore:
    return container.resolve("model_store")


# ----------------------- Utility Functions for Lifecycle Management -----------------------
def get_services_requiring_startup() -> list[StartupService]:
    """Get services that need startup tasks (e.g., background loading).

    These are intended to call in FastAPI's startup event
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
