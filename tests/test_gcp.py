"""These are basic test for Google Cloud API interactions.

They use mocking to avoid real GCP calls, but usefulness is limited since they don't
test actual GCP integration.
"""

import os
from unittest.mock import Mock, patch

import pandas as pd

from app.database_client import GoogleCloudAPI


@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "GCP_LOCATION": "US",
        "GCP_CGS_BUCKET": "test-bucket",
        "GCP_CGS_BUCKET_DIR": "test-dir",
    },
)
def test_dataset_property_with_default_env():
    """Test that dataset property includes default environment suffix."""
    api = GoogleCloudAPI()
    assert api.dataset == "test_dataset_dev"  # Default ENV is 'dev'


@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "prod",
        "GCP_LOCATION": "US",
        "GCP_CGS_BUCKET": "test-bucket",
        "GCP_CGS_BUCKET_DIR": "test-dir",
    },
)
def test_dataset_property_with_prod_env():
    """Test that dataset property works with production environment."""
    api = GoogleCloudAPI()
    assert api.dataset == "test_dataset_prod"


@patch("pandas_gbq.read_gbq")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_CGS_BUCKET": "test-bucket",
        "GCP_CGS_BUCKET_DIR": "test-dir",
    },
)
def test_sql_to_pandas(mock_read_gbq):
    """Test sql_to_pandas method with mocked pandas_gbq."""
    # Arrange
    mock_df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    mock_read_gbq.return_value = mock_df

    api = GoogleCloudAPI()
    sql_query = "SELECT * FROM test_table"

    # Act
    result = api.sql_to_pandas(sql_query)

    # Assert
    mock_read_gbq.assert_called_once_with(
        sql_query, project_id="test-project", location="US", progress_bar_type=None
    )
    pd.testing.assert_frame_equal(result, mock_df)


@patch("pandas_gbq.to_gbq")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_CGS_BUCKET": "test-bucket",
        "GCP_CGS_BUCKET_DIR": "test-dir",
    },
)
def test_write_pandas_to_table_with_mixed_columns(mock_to_gbq):
    """Test write_pandas_to_table with mixed column types including dates."""
    # Arrange
    api = GoogleCloudAPI()
    df = pd.DataFrame(
        {
            "name": ["Alice", "Bob"],
            "city": ["NYC", "LA"],
            "transaction_date": ["2023-01-01", "2023-01-02"],
            "end_date": ["2023-12-31", "2023-12-30"],
            "amount": [100.0, 200.0],
        }
    )
    table_name = "test_table"

    # Act
    api.write_pandas_to_table(df, table_name)

    # Assert
    mock_to_gbq.assert_called_once()
    _, kwargs = mock_to_gbq.call_args

    schema = kwargs["table_schema"]

    # Check string columns
    string_columns = [col["name"] for col in schema if col["type"] == "STRING"]
    assert "name" in string_columns
    assert "city" in string_columns

    # Check date columns
    date_columns = [col["name"] for col in schema if col["type"] == "DATE"]
    assert len(date_columns) == 2
    assert "transaction_date" in date_columns
    assert "end_date" in date_columns

    # Check other call parameters
    assert kwargs["destination_table"] == "test_dataset_test.test_table"
    assert kwargs["project_id"] == "test-project"
    assert kwargs["location"] == "US"
    assert kwargs["if_exists"] == "append"


@patch("google.cloud.storage.Client")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_CGS_BUCKET": "test-bucket",
        "GCP_CGS_BUCKET_DIR": "test-dir",
    },
)
def test_upload_file_to_gcs(mock_storage_client):
    """Test upload_file_to_gcs method."""
    # Arrange
    mock_client = Mock()
    mock_bucket = Mock()
    mock_blob = Mock()

    mock_storage_client.return_value = mock_client
    mock_client.get_bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    api = GoogleCloudAPI()
    local_file_path = "test_file.txt"

    # Act
    api.upload_file_to_gcs(local_file_path)

    # Assert
    mock_storage_client.assert_called_once()
    mock_client.get_bucket.assert_called_once_with("test-bucket")
    mock_bucket.blob.assert_called_once_with("test-dir/test_file.txt")
    mock_blob.upload_from_filename.assert_called_once_with(local_file_path)


@patch("google.cloud.storage.Client")
@patch.dict(
    os.environ,
    {
        "GCP_PROJECT_ID": "test-project",
        "GCP_BQ_DATASET": "test_dataset",
        "ENV": "test",
        "GCP_LOCATION": "US",
        "GCP_CGS_BUCKET": "test-bucket",
        "GCP_CGS_BUCKET_DIR": "test-dir",
    },
)
def test_download_file_from_gcs(mock_storage_client):
    """Test download_file_from_gcs method."""
    # Arrange
    mock_client = Mock()
    mock_bucket = Mock()
    mock_blob = Mock()

    mock_storage_client.return_value = mock_client
    mock_client.get_bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    api = GoogleCloudAPI()
    local_file_path = "downloaded_file.txt"

    # Act
    api.download_file_from_gcs(local_file_path)

    # Assert
    mock_storage_client.assert_called_once()
    mock_client.get_bucket.assert_called_once_with("test-bucket")
    mock_bucket.blob.assert_called_once_with("test-dir/downloaded_file.txt")
    mock_blob.download_to_filename.assert_called_once_with(local_file_path)
