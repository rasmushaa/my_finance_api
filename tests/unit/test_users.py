"""Tests for users service using DI container pattern."""

import os
from unittest.mock import Mock

import duckdb
import pandas as pd
import pytest

from app.services.users import UsersService


# -------------------------- Test Fixtures --------------------------
@pytest.fixture
def setup_users_env():
    """Initialize the runtime env for users tests."""
    os.environ["GCP_BQ_DATASET"] = "test_dataset"
    os.environ["ENV"] = "dev"
    yield
    # Cleanup after test
    for key in ["GCP_BQ_DATASET", "ENV"]:
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def mock_gcp_client():
    """Create a mock GCP client for testing."""
    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    return mock_client


def create_test_users_db() -> pd.DataFrame:
    """Create realistic test data for users."""
    return pd.DataFrame(
        {
            "UserEmail": [
                "john.doe@example.com",
                "jane.smith@example.com",
                "admin@company.com",
                "viewer@company.com",
                "editor@company.com",
                "deleted.user@example.com",
            ],
            "UserRole": [
                "user",
                "user",
                "admin",
                "viewer",
                "editor",
                "user",
            ],
            "_RowStatus": ["i", "i", "i", "i", "i", "d"],
        }
    )


def query_mock_users_db(query: str) -> pd.DataFrame:
    """Execute actual SQL queries on mocked users database using DuckDB."""
    mock_users = create_test_users_db()

    # Set up DuckDB with test data
    con = duckdb.connect()
    con.register("d_credentials", mock_users)

    # Create schema and table matching the expected structure
    dataset_name = f"{os.getenv('GCP_BQ_DATASET')}_{os.getenv('ENV')}"
    con.execute(f"CREATE SCHEMA {dataset_name}")
    con.execute(
        f"CREATE TABLE {dataset_name}.d_credentials AS SELECT * FROM d_credentials"
    )

    # Execute the actual query and return results
    return con.execute(query).df()


# -------------------------- Real SQL Execution Tests --------------------------
def test_users_service_with_real_sql_execution(setup_users_env):
    """Test UsersService with actual SQL execution using DuckDB."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    # Create mock client that executes real SQL
    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor

    # Initialize the service with the mock client
    service = UsersService(db_client=mock_client)

    # Test getting user by email - existing user
    result = service.get_user_by_email("john.doe@example.com")
    expected_result = {"email": "john.doe@example.com", "role": "user"}
    assert result == expected_result

    # Test getting user by email - admin user
    admin_result = service.get_user_by_email("admin@company.com")
    expected_admin = {"email": "admin@company.com", "role": "admin"}
    assert admin_result == expected_admin

    # Test getting user by email - non-existent user (should return empty dict)
    nonexistent_result = service.get_user_by_email("nonexistent@example.com")
    assert nonexistent_result == {}


# -------------------------- Critical Security & Edge Case Tests --------------------------
def test_users_service_malformed_emails(setup_users_env):
    """Test UsersService with malformed email inputs - critical for authentication security."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor
    service = UsersService(db_client=mock_client)

    # Test malformed emails - missing @ symbol
    result = service.get_user_by_email("invalid.email.com")
    assert result == {}

    # Test malformed emails - multiple @ symbols
    result = service.get_user_by_email("user@@example.com")
    assert result == {}

    # Test malformed emails - missing domain
    result = service.get_user_by_email("user@")
    assert result == {}

    # Test malformed emails - missing user part
    result = service.get_user_by_email("@example.com")
    assert result == {}

    # Test malformed emails - spaces in email
    result = service.get_user_by_email("user name@example.com")
    assert result == {}

    # Test malformed emails - invalid characters
    result = service.get_user_by_email("user<>@example.com")
    assert result == {}


def test_users_service_null_and_empty_inputs(setup_users_env):
    """Test UsersService with None and empty inputs - critical for authentication."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor
    service = UsersService(db_client=mock_client)

    # Test None input
    result = service.get_user_by_email(None)
    assert result == {}

    # Test empty string
    result = service.get_user_by_email("")
    assert result == {}

    # Test whitespace only
    result = service.get_user_by_email("   ")
    assert result == {}

    # Test tab and newline characters
    result = service.get_user_by_email("\t\n")
    assert result == {}


def test_users_service_sql_injection_attempts(setup_users_env):
    """Test UsersService against SQL injection attacks - CRITICAL SECURITY TEST."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor
    service = UsersService(db_client=mock_client)

    # Test SQL injection with single quote
    injection_attempt = "admin@company.com' OR '1'='1"
    result = service.get_user_by_email(injection_attempt)
    assert result == {}  # Should not return any data

    # Test SQL injection with UNION SELECT
    injection_attempt = "admin@company.com'; SELECT * FROM d_credentials; --"
    result = service.get_user_by_email(injection_attempt)
    assert result == {}

    # Test SQL injection with DROP TABLE attempt
    injection_attempt = "admin@company.com'; DROP TABLE d_credentials; --"
    result = service.get_user_by_email(injection_attempt)
    assert result == {}

    # Test SQL injection with comment bypass
    injection_attempt = "admin@company.com' -- "
    result = service.get_user_by_email(injection_attempt)
    assert result == {}


def test_users_service_case_sensitivity_and_whitespace(setup_users_env):
    """Test UsersService case sensitivity and whitespace handling."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor
    service = UsersService(db_client=mock_client)

    # Test case sensitivity - emails should be case sensitive
    result = service.get_user_by_email("JOHN.DOE@EXAMPLE.COM")
    assert result == {}  # Should not match lowercase version

    # Test leading/trailing whitespace
    result = service.get_user_by_email("  john.doe@example.com  ")
    assert result == {}  # Should not match due to whitespace


def test_users_service_extreme_inputs(setup_users_env):
    """Test UsersService with extreme and boundary inputs."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor
    service = UsersService(db_client=mock_client)

    # Test extremely long email (potential buffer overflow attempt)
    very_long_email = "a" * 1000 + "@example.com"
    result = service.get_user_by_email(very_long_email)
    assert result == {}

    # Test Unicode characters
    result = service.get_user_by_email("üser@éxample.com")
    assert result == {}

    # Test email with special characters
    result = service.get_user_by_email("user+test@example.com")
    assert result == {}

    # Test punycode domain
    result = service.get_user_by_email(
        "user@xn--nxasmq6b.com"
    )  # internationalized domain
    assert result == {}


def test_users_service_numeric_and_special_inputs(setup_users_env):
    """Test UsersService with numeric and other special data types."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_users_db(query)

    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor
    service = UsersService(db_client=mock_client)

    # Test numeric input
    result = service.get_user_by_email(12345)
    assert result == {}

    # Test boolean input
    result = service.get_user_by_email(True)
    assert result == {}

    # Test list input
    result = service.get_user_by_email(["admin@company.com"])
    assert result == {}

    # Test dictionary input
    result = service.get_user_by_email({"email": "admin@company.com"})
    assert result == {}
