"""Tests for mock schema validation against BigQuery YAML source-of-truth."""

import pandas as pd
import pytest

from scripts.bigquery_table_config import load_bigquery_table_definitions
from tests.helpers.duckdb_mock_client import DuckDBMockClient


def test_bigquery_table_yaml_contains_expected_tables():
    tables = load_bigquery_table_definitions()
    assert {
        "d_credentials",
        "d_filetypes",
        "f_transactions",
        "f_assets",
        "f_predictions",
    }.issubset(tables)


def test_mock_client_seed_rejects_schema_drift():
    bad_seed = pd.DataFrame(
        {
            "UserEmail": ["user@example.com"],
            "UserRole": ["user"],
            "_RowStatus": ["i"],
            "_RowCreatedAt": [pd.Timestamp("2024-01-01 00:00:00")],
            "_RowUpdatedAt": [pd.Timestamp("2024-01-01 00:00:00")],
            # Missing _RowUploadHash on purpose
        }
    )

    with pytest.raises(ValueError, match="schema mismatch"):
        DuckDBMockClient(seed_tables={"d_credentials": bad_seed})


def test_mock_client_seed_rejects_unknown_table():
    unknown_seed = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError, match="is not declared"):
        DuckDBMockClient(seed_tables={"unknown_table": unknown_seed})
