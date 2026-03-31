"""Tests for categories service using DI container pattern."""

import os
from unittest.mock import Mock

import duckdb
import pandas as pd
import pytest

from app.services.categories import CategoriesService


# -------------------------- Test Fixtures --------------------------
@pytest.fixture
def setup_categories_env():
    """Initialize the runtime env for categories tests."""
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


def create_test_categories_db() -> pd.DataFrame:
    """Create realistic test data for categories."""
    return pd.DataFrame(
        {
            "Name": [
                "Food",
                "Transport",
                "Entertainment",
                "Food",  # Duplicate for GROUP BY testing
                "Stocks",
                "Bonds",
                "Real Estate",
                "Cash",
                "Stocks",  # Duplicate for GROUP BY testing
            ],
            "Type": [
                "transaction",
                "transaction",
                "transaction",
                "transaction",
                "asset",
                "asset",
                "asset",
                "asset",
                "asset",
            ],
        }
    )


def query_mock_categories_db(query: str) -> pd.DataFrame:
    """Execute actual SQL queries on mocked category database using DuckDB."""
    mock_categories = create_test_categories_db()

    # Set up DuckDB with test data
    con = duckdb.connect()
    con.register("d_category", mock_categories)

    # Create schema and table matching the expected structure
    dataset_name = f"{os.getenv('GCP_BQ_DATASET')}_{os.getenv('ENV')}"
    con.execute(f"CREATE SCHEMA {dataset_name}")
    con.execute(f"CREATE TABLE {dataset_name}.d_category AS SELECT * FROM d_category")

    # Execute the actual query and return results
    return con.execute(query).df()


# -------------------------- Real SQL Execution Tests --------------------------
def test_categories_service_with_real_sql_execution(setup_categories_env):
    """Test CategoriesService with actual SQL execution using DuckDB."""

    def mock_sql_executor(query: str) -> pd.DataFrame:
        """Execute real SQL against DuckDB for testing."""
        return query_mock_categories_db(query)

    # Create mock client that executes real SQL
    mock_client = Mock()
    mock_client.dataset = "test_dataset_dev"
    mock_client.sql_to_pandas.side_effect = mock_sql_executor

    # Initialize the service with the mock client
    service = CategoriesService(db_client=mock_client)

    # Test expenditure categories - should be deduplicated by GROUP BY
    expenditure_result = service.get_expenditure_categories()
    expected_expenditure = [
        "Entertainment",
        "Food",
        "Transport",
    ]  # DuckDB sorts by default
    assert sorted(expenditure_result) == expected_expenditure
    assert len(expenditure_result) == 3  # Duplicates removed by GROUP BY

    # Test asset categories - should be deduplicated by GROUP BY
    asset_result = service.get_asset_categories()
    expected_assets = ["Bonds", "Cash", "Real Estate", "Stocks"]
    assert sorted(asset_result) == expected_assets
    assert len(asset_result) == 4  # Duplicates removed by GROUP BY
