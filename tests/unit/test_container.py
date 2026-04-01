"""Tests for the DI Container core functionality."""

from unittest.mock import Mock

import pytest

from app.core.container import Container


def test_container_initialization():
    """Test that container initializes with empty state."""
    container = Container()

    # Should have empty internal state
    assert len(container._Container__providers) == 0
    assert len(container._Container__singletons) == 0


def test_register_simple_provider():
    """Test registering a simple provider function."""
    container = Container()

    def create_string():
        return "test_value"

    container.register("test_string", create_string)

    # Provider should be registered but not singleton
    assert "test_string" in container._Container__providers
    provider, is_singleton = container._Container__providers["test_string"]
    assert provider is create_string
    assert is_singleton is False


def test_register_singleton_provider():
    """Test registering a singleton provider."""
    container = Container()

    def create_object():
        return {"id": "singleton"}

    container.register("singleton_obj", create_object, singleton=True)

    # Should be registered as singleton
    provider, is_singleton = container._Container__providers["singleton_obj"]
    assert is_singleton is True


def test_resolve_simple_dependency():
    """Test resolving a simple non-singleton dependency."""
    container = Container()

    def create_list():
        return [1, 2, 3]

    container.register("test_list", create_list)

    # Should resolve to new list each time
    result1 = container.resolve("test_list")
    result2 = container.resolve("test_list")

    assert result1 == [1, 2, 3]
    assert result2 == [1, 2, 3]
    assert result1 is not result2  # Different instances


def test_resolve_singleton_dependency():
    """Test resolving a singleton dependency."""
    container = Container()

    class TestService:
        def __init__(self):
            self.id = "service"

    container.register("service", TestService, singleton=True)

    # Should resolve to same instance each time
    result1 = container.resolve("service")
    result2 = container.resolve("service")

    assert isinstance(result1, TestService)
    assert isinstance(result2, TestService)
    assert result1 is result2  # Same instance
    assert result1.id == "service"


def test_resolve_missing_dependency_raises_error():
    """Test that resolving missing dependency raises ValueError."""
    container = Container()

    with pytest.raises(ValueError, match="No provider registered for 'nonexistent'"):
        container.resolve("nonexistent")


def test_singleton_cached_correctly():
    """Test that singletons are cached in singletons dict."""
    container = Container()

    call_count = 0

    def create_counter():
        nonlocal call_count
        call_count += 1
        return {"count": call_count}

    container.register("counter", create_counter, singleton=True)

    # First resolve should create and cache
    result1 = container.resolve("counter")
    assert result1["count"] == 1
    assert "counter" in container._Container__singletons

    # Second resolve should return cached instance
    result2 = container.resolve("counter")
    assert result2["count"] == 1  # Same count, not incremented
    assert result1 is result2


def test_non_singleton_not_cached():
    """Test that non-singletons are not cached."""
    container = Container()

    call_count = 0

    def create_counter():
        nonlocal call_count
        call_count += 1
        return {"count": call_count}

    container.register("counter", create_counter, singleton=False)

    # Each resolve should create new instance
    result1 = container.resolve("counter")
    result2 = container.resolve("counter")

    assert result1["count"] == 1
    assert result2["count"] == 2
    assert result1 is not result2
    assert "counter" not in container._Container__singletons


def test_lambda_providers():
    """Test using lambda functions as providers."""
    container = Container()

    container.register("lambda_value", lambda: "lambda_result")
    container.register("lambda_dict", lambda: {"key": "value"}, singleton=True)

    # Test non-singleton lambda
    result1 = container.resolve("lambda_value")
    assert result1 == "lambda_result"

    # Test singleton lambda
    dict1 = container.resolve("lambda_dict")
    dict2 = container.resolve("lambda_dict")
    assert dict1 == {"key": "value"}
    assert dict1 is dict2


def test_provider_with_closure():
    """Test providers that use closure variables."""
    container = Container()

    config_value = "test_config"

    def create_service():
        return Mock(config=config_value)

    container.register("service", create_service)

    result = container.resolve("service")
    assert result.config == "test_config"


def test_overriding_existing_registration():
    """Test that re-registering overwrites previous registration."""
    container = Container()

    # Register original
    container.register("value", lambda: "original")
    assert container.resolve("value") == "original"

    # Override with new registration
    container.register("value", lambda: "overridden")
    assert container.resolve("value") == "overridden"


def test_complex_dependency_chain():
    """Test resolving dependencies that depend on other dependencies."""
    container = Container()

    # Register base dependency - create mock with proper attributes
    def create_database():
        db = Mock()
        db.name = "db"
        return db

    container.register("database", create_database, singleton=True)

    # Register service that depends on database
    def create_service():
        service = Mock()
        service.db = container.resolve("database")
        service.name = "service"
        return service

    container.register("service", create_service)

    # First resolution - should create and cache database
    service1 = container.resolve("service")
    assert service1.name == "service"
    assert service1.db.name == "db"

    # Second resolution - should reuse the same database singleton
    service2 = container.resolve("service")
    assert service2.name == "service"
    assert service2.db.name == "db"

    # Services are different instances (service is not singleton)
    assert service1 is not service2

    # But they share the same database instance (database is singleton)
    assert service1.db is service2.db
