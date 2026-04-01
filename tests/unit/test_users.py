"""Tests for UsersService using shared DuckDB mock database client."""

import pandas as pd
import pytest

from app.services.users import UsersService
from tests.helpers.duckdb_mock_client import DuckDBMockClient

DATASET = "test_dataset_dev"


def create_test_users_db() -> pd.DataFrame:
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
            "_RowCreatedAt": [pd.Timestamp("2024-01-01 00:00:00")] * 6,
            "_RowUpdatedAt": [pd.Timestamp("2024-01-01 00:00:00")] * 6,
            "_RowUploadHash": [101, 102, 103, 104, 105, 106],
        }
    )


@pytest.fixture
def users_service() -> UsersService:
    db_client = DuckDBMockClient(
        dataset=DATASET,
        seed_tables={"d_credentials": create_test_users_db()},
    )
    return UsersService(db_client=db_client)


def test_users_service_with_real_sql_execution(users_service: UsersService):
    result = users_service.get_user_by_email("john.doe@example.com")
    assert result == {"email": "john.doe@example.com", "role": "user"}

    admin_result = users_service.get_user_by_email("admin@company.com")
    assert admin_result == {"email": "admin@company.com", "role": "admin"}

    nonexistent_result = users_service.get_user_by_email("nonexistent@example.com")
    assert nonexistent_result == {}


def test_users_service_malformed_emails(users_service: UsersService):
    assert users_service.get_user_by_email("invalid.email.com") == {}
    assert users_service.get_user_by_email("user@@example.com") == {}
    assert users_service.get_user_by_email("user@") == {}
    assert users_service.get_user_by_email("@example.com") == {}
    assert users_service.get_user_by_email("user name@example.com") == {}
    assert users_service.get_user_by_email("user<>@example.com") == {}


def test_users_service_null_and_empty_inputs(users_service: UsersService):
    assert users_service.get_user_by_email(None) == {}
    assert users_service.get_user_by_email("") == {}
    assert users_service.get_user_by_email("   ") == {}
    assert users_service.get_user_by_email("\t\n") == {}


def test_users_service_sql_injection_attempts(users_service: UsersService):
    assert users_service.get_user_by_email("admin@company.com' OR '1'='1") == {}
    assert (
        users_service.get_user_by_email(
            "admin@company.com'; SELECT * FROM d_credentials; --"
        )
        == {}
    )
    assert (
        users_service.get_user_by_email(
            "admin@company.com'; DROP TABLE d_credentials; --"
        )
        == {}
    )
    assert users_service.get_user_by_email("admin@company.com' -- ") == {}


def test_users_service_case_sensitivity_and_whitespace(users_service: UsersService):
    assert users_service.get_user_by_email("JOHN.DOE@EXAMPLE.COM") == {}
    assert users_service.get_user_by_email("  john.doe@example.com  ") == {}


def test_users_service_extreme_inputs(users_service: UsersService):
    very_long_email = "a" * 1000 + "@example.com"
    assert users_service.get_user_by_email(very_long_email) == {}
    assert users_service.get_user_by_email("üser@éxample.com") == {}
    assert users_service.get_user_by_email("user+test@example.com") == {}
    assert users_service.get_user_by_email("user@xn--nxasmq6b.com") == {}


def test_users_service_numeric_and_special_inputs(users_service: UsersService):
    assert users_service.get_user_by_email(12345) == {}
    assert users_service.get_user_by_email(True) == {}
    assert users_service.get_user_by_email(["admin@company.com"]) == {}
    assert users_service.get_user_by_email({"email": "admin@company.com"}) == {}
